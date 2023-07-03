"""
monobit.formats.xlfd.hbf - Hanzi Bitmap File Format

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ...storage import loaders, savers
from ...magic import FileFormatError
from ...font import Font, Coord
from ...glyph import Glyph
from ...binary import ceildiv

from .bdf import read_props
from .xlfd import parse_xlfd_properties, create_xlfd_properties
from .xlfd import create_xlfd_name
from ..text.yaff import globalise_glyph_metrics


@loaders.register(
    name='hbf',
    magic=(b'HBF_START_FONT ',),
    patterns=('*.hbf',),
)
def load_hbf(instream):
    """
    Load font from Hanzi Bitmap Format (HBF) file.
    """
    where = instream.where
    instream = instream.text
    (
        comments, hbf_props, x_props,
        b2_ranges, b3_ranges, c_ranges
    ) = _read_hbf_global(instream)
    logging.info('hbf properties:')
    for name, value in hbf_props.items():
        logging.info('    %s: %s', name, value)
    logging.info('x properties:')
    for name, value in x_props.items():
        logging.info('    %s: %s', name, value)
    glyphs = _read_hbf_glyphs(
        instream, where, b2_ranges, b3_ranges, c_ranges, hbf_props
    )
    # check number of characters, but don't break if no match
    # if nchars != len(glyphs):
    #     logging.warning('Number of characters found does not match CHARS declaration.')
    properties = _parse_properties(hbf_props, x_props)
    font = Font(glyphs, comment=comments, **properties)
    # label glyphs with code scheme, if known and recognised
    font = font.label()
    return font

@savers.register(linked=load_hbf)
def save_hbf(fonts, outstream, code_scheme:str=''):
    """
    Save font to Hanzi Bitmap Format (HBF) file.

    code_scheme: override HBF_CODE_SCHEME value (default: use encoding)
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to HBF file.')
    # ensure codepoint values are set
    font = fonts[0]
    _save_hbf(font, outstream.text, outstream.where, code_scheme)


##############################################################################
# HBF reader

# https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/Format.html
# https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/BitmapFile.html

# https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/CodeSchemes.html
# these are matches to encodings for which we have unicode mappings
_HBF_CODE_SCHEMES_BASE = {
    # > GB2312-1980
    # > not simply "GB", nor "GB2312". there are many GuoBiao's for hanzi.
    # GBK is a superset of GB2312, often taken to mean windows-936
    'GB2312': 'gbk',
    # > Big5
    # > any so-called "Big5" bitmap file(s) can be used, but such bitmap file(s)
    # > must conform to the Big5 character code standard without vendor-added
    # > character code. The Big5 character code scheme has the following valid
    # > code ranges for hanzi:
    # >        0xA440-0xC67E for frequently-used hanzi      (5401 chars)
    # >        0xC940-0xF9D5 for less-frequently-used hanzi (7652 chars)
    'Big5': 'big5',
    # Big5 ETen 3.10
    # > not simply "Big5"; use specifically the bitmap files in the
    # > ETen system 3.10 which contains vendor-specific character codes.
    # > Similar specification of other vendors and software versions are
    # > acceptable, to provide a more accurate description.
    'Big5 ETen': 'big5-eten',
    # CNS11643-92p1 to CNS11643-92p7
    # Chinese National Standard of ROC, containing 7 planes.
    # complication is that HBF defines 2-byte coding only
    # so the plane number would need to be extracted from the HBF_CODE_SCHEME
    'CNS11643': 'cns11643',
    # > Unicode 1.1
    # > version "1.1", equivalent to ISO/IEC 10646-1 UCS-2, level 3. Perhaps there
    # > will be vendor-specific versions at a later date.
    'Unicode': 'unicode',
    # > JISX0208-1990
    # > Japanese Industrial Standard
    'JISX0208': 'jisx0208',
    # > KSC5601-1987
    # > Korean Standard Code (formingly KIPS)
    'KSC5601': 'ksc5601'
}

def _normalise_code_scheme(hbf_cs):
    """Normalise the code scheme name for matching."""
    return hbf_cs.lower().replace(' ', '-').replace('.', '-')

# sort from longer to shorter keys to resolve collisions
_HBF_CODE_SCHEMES = {
    _normalise_code_scheme(_k): _v
    for _k, _v in sorted(
        _HBF_CODE_SCHEMES_BASE.items(),
        key=lambda _i: len(_i[0]),
        reverse=True,
    )
}

def _map_code_scheme(hbf_code_scheme):
    """
    Map HBF code scheme description to monobit encoding name.
    returns encoding_name, plane
    """
    hbf_code_scheme = _normalise_code_scheme(hbf_code_scheme)
    for cs, enc in _HBF_CODE_SCHEMES.items():
        if hbf_code_scheme.startswith(cs):
            if cs == 'cns11643':
                # assume the last nonempty char is the plane number
                plane_desc = hbf_code_scheme.strip()[-1:]
                try:
                    return enc, int(plane_desc)
                except ValueError:
                    pass
            return enc, None
    return hbf_code_scheme, None

def _read_hbf_global(instream):
    """Read global section of HBF file."""
    hbf_props, comments = _read_section(
        instream, end='ENDFONT',
        subsections=(
            'STARTPROPERTIES', 'HBF_START_BYTE_2_RANGES',
            'HBF_START_BYTE_3_RANGES', 'HBF_START_CODE_RANGES',
        )
    )
    hbf_props = dict(hbf_props)
    x_props = dict(hbf_props.pop('STARTPROPERTIES', {}))
    b2_ranges = hbf_props.pop('HBF_START_BYTE_2_RANGES')
    b3_ranges = hbf_props.pop('HBF_START_BYTE_3_RANGES', {})
    c_ranges = hbf_props.pop('HBF_START_CODE_RANGES')
    comments = '\n'.join(comments)
    return comments, hbf_props, x_props, b2_ranges, b3_ranges, c_ranges

def _read_section(instream, subsections, end):
    """Read a section of HBF file."""
    logging.debug('reading section %s', end)
    props = []
    comments = []
    while True:
        head_props, head_comments, keyword = read_props(
            instream, ends=subsections + (end,)
        )
        props.extend(head_props)
        comments.extend(head_comments)
        logging.debug((keyword, end, subsections))
        if not keyword or keyword == end:
            return props, comments
        sec_props, sec_comments = _read_section(
            instream, subsections=(), end=keyword.replace('START', 'END')
        )
        props.append((keyword, sec_props))
        # we're combining all comments in one block
        comments.append('')
        comments.extend(sec_comments)

def indexer(plane, code_range, b2_ranges, b3_ranges):
    """Generator to run through code range keeping to allowed low-bytes."""
    if not code_range:
        return
    n_bytes = 3 if b3_ranges else 2
    planeshift = 8 * n_bytes
    hishift = 8 * (n_bytes-1)
    loshift = 8 * (n_bytes-2)
    himask = (1 << hishift) - 1
    lomask = (1 << loshift) - 1
    for codepoint in code_range:
        byte2 = (codepoint & himask) >> loshift
        if all(byte2 not in _range for _range in b2_ranges):
            continue
        if n_bytes == 3:
            byte3 = codepoint & lomask
            if all(byte3 not in _range for _range in b3_ranges):
                continue
        if plane is None:
            yield codepoint
        else:
            yield ((0x80 + plane) << planeshift) + codepoint

def _convert_ranges(b2_ranges):
    """Convert range descriptors to ranges."""
    b2_ranges = tuple(
        _split_hbf_ints(_range, sep='-')
        for _, _range in b2_ranges
    )
    b2_ranges = tuple(
        range(_range[0], _range[1]+1)
        for _range in b2_ranges
    )
    return b2_ranges

def _read_hbf_glyphs(instream, where, b2_ranges, b3_ranges, c_ranges, props):
    """Read glyphs from bitmap files and index according to ranges."""
    width, height, _, _ = _split_hbf_ints(props['HBF_BITMAP_BOUNDING_BOX'])
    bytesize = height * ceildiv(width, 8)
    # get 2nd- and 3rd-byte ranges
    b2_ranges = _convert_ranges(b2_ranges)
    b3_ranges = _convert_ranges(b3_ranges)
    # get encoding plane (0th byte)
    _, plane = _map_code_scheme(props['HBF_CODE_SCHEME'])
    code_ranges = []
    glyphs = []
    for _, c_desc in c_ranges:
        code_range, filename, offset = c_desc.split()
        code_range = _split_hbf_ints(code_range, sep='-')
        code_range = range(code_range[0], code_range[1]+1)
        offset = hbf_int(offset)
        path = Path(instream.name).parent
        with where.open(path / filename, 'r') as bitmapfile:
            # discard offset bytes
            bitmapfile.read(offset)
            for codepoint in indexer(plane, code_range, b2_ranges, b3_ranges):
                glyphbytes = bitmapfile.read(bytesize)
                glyphs.append(Glyph.from_bytes(
                    glyphbytes, width=width, codepoint=codepoint
                ))
    return glyphs


##############################################################################
# properties

def hbf_int(numstr):
    """Convert HBF int representation to int."""
    # HBF has c-style octals 0777
    if numstr.startswith('0') and numstr[1:2].isdigit():
        return int(numstr[1:], 8)
    return int(numstr, 0)


def _split_hbf_ints(value, sep=None):
    """Split a string and convert elements to int."""
    return tuple(hbf_int(_p) for _p in value.split(sep))


def _parse_properties(hbf_props, x_props):
    """Parse metrics and metadata."""
    # parse meaningful metadata
    properties, unparsed, plane = _parse_hbf_properties(hbf_props)
    # the FONT field *may* conform to xlfd but doesn't have to. don't parse it
    xlfd_props = parse_xlfd_properties(x_props, xlfd_name='', to_int=hbf_int)
    for key, value in unparsed.items():
        logging.info(f'Unrecognised HBF property {key}={value}')
        # preserve as property
        properties[key] = value
    for key, value in xlfd_props.items():
        if key in properties and properties[key] != value:
            logging.debug(
                'Inconsistency between HBF and XLFD properties: '
                '%s=%s (from XLFD) but %s=%s (from HBF). Taking HBF property.',
                key, value, key, properties[key]
            )
        else:
            properties[key] = value
    # ensure default codepoint gets a plane value
    if plane is not None and 'default_char' in properties:
        properties['default_char'] += (0x80+plane) * 0x10000
    # prefer hbf code scheme to charset values from xlfd
    logging.info('yaff properties:')
    for name, value in properties.items():
        logging.info('    %s: %s', name, value)
    return properties

def _parse_hbf_properties(hbf_props):
    """Parse HBF properties."""
    size, xdpi, ydpi = _split_hbf_ints(hbf_props.pop('SIZE'))
    properties = {
        'source_format': 'HBF v{}'.format(hbf_props.pop('HBF_START_FONT')),
        'point_size': size,
        'dpi': (xdpi, ydpi),
    }
    width, height, offset_x, offset_y = _split_hbf_ints(
        hbf_props.pop('HBF_BITMAP_BOUNDING_BOX')
    )
    # https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/BoundingBoxes.html
    # fontboundingbox is equal or larger than bitmap bounding box
    # may be used to specify inter-glyph and inter-line spacing
    # the documented examples show the effect of different bounding box heights
    # but the impact of the fondboundingbox offset is unclear to me
    full_width, full_height, full_offset_x, full_offset_y = _split_hbf_ints(
        hbf_props.pop('FONTBOUNDINGBOX')
    )
    properties.update({
        'line_height': full_height,
        # full_width :==: advance-width == left-bearing + width + right-bearing
        'left_bearing': offset_x,
        'right_bearing': full_width - width - offset_x,
        # I think the fontboundingbox offsets actually go unused
        'shift_up': offset_y,
    })
    # known but we don't use it
    properties['font-id'] = hbf_props.pop('FONT', None)
    # match encoding name
    code_scheme = hbf_props.pop('HBF_CODE_SCHEME')
    properties['encoding'], plane = _map_code_scheme(code_scheme)
    logging.debug(
        'Interpreting code scheme `%s` as encoding `%s` %s',
        code_scheme, properties['encoding'],
        f'plane {plane}' if plane is not None else ''
    )
    hbf_props.pop('HBF_END_FONT', None)
    # keep unparsed hbf props
    return properties, hbf_props, plane


##############################################################################
# hbf writer

def _save_hbf(font, outstream, container, code_scheme):
    """Write one font to HBF."""
    bitmap_name = container.unused_name(outstream.name + '.bin')
    hbf_props, bitmaps = _convert_to_hbf(font, bitmap_name, code_scheme)
    for name, value in hbf_props:
        logging.info('    %s: %s', name, value)
    with container.open(bitmap_name, 'w') as binfile:
        for bitmap in bitmaps:
            binfile.write(bitmap)
    for name, value in hbf_props:
        outstream.write(f'{name} {value}\n')


def _convert_to_hbf(font, bitmap_name, code_scheme):
    """Convert to HBF properties."""
    # set codepoints
    font = font.label(codepoint_from=font.encoding)
    # get ranges
    cps, cranges, b2ranges, b3ranges = _get_code_ranges(font)
    font = font.subset(cps)
    # check if the remaining glyphs mae for a cell font
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'Only character-cell fonts can be stored in HBF format.'
        )
    # bring font to padded, equalised normal form
    # then extract common bearings
    font = font.equalise_horizontal()
    padding = font.padding
    font = font.crop(*padding)
    # convert properties
    xlfd_props = create_xlfd_properties(font)
    if 'hbf.font' in font.get_properties():
        fontname = font.get_property('hbf.font')
        xlfd_props.pop('HBF.FONT')
    else:
        fontname = create_xlfd_name(xlfd_props)
    bbx = (
        f'{font.raster_size.x} {font.raster_size.y} '
        f'{padding.left} {padding.bottom}'
    )
    font_bbx = (
        f'{font.raster_size.x+padding.right} {font.raster_size.y+padding.top} '
        f'{padding.left} {padding.bottom}'
    )
    code_scheme = font.encoding
    props = [
        ('HBF_START_FONT', '1.1'),
        ('HBF_CODE_SCHEME', code_scheme),
    ] + [
        ('COMMENT', _comment) for _comment in font.get_comment().splitlines()
    ] + [
        ('FONT', fontname),
        ('SIZE', f'{font.point_size} {font.dpi.x} {font.dpi.y}'),
        ('HBF_BITMAP_BOUNDING_BOX', bbx),
        ('FONTBOUNDINGBOX', font_bbx),
    ]
    if xlfd_props:
        props.append(('STARTPROPERTIES', str(len(xlfd_props))))
        props.extend(xlfd_props.items())
        props.append(('ENDPROPERTIES', ''))
    props.append(('CHARS', f'{len(font.glyphs)}'))
    # byte-2 ranges
    props.append(('HBF_START_BYTE_2_RANGES', str(len(b2ranges))))
    for b2range in b2ranges:
        props.append(_format_byte_range(b2range, 2))
    props.append(('HBF_END_BYTE_2_RANGES', ''))
    # byte-3 ranges
    if b3ranges:
        props.append(('HBF_START_BYTE_3_RANGES', str(len(b3ranges))))
        for b3range in b3ranges:
            props.append(_format_byte_range(b3range, 3))
        props.append(('HBF_END_BYTE_3_RANGES', ''))
    # code ranges
    props.append(('HBF_START_CODE_RANGES', str(len(cranges))))
    # create glyph bitmaps, one code range at a time
    bitmaps = []
    offset = 0
    n_bytes = len(cps[-1])
    for crange in cranges:
        bitmap = b''.join(
            font.get_glyph(codepoint=_cp).as_bytes()
            for _cp in indexer(None, crange, b2ranges, b3ranges)
        )
        start = f'{crange.start:X}'.zfill(2*n_bytes)
        end = f'{crange.stop-1:X}'.zfill(2*n_bytes)
        props.append((
            'HBF_CODE_RANGE',
            f'0x{start}-0x{end} {bitmap_name} {offset}'
        ))
        bitmaps.append(bitmap)
        offset += len(bitmap)
    props.append(('HBF_END_CODE_RANGES', ''))
    return props, bitmaps


def _format_byte_range(brange, n_byte):
    return (
        f'HBF_BYTE_{n_byte}_RANGE',
        f'{brange.start:#02X}-{brange.stop-1:#02X}'
    )


def _get_code_ranges(font):
    """Determine contiguous ranges."""
    cps = font.get_codepoints()
    if not cps:
        raise FileFormatError('No storable glyphs in font.')
    n_bytes = len(max(cps))
    if n_bytes not in (2, 3):
        raise FileFormatError('HBF can only store 2- or 3-byte code ranges.')
    # only store full-length codepoints and store in order
    cps = sorted(_cp for _cp in cps if len(_cp) == n_bytes)
    # determine byte-2 ranges
    b2 = sorted(set(_cp[1] for _cp in cps))
    b2ranges = _find_ranges(b2)
    logging.debug('BYTE_2_RANGES %s', b2ranges)
    # determine byte-3 ranges
    if n_bytes == 3:
        b3 = sorted(set(_cp[2] for _cp in cps))
        b3ranges = _find_ranges(b3)
        logging.debug('BYTE_3_RANGES %s', b3ranges)
    else:
        b3ranges = ()
    # determine code ranges subject to byte-2, byte-3 ranges already found
    start_crange = range(int(cps[0]), int(cps[-1])+1)
    gen = indexer(None, start_crange, b2ranges, b3ranges)
    cranges = _find_ranges(cps, gen)
    logging.debug('CODE_RANGES %s', cranges)
    return cps, cranges, b2ranges, b3ranges


def _find_ranges(cps, indexgen=None):
    """Find code range subject to indexer."""
    cur_start = int(cps[0])
    cur_end = cur_start
    if not indexgen:
        indexgen = iter(range(cur_start, int(cps[-1])+1))
    index = next(indexgen)
    ranges = []
    try:
        for cp in cps[1:]:
            cp = int(cp)
            if cp <= index:
                continue
            # cp > index, get next index which is higher than previous.
            # so now cp can be less, equal or higher
            index = next(indexgen)
            if cp == index:
                cur_end = cp
            else:
                ranges.append(range(cur_start, cur_end + 1))
                cur_start, cur_end = cp, cp
                while cp > index:
                    index = next(indexgen)
    except StopIteration:
        logging.debug('Indexer was exhausted')
    ranges.append(range(cur_start, cur_end + 1))
    return ranges
