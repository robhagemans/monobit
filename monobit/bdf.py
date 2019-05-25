"""
monobit.bdf - read and write .bdf files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .typeface import Typeface
from .font import Font
from .glyph import Glyph


# BDF is specified as ASCII only
# but the XLFD atoms are specified as iso8859-1, so this seems the best choice

@Typeface.loads('bdf', name='BDF', encoding='iso8859-1')
def load(instream):
    """Load font from a .bdf file."""
    nchars, comments, bdf_props, x_props = _read_bdf_global(instream)
    glyphs, glyph_props, labels = _read_bdf_characters(instream)
    # check number of characters, but don't break if no match
    if nchars != len(glyphs):
        logging.warning('Possibly corrupted BDF file: number of characters found does not match CHARS declaration.')
    glyphs, properties = _parse_properties(glyphs, glyph_props, bdf_props, x_props, instream.name)
    return Typeface([Font(glyphs, labels, comments=comments, properties=properties)])


def _read_dict(instream, until=None):
    """Read key-value pairs."""
    result = {}
    for line in instream:
        if not line:
            continue
        if ' ' not in line:
            break
        keyword, values = line[:-1].split(' ', 1)
        result[keyword] = values.strip()
        if keyword == until:
            break
    return result

def _read_bdf_characters(instream):
    """Read character section."""
    # output
    glyphs = []
    labels = {}
    glyph_meta = []
    for line in instream:
        line = line.rstrip('\r\n')
        if not line:
            continue
        if line.startswith('ENDFONT'):
            break
        elif not line.startswith('STARTCHAR'):
            raise ValueError('Expected STARTCHAR')
        keyword, values = line.split(' ', 1)
        meta = _read_dict(instream, until='BITMAP')
        meta[keyword] = values
        width, height, _, _ = meta['BBX'].split(' ')
        width, height = int(width), int(height)
        # convert from hex-string to list of bools
        hexstr = ''.join(instream.readline().strip() for _ in range(height))
        glyph = Glyph.from_hex(hexstr, width, height)
        # store labels, if they're not just ordinals
        try:
            int(meta['STARTCHAR'])
        except ValueError:
            labels[meta['STARTCHAR']] = len(glyphs)
        # ENCODING must be single integer or -1 followed by integer
        encvalue = int(meta['ENCODING'].split(' ')[-1])
        # no encoding number found
        if encvalue != -1:
            labels[encvalue] = len(glyphs)
        glyphs.append(glyph)
        glyph_meta.append(meta)
        if not instream.readline().startswith('ENDCHAR'):
            raise('Expected ENDCHAR')
    return glyphs, glyph_meta, labels

def _read_bdf_global(instream):
    """Read global section of BDF file."""
    # read global section
    bdf_props = {}
    x_props = {}
    comments = []
    parsing_x = False
    nchars = -1
    for line in instream:
        line = line.strip('\r\n')
        if not line:
            continue
        elif line.startswith('COMMENT'):
            comments.append(line[8:])
        elif line.startswith('STARTPROPERTIES'):
            parsing_x = True
        elif line.startswith('ENDPROPERTIES'):
            parsing_x = False
        else:
            keyword, values = line.split(' ', 1)
            values = values.strip()
            if keyword == 'CHARS':
                # value equals number of chars
                # this signals the end of the global section
                nchars = int(values)
                return nchars, comments, bdf_props, x_props
            elif parsing_x:
                x_props[keyword] = values
            else:
                # record all keywords in the same metadata table
                bdf_props[keyword] = values
    raise ValueError('No character information found in BDF file.')


##############################################################################
# properties

_SLANT_MAP = {
    'R': 'roman',
    'I': 'italic',
    'O': 'oblique',
    'RO': 'reverse-oblique',
    'RI': 'reverse-italic',
    'OT': '', # 'other'
}

_SPACING_MAP = {
    'P': 'proportional',
    'M': 'monospace',
    'C': 'cell',
}

_SETWIDTH_MAP = {
    '0': '', # Undefined or unknown
    '10': 'ultra-condensed',
    '20': 'extra-condensed',
    '30': 'condensed', # Condensed, Narrow, Compressed, ...
    '40': 'semi-condensed',
    '50': 'medium', # Medium, Normal, Regular, ...
    '60': 'semi-expanded', # SemiExpanded, DemiExpanded, ...
    '70': 'expanded',
    '80': 'extra-expanded', # ExtraExpanded, Wide, ...
    '90': 'ultra-expanded',
}

_WEIGHT_MAP = {
    '0': '', # Undefined or unknown
    '10': 'thin', # UltraLight
    '20': 'extra-light',
    '30': 'light',
    '40': 'semi-light', # SemiLight, Book, ...
    '50': 'medium', # Medium, Normal, Regular,...
    '60': 'semi-bold', # SemiBold, DemiBold, ...
    '70': 'bold',
    '80': 'extra-bold', #ExtraBold, Heavy, ...
    '90': 'heavy', #UltraBold, Black, ...,
}

def _parse_properties(glyphs, glyph_props, bdf_props, x_props, filename):
    """Parse metrics and metadata."""
    logging.info('bdf properties:')
    for name, value in bdf_props.items():
        logging.info('    %s: %s', name, value)
    logging.info('x properties:')
    for name, value in x_props.items():
        logging.info('    %s: %s', name, value)
    # parse meaningful metadata
    glyphs, properties, xlfd_name = _parse_bdf_properties(glyphs, glyph_props, bdf_props)
    xlfd_props = _parse_xlfd_properties(x_props, xlfd_name)
    for key, value in xlfd_props.items():
        if key in properties and properties[key] != value:
            logging.warning(
                'Inconsistency between BDF and XLFD properties: '
                '%s=%s (XLFD) but %s=%s (BDF). Taking BDF property.',
                key, value, key, properties[key]
            )
        else:
            properties[key] = value
    # check if default har exists, remove otherwise
    if 'default-char' in properties and not int(properties['default-char'], 0) in glyphs:
        # if the number doesn't occur, no default is set.
        del properties['default-char']
    return glyphs, properties


def _parse_bdf_properties(glyphs, glyph_props, bdf_props):
    """Parse BDF global and per-glyph geometry."""
    size, xdpi, ydpi = bdf_props.pop('SIZE').split(' ')
    properties = {
        'source-format': 'BDF v{}'.format(bdf_props.pop('STARTFONT')),
        'point-size': size,
        'dpi': ' '.join((xdpi, ydpi)) if xdpi != ydpi else xdpi,
    }
    try:
        properties['revision'] = bdf_props.pop('CONTENTVERSION')
    except KeyError:
        pass
    # global settings, tend to be overridden by per-glyph settings
    global_bbx = bdf_props.pop('FONTBOUNDINGBOX')
    # not supported: METRICSSET !=0, DWIDTH1, SWIDTH1
    # global DWIDTH; use bounding box as fallback if not specified
    global_dwidth = bdf_props.pop('DWIDTH', global_bbx[:2])
    global_swidth = bdf_props.pop('SWIDTH', 0)
    offsets_x = []
    offsets_y = []
    overshoots = []
    heights = []
    for glyph, props in zip(glyphs, glyph_props):
        props['BBX'] = props.get('BBX', global_bbx)
        props['DWIDTH'] = props.get('DWIDTH', global_dwidth)
        bbx_width, bbx_height, offset_x, offset_y = (int(_p) for _p in props['BBX'].split(' '))
        dwidth_x, dwidth_y = (int(_p) for _p in props['DWIDTH'].split(' '))
        try:
            # ignore SWIDTH, can be calculated - SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )
            swidth_x, swidth_y = (int(_x) for _x in props.get('SWIDTH', global_swidth).split(' '))
            #logging.info('x swidth: %s dwidth: %s', swidth_x*int(size)*int(xdpi) / 72000, dwidth_x)
            #logging.info('y swidth: %s dwidth: %s', swidth_y*int(size)*int(ydpi) / 72000, dwidth_y)
        except KeyError:
            pass
        offsets_x.append(offset_x)
        offsets_y.append(offset_y)
        overshoots.append((offset_x + bbx_width) - dwidth_x)
        heights.append(bbx_height + offset_y)
    leftmost = min(offsets_x)
    rightmost = max(overshoots)
    bottommost = min(offsets_y)
    topmost = max(heights)
    properties['offset-before'] = leftmost
    properties['offset-after'] = -rightmost
    properties['bottom'] = bottommost
    mod_glyphs = []
    for glyph, props in zip(glyphs, glyph_props):
        bbx_width, bbx_height, offset_x, offset_y = (int(_p) for _p in props['BBX'].split(' '))
        dwidth_x, dwidth_y = (int(_p) for _p in props['DWIDTH'].split(' '))
        overshoot = (offset_x + bbx_width) - dwidth_x
        padding_right = rightmost - overshoot
        padding_left = offset_x - leftmost
        padding_bottom = offset_y - bottommost
        padding_top = topmost - bbx_height - offset_y
        glyph = [
            (False,) * padding_left
            + _row[:bbx_width]
            + (False,) * padding_right
            for _row in glyph._rows[:bbx_height]
        ]
        matrix_width = padding_left + bbx_width + padding_right
        glyph = (
            [(False,) * matrix_width for _ in range(padding_top)]
            + glyph
            + [(False,) * matrix_width for _ in range(padding_bottom)]
        )
        mod_glyphs.append(Glyph(glyph))
    xlfd_name = bdf_props.pop('FONT')
    # keep unparsed bdf props
    properties.update({
        'bdf.' + _key: _value
        for _key, _value in bdf_props.items()
    })
    return mod_glyphs, properties, xlfd_name

def _parse_xlfd_name(xlfd_str):
    """Parse X logical font description font name string."""
    mapping = {
        'foundry': 1,
        'family': 2,
        'weight': 3,
        'slant': 4,
        'setwidth': 5,
        'style': 6,
        'pixel-size': 7,
        'point-size': 8,
        '_dpi-x': 9,
        '_dpi-y': 10,
        'spacing': 11,
        'average-width': 12,
        '_charset-registry': 13,
        '_charset-encoding': 14,
    }
    xlfd = xlfd_str.split('-')
    properties = {}
    if len(xlfd) >= 15:
        for key, index in mapping.items():
            if xlfd[index]:
                properties[key] = xlfd[index]
    else:
        logging.warning('Could not parse X font name string `%s`', xlfd_str)
        return {}
    return properties


def _parse_xlfd_properties(x_props, xlfd_name):
    """Parse X metadata."""
    xlfd_name_props = _parse_xlfd_name(xlfd_name)
    # we ignore AVERAGE_WIDTH, can be calculated
    mapping = {
        # rendering hints
        'FONT_ASCENT': 'ascent',
        'FONT_DESCENT': 'descent',
        'X_HEIGHT': 'x-height',
        'CAP_HEIGHT': 'cap-height',
        # display characteristics - already specified in bdf props
        'RESOLUTION_X': '_dpi-x',
        'RESOLUTION_Y': '_dpi-y',
        'RESOLUTION': 'dpi',
        'POINT_SIZE': 'point-size',
        # can be calculated: PIXEL_SIZE = ROUND((RESOLUTION_Y * POINT_SIZE) / 722.7)
        # description
        'FACE_NAME': 'name',
        'FULL_NAME': 'name',
        'FONT_VERSION': 'version',
        'COPYRIGHT': 'copyright',
        'NOTICE': 'notice',
        'FOUNDRY': 'foundry',
        'FAMILY_NAME': 'family',
        'WEIGHT_NAME': 'weight',
        'RELATIVE_WEIGHT': '_rel-weight',
        'SLANT': 'slant',
        'SPACING': 'spacing',
        'SETWIDTH_NAME': 'setwidth',
        'RELATIVE_SETWIDTH': '_rel-setwidth',
        'ADD_STYLE_NAME': 'style',
        'PIXEL_SIZE': 'pixel-size',
        'AVERAGE_WIDTH': 'average-width',
        # encoding
        'CHARSET_REGISTRY': '_charset-registry',
        'CHARSET_ENCODING': '_charset-encoding',
        'DEFAULT_CHAR': 'default-char',
    }
    properties = {}
    for xkey, key in mapping.items():
        try:
            value = x_props.pop(xkey).strip('"')
        except KeyError:
            value = xlfd_name_props.get(key, '')
        if value:
            properties[key] = value
    # modify/summarise values
    if 'descent' in properties:
        properties['descent'] = -int(properties['descent'])
    #if 'resolution-x' in properties and 'resolution-y' in properties:
    #    properties['dpi'] = '{} {}'.format(properties.pop('resolution-x'), properties.pop('resolution-y'))
    #elif 'resolution' in properties:
    #    properties['dpi'] = '{} {}'.format(properties['resolution'], properties['resolution'])
    if 'slant' in properties and properties['slant']:
        properties['slant'] = _SLANT_MAP[properties['slant']]
    if 'spacing' in properties and properties['spacing']:
        properties['spacing'] = _SPACING_MAP[properties['spacing']]
    # prefer the more precise relative weight and setwidth measures
    if '_rel-setwidth' in properties and properties['_rel-setwidth']:
        properties['setwidth'] = _SETWIDTH_MAP[properties.pop('_rel-setwidth')]
    if '_rel-weight' in properties and properties['_rel-weight']:
        properties['weight'] = _WEIGHT_MAP[properties.pop('_rel-weight')]
    if 'average-width' in properties:
        properties['average-width'] = int(properties['average-width']) / 10
    if '_dpi-x' in properties and '_dpi-y' in properties:
        xdpi, ydpi = properties.pop('_dpi-x'), properties.pop('_dpi-y')
        if 'dpi' in properties and not (properties['dpi'] == xdpi == ydpi):
            logging.warning(
                'Inconsistent XLFD dpi properties: dpi={} but dpi-x={} and dpi-y={}.',
                properties['dpi'], xdpi, ydpi
            )
        properties['dpi'] = ' '.join((xdpi, ydpi)) if xdpi != ydpi else xdpi
    # encoding
    try:
        registry = properties.pop('_charset-registry')
        encoding = properties.pop('_charset-encoding')
    except KeyError:
        pass
    else:
        properties['encoding'] = (registry + '-' + encoding).lower()
    try:
        properties['default-char'] = hex(int(properties['default-char']))
    except KeyError:
        pass
    for key in ('weight', 'slant', 'spacing', 'setwidth'):
        try:
            properties[key] = properties[key].lower()
        except KeyError:
            pass
    # keep unparsed properties
    if not xlfd_name_props:
        properties['bdf.FONT'] = xlfd_name
    properties.update({'xlfd.' + _k: _v.strip('"') for _k, _v in x_props.items()})
    return properties


# from:  Glyph Bitmap Distribution Format (BDF) Specification 2.2 (22 Mar 93)
#
# METRICSSET integer
# (Optional) The integer value of METRICSSET may be 0, 1, or 2, which corre-
# spond to writing direction 0 only, 1 only, or both (respectively). If not
# present, METRICSSET 0 is implied. If METRICSSET is 1, DWIDTH and
# SWIDTH keywords are optional.
#
# Note
# Version 2.1 of this document only allowed the metrics keywords SWIDTH and
# DWIDTH , and only at the glyph level. If compatibility with 2.1 is an issue,
# metrics should not be specified as global values.
# These keywords all have the same meanings as specified in section 3.2, Indi-
# vidual Glyph Information.


# per-glyph info:
#
# SWIDTH swx0 swy0
# SWIDTH is followed by swx0 and swy0, the scalable width of the glyph in x
# and y for writing mode 0. The scalable widths are of type Number and are in
# units of 1/1000th of the size of the glyph and correspond to the widths found
# in AFM files (for outline fonts). If the size of the glyph is p points, the width
# information must be scaled by p /1000 to get the width of the glyph in
# printer’s points. This width information should be regarded as a vector indi-
# cating the position of the next glyph’s origin relative to the origin of this
# glyph. SWIDTH is mandatory for all writing mode 0 fonts.
# To convert the scalable width to the width in device pixels, multiply SWIDTH
# times p /1000 times r /72, where r is the device resolution in pixels per inch.
# The result is a real number giving the ideal width in device pixels. The actual
# device width must be an integral number of device pixels and is given by the
#
# SWIDTH1 swx1 swy1
# SWIDTH 1 is followed by the values for swx1 and swy1, the scalable width of
# the glyph in x and y, for writing mode 1 (vertical direction). The values are of
# type Number , and represent the widths in glyph space coordinates.
#
# DWIDTH1 dwx1 dwy1
# DWIDTH1 specifies the integer pixel width of the glyph in x and y. Like
# SWIDTH 1, this width information is a vector indicating the position of the
# next glyph’s origin relative to the origin of this glyph. DWIDTH1 is manda-
# tory for all writing mode 1 fonts.
#
# Note
# If METRICSSET is 1 or 2, both SWIDTH1 and DWIDTH1 must be present; if
# METRICSSET is 0, both should be absent.
#
# VVECTOR xoff yoff
# VVECTOR (optional) specifies the components of a vector from origin 0 (the
# origin for writing direction 0) to origin 1 (the origin for writing direction 1).
# If the value of METRICSSET is 1 or 2, VVECTOR must be specified either at
# the global level, or for each individual glyph. If specified at the global level,
# the VVECTOR is the same for all glyphs, though the inclusion of this
# keyword in an individual glyph has the effect of overriding the bal value for
# that specific glyph.
#
# BBX BBw BBh BBxoff0x BByoff0y
# BBX is followed by BBw, the width of the black pixels in x, and BBh, the
# height in y. These are followed by the x and y displacement, BBxoff0 and
# BByoff0, of the lower left corner of the bitmap from origin 0. All values are
# are an integer number of pixels.
# If the font specifies metrics for writing direction 1, VVECTOR specifies the
# offset from origin 0 to origin 1. For example, for writing direction 1, the
# offset from origin 1 to the lower left corner of the bitmap would be:
# BBxoff1x,y = BBxoff0x,y – VVECTOR
