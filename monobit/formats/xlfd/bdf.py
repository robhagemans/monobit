"""
monobit.formats.xlfd.bdf - Adobe Glyph Bitmap Distribution Format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...binary import ceildiv
from ...storage import loaders, savers
from ...magic import FileFormatError
from ...font import Font, Coord
from ...raster import Raster
from ...glyph import Glyph
from ...encoding import charmaps, NotFoundError
from ...taggers import tagmaps
from ...labels import Char, Codepoint, Tag

from .xlfd import parse_xlfd_properties, create_xlfd_properties
from .xlfd import create_xlfd_name, CUSTOM_PROP


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
    bdf_glyphs = _read_bdf_glyphs(instream)
    glyphs, properties = _convert_from_bdf(bdf_glyphs, bdf_props, x_props)
    font = Font(glyphs, comment=comments, **properties)
    # create char labels, if encoding recognised
    font = font.label()
    # store labels as char only if we're working in unicode
    if charmaps.is_unicode(font.encoding):
        font = font.label(codepoint_from=None)
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
    bdf_glyphs = []
    for line in instream:
        line = line.rstrip()
        if not line:
            continue
        if line.startswith('ENDFONT'):
            break
        keyword, _, tag = line.partition(' ')
        if keyword != 'STARTCHAR':
            raise FileFormatError(f'Expected STARTCHAR, not {line}')
        glyph_props = {'STARTCHAR': tag}
        proplist, comments, _ = read_props(instream, ends=('BITMAP',))
        propdict = dict(proplist)
        glyph_props |= dict(
            DWIDTH=_bdf_ints(propdict.pop('DWIDTH', None)),
            SWIDTH=_bdf_ints(propdict.pop('SWIDTH', None)),
            VVECTOR=_bdf_ints(propdict.pop('VVECTOR', None)),
            DWIDTH1=_bdf_ints(propdict.pop('DWIDTH1', None)),
            SWIDTH1=_bdf_ints(propdict.pop('SWIDTH1', None)),
            BBX=_bdf_ints(propdict.pop('BBX', None)),
        )
        glyph_props |= propdict
        glyph_props['COMMENT'] = '\n'.join(comments)
        glyph_props = {_k: _v for _k, _v in glyph_props.items() if _v is not None}
        # convert from hex-string to raster
        width, height, _, _ = glyph_props['BBX']
        hexstr = ''.join(
            # remove excess bytes on each hex line
            instream.readline().strip()[:ceildiv(width, 8)*2]
            for _ in range(height)
        )
        try:
            raster = Raster.from_hex(hexstr, width, height)
        except ValueError as e:
            logging.warning(f'Could not read glyph `{tag}` {hexstr}: {e}')
        else:
            bdf_glyphs.append(glyph_props | {'raster': raster})
        line = instream.readline()
        if not line.startswith('ENDCHAR'):
            raise FileFormatError(f'Expected ENDCHAR, not {line}')
    return bdf_glyphs


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
    if instr is not None:
        return tuple(int(_p) for _p in instr.split())
    return None


def _convert_from_bdf(bdf_glyphs, bdf_props, x_props):
    """Convert BDF data to monobit glyphs and properties."""
    # parse meaningful metadata
    known, global_metrics, bdf_unparsed = _extract_known_bdf_properties(bdf_props)
    properties = _convert_bdf_properties(known)
    glyphs = _convert_bdf_glyphs(bdf_glyphs, global_metrics, known)
    xlfd_props = parse_xlfd_properties(x_props, known['FONT'])
    # consistency checks
    if known['NCHARS'] != len(bdf_glyphs):
        logging.warning('Number of characters found does not match CHARS declaration.')
    for key, value in bdf_unparsed.items():
        logging.warning(f'Unrecognised BDF property {key}={value}')
        # preserve as custom property namespace, avoid clashes with yaff props
        properties[f'{CUSTOM_PROP}.{key}'] = value
    for key, value in xlfd_props.items():
        if key in properties and properties[key] != value:
            logging.debug(
                'Inconsistency between BDF and XLFD properties: '
                '%s=%s (from XLFD) but %s=%s (from BDF). Taking BDF property.',
                key, value, key, properties[key]
            )
        else:
            properties[key] = value
    return glyphs, properties


def _extract_known_bdf_properties(bdf_props):
    """Extract and classify global BDF properties that we know and use."""
    known = dict(
        SIZE=_bdf_ints(bdf_props.pop('SIZE')),
        STARTFONT=bdf_props.pop('STARTFONT'),
        CONTENTVERSION=bdf_props.pop('CONTENTVERSION', None),
        NCHARS=int(bdf_props.pop('CHARS')),
        FONT=bdf_props.pop('FONT'),
        METRICSSET=int(bdf_props.pop('METRICSSET', '0')),
    )
    # we're not type converting global metrics
    # because we still need to override with (unconverted) glyph metrics
    global_metrics = dict(
        # global DWIDTH; use bounding box as fallback if not specified
        DWIDTH=_bdf_ints(
            bdf_props.pop(
                'DWIDTH', ' '.join(bdf_props['FONTBOUNDINGBOX'].split()[:2])
            )
        ),
        SWIDTH=_bdf_ints(bdf_props.pop('SWIDTH', '0 0')),
        VVECTOR=_bdf_ints(bdf_props.pop('VVECTOR', '0 0')),
        DWIDTH1=_bdf_ints(bdf_props.pop('DWIDTH1', '0 0')),
        SWIDTH1=_bdf_ints(bdf_props.pop('SWIDTH1', '0 0')),
        BBX=_bdf_ints(bdf_props.pop('FONTBOUNDINGBOX')),
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
        'source_format': f"BDF v{bdf_props['STARTFONT']}",
        'point_size': size,
        'dpi': (xdpi, ydpi),
        'revision': bdf_props['CONTENTVERSION'],
    }
    return properties


def _convert_bdf_labels(props):
    """Convert BDF glyph tags and encoding values to monobit labels."""
    labels = []
    # store STARTCHAR labels, if they're not just ordinals
    tag = props['STARTCHAR']
    try:
        int(tag)
    except ValueError:
        labels.append(Tag(tag))
    # ENCODING must be single integer or -1 followed by integer
    *_, encvalue = _bdf_ints(props['ENCODING'])
    if encvalue >= 0:
        labels.append(Codepoint(encvalue))
    return labels


def _convert_bdf_glyphs(bdf_glyphs, global_metrics, bdf_props):
    """Convert glyph properties."""
    if bdf_props['METRICSSET'] not in (0, 1, 2):
        logging.warning(
            f"Unsupported value METRICSSET={bdf_props['METRICSSET']} ignored"
        )
    glyphs = []
    for props in bdf_glyphs:
        raster = props.pop('raster')
        # fall back to glabal metrics, if not defined per-glyph
        props = global_metrics | props
        new_props = {}
        if bdf_props['METRICSSET'] != 1:
            new_props.update(_convert_horiz_metrics(raster.width, props, bdf_props))
        if bdf_props['METRICSSET'] in (1, 2):
            new_props.update(_convert_vert_metrics(raster.height, props, bdf_props))
        labels = _convert_bdf_labels(props)
        glyphs.append(Glyph(
            raster, labels=labels, comment=props['COMMENT'], **new_props
        ))
    return glyphs


def _convert_horiz_metrics(glyph_width, props, bdf_props):
    """Convert glyph horizontal metrics."""
    new_props = {}
    # bounding box & offset
    _bbx_width, _bbx_height, bboffx, shift_up = props['BBX']
    new_props['shift_up'] = shift_up
    # advance width
    dwidth_x, dwidth_y = props['DWIDTH']
    if dwidth_x > 0:
        advance_width = dwidth_x
        left_bearing = bboffx
    else:
        advance_width = -dwidth_x
        # bboffx would likely be negative
        left_bearing = advance_width + bboffx
    new_props['left_bearing'] = left_bearing
    new_props['right_bearing'] = advance_width - glyph_width - left_bearing
    # scalable width
    swidth_x, swidth_y = props['SWIDTH']
    new_props['scalable_width'] = swidth_to_pixel(
        swidth_x, point_size=bdf_props['SIZE'][0], dpi=bdf_props['SIZE'][1]
    )
    if new_props['scalable_width'] == advance_width:
        new_props['scalable_width'] = None
    if dwidth_y or swidth_y:
        logging.warning(
            'Vertical advance in horizontal writing not supported; ignored'
        )
    return new_props


def _convert_vert_metrics(glyph_height, props, bdf_props):
    """Convert glyph vertical metrics."""
    new_props = {}
    # bounding box & offset
    bbx_width, _bbx_height, bboffx, bboffy = props['BBX']
    voffx, voffy = props['VVECTOR']
    to_bottom = bboffy - voffy
    # vector from baseline to raster left; negative: baseline to right of left raster edge
    to_left = bboffx - voffx
    # leftward shift from baseline to raster central axis
    new_props['shift_left'] = ceildiv(bbx_width, 2) + to_left
    # advance height
    dwidth1_x, dwidth1_y = props['DWIDTH1']
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
    swidth1_x, swidth1_y = props['SWIDTH1']
    new_props['scalable_height'] = swidth_to_pixel(
        swidth1_y, point_size=bdf_props['SIZE'][0], dpi=bdf_props['SIZE'][2]
    )
    if new_props['scalable_height'] == advance_height:
        new_props['scalable_height'] = None
    if dwidth1_x or swidth1_x:
        logging.warning(
            'Horizontal advance in vertical writing not supported; ignored'
        )
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
    xlfd_props = create_xlfd_properties(font)
    xlfd_name = create_xlfd_name(xlfd_props)
    bdf_props = _convert_to_bdf_properties(font, xlfd_name)
    # minimize glyphs to ink-bounds (BBX) before storing, except "cell" fonts
    if font.spacing not in ('character-cell', 'multi-cell'):
        font = font.reduce()
    # ensure character labels exist if needed
    if charmaps.is_unicode(font.encoding):
        font = font.label(match_whitespace=False, match_graphical=False)
    glyphs = tuple(
        _convert_to_bdf_glyph(glyph, font)
        for glyph in font.glyphs
    )
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


def _convert_to_bdf_properties(font, xlfd_name):
    bdf_props = [
        ('STARTFONT', '2.1'),
    ] + [
        ('COMMENT', _comment) for _comment in font.get_comment().splitlines()
    ] + [
        ('FONT', xlfd_name),
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
    if font.has_vertical_metrics():
        bdf_props.append(('METRICSSET', '2'))
    return bdf_props


def _get_glyph_encvalue(glyph, is_unicode):
    """Get BDF ENCODING value and STARTCHAR tag."""
    if is_unicode:
        if len(glyph.char) == 1:
            encoding = ord(glyph.char)
        else:
            # multi-codepoint grapheme cluster or not set
            # -1 means no encoding value in bdf
            encoding = -1
    elif glyph.codepoint:
        # encoding values above 256 become multi-byte
        # unless we're working in unicode
        encoding = int(glyph.codepoint)
    else:
        encoding = -1
    # char must have a name in bdf
    for tag in glyph.tags:
        # bdf must only include printable ascii
        # postscript names (AGL) are purely alphanumeric
        # keep the first alphanumeric tag as the glyph name if available
        try:
            name = tag.value.encode('ascii').decode()
            if all(_c.isalnum() for _c in name):
                break
        except UnicodeError:
            pass
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
    return encoding, name


def _convert_to_bdf_glyph(glyph, font):
    encoding, name = _get_glyph_encvalue(
        glyph, charmaps.is_unicode(font.encoding)
    )
    swidth_y, dwidth_y = 0, 0
    # SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )
    # DWIDTH specifies the widths in x and y, dwx0 and dwy0, in device pixels.
    # Like SWIDTH , this width information is a vector indicating the position of
    # the next glyph’s origin relative to the origin of this glyph.
    dwidth_x = glyph.advance_width
    swidth_x = pixel_to_swidth(
        glyph.scalable_width, font.point_size, font.dpi.x
    )
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
    if font.has_vertical_metrics():
        to_left = glyph.shift_left - ceildiv(glyph.width, 2)
        to_bottom = -glyph.top_bearing - glyph.height
        voffx = glyph.left_bearing - to_left
        voffy = glyph.shift_up - to_bottom
        # dwidth1 vector: negative is down
        dwidth1_y = -glyph.advance_height
        swidth1_y = pixel_to_swidth(
            -glyph.scalable_height, font.point_size, font.dpi.y
        )
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
    return glyphdata
