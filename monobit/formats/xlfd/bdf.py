"""
monobit.formats.xlfd.bdf - Adobe Glyph Bitmap Distribution Format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...binary import int_to_bytes, bytes_to_int, ceildiv
from ...storage import loaders, savers
from ...magic import FileFormatError
from ...font import Font, Coord
from ...glyph import Glyph
from ...encoding import charmaps, NotFoundError
from ...taggers import tagmaps
from ...labels import Char

from .xlfd import _parse_xlfd_properties, _create_xlfd_properties
from .xlfd import _create_xlfd_name


@loaders.register(
    name='bdf',
    magic=(b'STARTFONT ',),
    patterns=('*.bdf',),
)
def load_bdf(instream):
    """
    Load font from Adobe Glyph Bitmap Distribution Format (BDF) file.
    """
    instream = instream.text
    comments, bdf_props, x_props = _read_bdf_global(instream)
    logging.info('bdf properties:')
    for name, value in bdf_props.items():
        logging.info('    %s: %s', name, value)
    logging.info('x properties:')
    for name, value in x_props.items():
        logging.info('    %s: %s', name, value)
    glyphs, glyph_props = _read_bdf_glyphs(instream)
    glyphs, properties = _parse_properties(glyphs, glyph_props, bdf_props, x_props)
    font = Font(glyphs, comment=comments, **properties)
    try:
        font = font.label()
    except NotFoundError:
        pass
    return font


@savers.register(linked=load_bdf)
def save_bdf(fonts, outstream):
    """
    Save font to Adobe Glyph Bitmap Distribution Format (BDF) file.
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to BDF file.')
    # ensure codepoint values are set
    font = fonts[0]
    try:
        font = font.label(codepoint_from=font.encoding)
    except NotFoundError:
        pass
    _save_bdf(font, outstream.text)


##############################################################################
# BDF reader
# BDF specification: https://adobe-type-tools.github.io/font-tech-notes/pdfs/5005.BDF_Spec.pdf


def read_props(instream, ends, keep_end=False):
    """Read key-value properties with comments."""
    # read global section
    props = []
    comments = []
    keyword = ''
    for line in instream:
        line = line.strip()
        if not line:
            continue
        if line.startswith('COMMENT'):
            comments.append(line[8:])
            continue
        keyword, _, value = line.partition(' ')
        props.append((keyword, value))
        if keyword in ends:
            if not keep_end:
                del props[-1]
            break
        else:
            keyword = ''
    return props, comments, keyword


def _read_bdf_glyphs(instream):
    """Read character section."""
    # output
    glyphs = []
    glyph_meta = []
    for line in instream:
        line = line.rstrip('\r\n')
        if not line:
            continue
        if line.startswith('ENDFONT'):
            break
        elif not line.startswith('STARTCHAR'):
            raise FileFormatError(f'Expected STARTCHAR, not {line}')
        keyword, values = line.split(' ', 1)
        meta, comments, _ = read_props(instream, ends=('BITMAP',))
        meta = dict(meta)
        meta[keyword] = values
        # store labels, if they're not just ordinals
        label = meta['STARTCHAR']
        width, height, _, _ = _bdf_ints(meta['BBX'])
        # convert from hex-string to list of bools
        # remove trailing zeros on each hex line
        hexstr = ''.join(
            instream.readline().strip()[:ceildiv(width, 8)*2]
            for _ in range(height)
        )
        try:
            glyph = Glyph.from_hex(hexstr, width, height, comment='\n'.join(comments))
        except ValueError as e:
            logging.warning(f'Could not read glyph `{label}` {hexstr}: {e}')
        else:
            try:
                int(label)
            except ValueError:
                glyph = glyph.modify(tag=label)
            # ENCODING must be single integer or -1 followed by integer
            *_, encvalue = _bdf_ints(meta['ENCODING'])
            glyph = glyph.modify(encvalue=encvalue)
            glyphs.append(glyph)
            glyph_meta.append(meta)
        line = instream.readline()
        if not line.startswith('ENDCHAR'):
            raise FileFormatError(f'Expected ENDCHAR, not {line}')
    return glyphs, glyph_meta


def _read_bdf_global(instream):
    """Read global section of BDF file."""
    start_props, start_comments, end = read_props(instream, ends=('STARTPROPERTIES', 'CHARS'), keep_end=True)
    x_props, x_comments = {}, {}
    end_props, end_comments = {}, {}
    if end != 'CHARS':
        del start_props[-1]
        x_props, x_comments, end = read_props(instream, ends=('CHARS', 'ENDPROPERTIES'), keep_end=True)
        if end != 'CHARS':
            del x_props[-1]
            end_props, end_comments, _ = read_props(instream, ends=('CHARS',), keep_end=True)
    bdf_props = {**dict(start_props), **dict(end_props)}
    comments = [*start_comments, *x_comments, *end_comments]
    return '\n'.join(comments), bdf_props, dict(x_props)


##############################################################################
# converter

def _bdf_ints(instr):
    return (int(_p) for _p in instr.split())


def _parse_properties(glyphs, glyph_props, bdf_props, x_props):
    """Parse metrics and metadata."""
    # parse meaningful metadata
    known, global_metrics, bdf_unparsed = _extract_known_bdf_properties(bdf_props)
    if known['NCHARS'] != len(glyphs):
        logging.warning('Number of characters found does not match CHARS declaration.')
    properties = _convert_bdf_properties(known)
    glyphs = _convert_glyph_properties(glyphs, global_metrics, glyph_props)
    xlfd_props = _parse_xlfd_properties(x_props, known['FONT'])
    for key, value in bdf_unparsed.items():
        logging.info(f'Unrecognised BDF property {key}={value}')
        # preserve as property
        properties[key] = value
    for key, value in xlfd_props.items():
        if key in properties and properties[key] != value:
            logging.debug(
                'Inconsistency between BDF and XLFD properties: '
                '%s=%s (from XLFD) but %s=%s (from BDF). Taking BDF property.',
                key, value, key, properties[key]
            )
        else:
            properties[key] = value
    # store labels as char if we're working in unicode, codepoint otherwise
    if not charmaps.is_unicode(properties.get('encoding', '')):
        glyphs = [
            _glyph.modify(codepoint=_glyph.encvalue).drop('encvalue')
            if _glyph.encvalue != -1 else _glyph.drop('encvalue')
            for _glyph in glyphs
        ]
    else:
        glyphs = [
            _glyph.modify(char=chr(_glyph.encvalue)).drop('encvalue')
            if _glyph.encvalue != -1 else _glyph.drop('encvalue')
            for _glyph in glyphs
        ]
    return glyphs, properties


def _extract_known_bdf_properties(bdf_props):
    """Extract and classify global BDF properties that we know and use."""
    known = dict(
        SIZE=tuple(_bdf_ints(bdf_props.pop('SIZE'))),
        STARTFONT=bdf_props.pop('STARTFONT'),
        CONTENTVERSION=bdf_props.pop('CONTENTVERSION', None),
        NCHARS=int(bdf_props.pop('CHARS')),
        FONT=bdf_props.pop('FONT'),
    )
    metricsset = int(bdf_props.pop('METRICSSET', '0'))
    if metricsset not in (0, 1, 2):
        logging.warning(f'Unsupported value METRICSSET={metricsset} ignored')
        metricsset = 0
    # we're not type converting global metrics except METRICSSET
    # because we still need to override with (unconverted) glyph metrics
    global_metrics = dict(
        METRICSSET=metricsset,
        # global DWIDTH; use bounding box as fallback if not specified
        DWIDTH=bdf_props.pop('DWIDTH', ' '.join(bdf_props['FONTBOUNDINGBOX'].split()[:2])),
        SWIDTH=bdf_props.pop('SWIDTH', '0 0'),
        VVECTOR=bdf_props.pop('VVECTOR', '0 0'),
        DWIDTH1=bdf_props.pop('DWIDTH1', '0 0'),
        SWIDTH1=bdf_props.pop('SWIDTH1', '0 0'),
        BBX=bdf_props.pop('FONTBOUNDINGBOX'),
    )
    # keep unparsed bdf props
    return known, global_metrics, bdf_props


def _convert_bdf_properties(bdf_props):
    """Convert BDF global properties."""
    size, xdpi, ydpi, *depth_info = bdf_props['SIZE']
    if depth_info and depth_info[0] != 1:
        # Microsoft greymap extension of BDF, FontForge "BDF 2.3"
        # https://fontforge.org/docs/techref/BDFGrey.html
        raise FileFormatError('Greymap BDF not supported.')
    properties = {
        'source_format': 'BDF v{}'.format(bdf_props['STARTFONT']),
        'point_size': size,
        'dpi': (xdpi, ydpi),
        'revision': bdf_props['CONTENTVERSION'],
    }
    return properties


def _convert_glyph_properties(glyphs, global_metrics, glyph_props):
    """Convert glyph properties."""
    mod_glyphs = []
    for glyph, props in zip(glyphs, glyph_props):
        # fall back to glabal metrics, if not defined per-glyph
        props = global_metrics | props
        new_props = {}
        if global_metrics['METRICSSET'] in (0, 2):
            new_props.update(_convert_horiz_metrics(glyph.width, props))
        if global_metrics['METRICSSET'] in (1, 2):
            new_props.update(_convert_vert_metrics(glyph.height, props))
        mod_glyphs.append(glyph.modify(**new_props))
    return mod_glyphs


def _convert_horiz_metrics(glyph_width, props):
    """Convert glyph horizontal metrics."""
    new_props = {}
    # bounding box & offset
    _bbx_width, _bbx_height, bboffx, shift_up = _bdf_ints(props['BBX'])
    new_props['shift_up'] = shift_up
    # advance width
    dwidth_x, dwidth_y = _bdf_ints(props['DWIDTH'])
    if dwidth_y:
        raise FileFormatError('Vertical advance in horizontal writing not supported.')
    if dwidth_x > 0:
        advance_width = dwidth_x
        left_bearing = bboffx
    else:
        advance_width = -dwidth_x
        # bboffx would likely be negative
        left_bearing = advance_width + bboffx
    new_props['left_bearing'] = left_bearing
    new_props['right_bearing'] = advance_width - glyph_width - left_bearing
    return new_props


def _convert_vert_metrics(glyph_height, props):
    """Convert glyph vertical metrics."""
    new_props = {}
    # bounding box & offset
    bbx_width, _bbx_height, bboffx, bboffy = _bdf_ints(props['BBX'])
    voffx, voffy = _bdf_ints(props['VVECTOR'])
    to_bottom = bboffy - voffy
    # vector from baseline to raster left; negative: baseline to right of left raster edge
    to_left = bboffx - voffx
    # leftward shift from baseline to raster central axis
    new_props['shift_left'] = ceildiv(bbx_width, 2) + to_left
    # advance height
    dwidth1_x, dwidth1_y = _bdf_ints(props['DWIDTH1'])
    if dwidth1_x:
        raise FileFormatError('Horizontal advance in vertical writing not supported.')
    # dwidth1 vector: negative is down
    if dwidth1_y < 0:
        advance_height = -dwidth1_y
        top_bearing = -to_bottom - glyph_height
        bottom_bearing = advance_height - glyph_height - top_bearing
    else:
        advance_height = dwidth1_y
        bottom_bearing = to_bottom
        top_bearing = advance_height - glyph_height - bottom_bearing
    new_props['top_bearing'] = top_bearing
    new_props['bottom_bearing'] = bottom_bearing
    return new_props


def swidth_to_pixel(swidth, point_size, dpi):
    """DWIDTH = SWIDTH * points/1000 * dpi / 72"""
    return swidth * (point_size / 1000) * (dpi / 72)


##############################################################################
# BDF writer

def pixel_to_swidth(dwidth, point_size, dpi):
    """SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )"""
    return int(
        round(dwidth / (point_size / 1000) / (dpi / 72))
    )


def _save_bdf(font, outstream):
    """Write one font to X11 BDF 2.1."""
    # property table
    xlfd_props = _create_xlfd_properties(font)
    bdf_props = [
        ('STARTFONT', '2.1'),
    ] + [
        ('COMMENT', _comment) for _comment in font.get_comment().splitlines()
    ] + [
        ('FONT', _create_xlfd_name(xlfd_props)),
        ('SIZE', f'{font.point_size} {font.dpi.x} {font.dpi.y}'),
        (
            # per the example in the BDF spec,
            # the first two coordinates in FONTBOUNDINGBOX
            # are the font's ink-bounds
            'FONTBOUNDINGBOX', (
                f'{font.bounding_box.x} {font.bounding_box.y} '
                f'{font.ink_bounds.left} {font.ink_bounds.bottom}'
            )
        )
    ]
    vertical_metrics = ('shift_left', 'top_bearing', 'bottom_bearing')
    has_vertical_metrics = any(
        _k in _g.get_properties()
        for _g in font.glyphs
        for _k in vertical_metrics
    )
    if has_vertical_metrics:
        bdf_props.append(('METRICSSET', '2'))
    # minimize glyphs to ink-bounds (BBX) before storing, except "cell" fonts
    if font.spacing not in ('character-cell', 'multi-cell'):
        font = font.reduce()
    # labels
    # get glyphs for encoding values
    encoded_glyphs = []
    for glyph in font.glyphs:
        if charmaps.is_unicode(font.encoding):
            if len(glyph.codepoint) == 1:
                encoding, = glyph.codepoint
            else:
                # multi-codepoint grapheme cluster or not set
                # -1 means no encoding value in bdf
                encoding = -1
        elif glyph.codepoint:
            # encoding values above 256 become multi-byte
            # unless we're working in unicode
            encoding = bytes_to_int(glyph.codepoint)
        else:
            encoding = -1
        # char must have a name in bdf
        # keep the first tag as the glyph name if available
        if glyph.tags:
            name = glyph.tags[0]
        else:
            # look up in adobe glyph list if character available
            name = tagmaps['adobe'].tag(*glyph.get_labels()).value
            # otherwise, use encoding value if available
            if not name and encoding != -1:
                name = f'char{encoding:02X}'
            if not name:
                logging.warning(
                    f'Multi-codepoint glyph {glyph.codepoint}'
                    "can't be stored as no name or character available."
                )
        encoded_glyphs.append((encoding, name, glyph))
    glyphs = []
    for encoding, name, glyph in encoded_glyphs:
        swidth_y, dwidth_y = 0, 0
        # SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )
        # DWIDTH specifies the widths in x and y, dwx0 and dwy0, in device pixels.
        # Like SWIDTH , this width information is a vector indicating the position of
        # the next glyph’s origin relative to the origin of this glyph.
        dwidth_x = glyph.advance_width
        swidth_x = pixel_to_swidth(dwidth_x, font.point_size, font.dpi.x)
        glyphdata = [
            ('STARTCHAR', name),
            ('ENCODING', str(encoding)),
            # "The SWIDTH y value should always be zero for a standard X font."
            # "The DWIDTH y value should always be zero for a standard X font."
            ('SWIDTH', f'{swidth_x} 0'),
            ('DWIDTH', f'{dwidth_x} 0'),
            ('BBX', (
                f'{glyph.width} {glyph.height} '
                f'{glyph.left_bearing} {glyph.shift_up}'
            )),
        ]
        if has_vertical_metrics:
            to_left = glyph.shift_left - ceildiv(glyph.width, 2)
            to_bottom = -glyph.top_bearing - glyph.height
            voffx = glyph.left_bearing - to_left
            voffy = glyph.shift_up - to_bottom
            # dwidth1 vector: negative is down
            dwidth1_y = -glyph.advance_height
            swidth1_y = pixel_to_swidth(dwidth1_y, font.point_size, font.dpi.y)
            glyphdata.extend([
                ('VVECTOR', f'{voffx} {voffy}'),
                ('SWIDTH1', f'0 {swidth1_y}'),
                ('DWIDTH1', f'0 {dwidth1_y}'),
            ])
        # bitmap
        if not glyph.height:
            glyphdata.append(('BITMAP', ''))
        else:
            hex = glyph.as_hex().upper()
            width = len(hex) // glyph.height
            split_hex = [
                hex[_offs:_offs+width]
                for _offs in range(0, len(hex), width)
            ]
            glyphdata.append(('BITMAP', '\n' + '\n'.join(split_hex)))
        glyphs.append(glyphdata)
    # write out
    for key, value in bdf_props:
        if value:
            outstream.write(f'{key} {value}\n')
    if xlfd_props:
        outstream.write(f'STARTPROPERTIES {len(xlfd_props)}\n')
        for key, value in xlfd_props.items():
            outstream.write(f'{key} {value}\n')
        outstream.write('ENDPROPERTIES\n')
    outstream.write(f'CHARS {len(glyphs)}\n')
    for glyph in glyphs:
        for key, value in glyph:
            outstream.write(f'{key} {value}\n')
        outstream.write('ENDCHAR\n')
    outstream.write('ENDFONT\n')
