"""
monobit.bdf - read and write .bdf files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .typeface import Typeface
from .font import Font
from .glyph import Glyph


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
    '50': 'regular', # Medium, Normal, Regular,...
    '60': 'semi-bold', # SemiBold, DemiBold, ...
    '70': 'bold',
    '80': 'extra-bold', # ExtraBold, Heavy, ...
    '90': 'heavy', # UltraBold, Black, ...,
}

# fields of the xlfd font name
_XLFD_NAME_FIELDS = (
    None,
    'foundry',
    'family',
    'weight',
    'slant',
    'setwidth',
    'style',
    'pixel-size',
    'point-size',
    '_dpi-x',
    '_dpi-y',
    'spacing',
    'average-width',
    '_charset-registry',
    '_charset-encoding',
)

_XLFD_PROPERTIES = {
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
    'FONT_VERSION': 'revision',
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

# unparsed xlfd properties, for reference
_XLFD_UNPARSED = {
    'MIN_SPACE',
    'NORM_SPACE',
    'MAX_SPACE',
    'END_SPACE',
    'AVG_CAPITAL_WIDTH',
    'AVG_LOWERCASE_WIDTH',
    'QUAD_WIDTH',
    'FIGURE_WIDTH',
    'SUPERSCRIPT_X',
    'SUPERSCRIPT_Y',
    'SUBSCRIPT_X',
    'SUBSCRIPT_Y',
    'SUPERSCRIPT_SIZE',
    'SUBSCRIPT_SIZE',
    'SMALL_CAP_SIZE',
    'UNDERLINE_POSITION',
    'UNDERLINE_THICKNESS',
    'STRIKEOUT_ASCENT',
    'STRIKEOUT_DESCENT',
    'ITALIC_ANGLE',
    'WEIGHT',
    'DESTINATION',
    'FONT_TYPE',
    'RASTERIZER_NAME',
    'RASTERIZER_VERSION',
    #'RAW_*',
    'AXIS_NAMES',
    'AXIS_LIMITS',
    'AXIS_TYPES',
}


##############################################################################
# top-level calls

# BDF is specified as ASCII only
# but the XLFD atoms are specified as iso8859-1, so this seems the best choice

@Typeface.loads('bdf', name='BDF', encoding='iso8859-1')
def load(instream):
    """Load font from a .bdf file."""
    nchars, comments, bdf_props, x_props = _read_bdf_global(instream)
    glyphs, glyph_props, labels = _read_bdf_characters(instream)
    # check number of characters, but don't break if no match
    if nchars != len(glyphs):
        logging.warning('Number of characters found does not match CHARS declaration.')
    glyphs, properties = _parse_properties(glyphs, glyph_props, bdf_props, x_props)
    return Typeface([Font(glyphs, labels, comments=comments, properties=properties)])


##############################################################################
# BDF reader

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

def _parse_properties(glyphs, glyph_props, bdf_props, x_props):
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
    return glyphs, properties


def _parse_bdf_properties(glyphs, glyph_props, bdf_props):
    """Parse BDF global and per-glyph geometry."""
    size, xdpi, ydpi = bdf_props.pop('SIZE').split(' ')
    properties = {
        'source-format': 'BDF v{}'.format(bdf_props.pop('STARTFONT')),
        'point-size': size,
        'dpi': (xdpi, ydpi),
    }
    try:
        properties['revision'] = bdf_props.pop('CONTENTVERSION')
    except KeyError:
        pass
    # global settings, tend to be overridden by per-glyph settings
    global_bbx = bdf_props.pop('FONTBOUNDINGBOX')
    # not supported: METRICSSET != 0
    writing_direction = bdf_props.pop('METRICSSET', 0)
    if writing_direction == 1:
        # top-to-bottom only
        raise ValueError('Top-to-bottom fonts not yet supported.')
    elif writing_direction == 2:
        logging.warning(
            'Top-to-bottom fonts not yet supported. Preserving horizontal metrics only.'
        )
    # global DWIDTH; use bounding box as fallback if not specified
    global_dwidth = bdf_props.pop('DWIDTH', global_bbx[:2])
    global_swidth = bdf_props.pop('SWIDTH', 0)
    # ignored: for METRICSSET in 1, 2: DWIDTH1, SWIDTH1, VVECTOR
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
            # ideally, SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )
            swidth_x, swidth_y = (int(_x) for _x in props.get('SWIDTH', global_swidth).split(' '))
            #logging.info('x swidth: %s dwidth: %s', swidth_x*int(size)*int(xdpi) / 72000, dwidth_x)
            #logging.info('y swidth: %s dwidth: %s', swidth_y*int(size)*int(ydpi) / 72000, dwidth_y)
        except KeyError:
            pass
        # ignored: for METRICSSET in 1, 2: DWIDTH1, SWIDTH1, VVECTOR
        offsets_x.append(offset_x)
        offsets_y.append(offset_y)
        overshoots.append((offset_x + bbx_width) - dwidth_x)
        heights.append(bbx_height + offset_y)
    # shift/resize all glyphs to font bounding box
    leftmost = min(offsets_x)
    rightmost = max(overshoots)
    bottommost = min(offsets_y)
    topmost = max(heights)
    properties['bearing-before'] = leftmost
    properties['bearing-after'] = -rightmost
    properties['offset'] = bottommost
    mod_glyphs = []
    for glyph, props in zip(glyphs, glyph_props):
        bbx_width, bbx_height, offset_x, offset_y = (int(_p) for _p in props['BBX'].split(' '))
        dwidth_x, dwidth_y = (int(_p) for _p in props['DWIDTH'].split(' '))
        overshoot = (offset_x + bbx_width) - dwidth_x
        padding_right = rightmost - overshoot
        padding_left = offset_x - leftmost
        padding_bottom = offset_y - bottommost
        padding_top = topmost - bbx_height - offset_y
        glyph = glyph.expand(padding_left, padding_top, padding_right, padding_bottom)
        mod_glyphs.append(glyph)
    xlfd_name = bdf_props.pop('FONT')
    # keep unparsed bdf props
    properties.update({
        'bdf.' + _key: _value
        for _key, _value in bdf_props.items()
    })
    return mod_glyphs, properties, xlfd_name


def _parse_xlfd_name(xlfd_str):
    """Parse X logical font description font name string."""
    xlfd = xlfd_str.split('-')
    if len(xlfd) == 15:
        properties = {_key: _value for _key, _value in zip(_XLFD_NAME_FIELDS, xlfd) if _key}
    else:
        logging.warning('Could not parse X font name string `%s`', xlfd_str)
        return {}
    return properties


def _parse_xlfd_properties(x_props, xlfd_name):
    """Parse X metadata."""
    xlfd_name_props = _parse_xlfd_name(xlfd_name)
    # we ignore AVERAGE_WIDTH, can be calculated
    mapping = _XLFD_PROPERTIES
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
    if 'slant' in properties and properties['slant']:
        properties['slant'] = _SLANT_MAP[properties['slant']]
    if 'spacing' in properties and properties['spacing']:
        properties['spacing'] = _SPACING_MAP[properties['spacing']]
    # prefer the more precise relative weight and setwidth measures
    if '_rel-setwidth' in properties and properties['_rel-setwidth']:
        properties['setwidth'] = _SETWIDTH_MAP[properties.pop('_rel-setwidth')]
    if '_rel-weight' in properties and properties['_rel-weight']:
        properties['weight'] = _WEIGHT_MAP[properties.pop('_rel-weight')]
    if 'point-size' in properties:
        properties['point-size'] = str(round(int(properties['point-size']) / 10))
    if 'average-width' in properties:
        properties['average-width'] = int(properties['average-width']) / 10
    if '_dpi-x' in properties and '_dpi-y' in properties:
        xdpi, ydpi = properties.pop('_dpi-x'), properties.pop('_dpi-y')
        if 'dpi' in properties and not (properties['dpi'] == xdpi == ydpi):
            logging.warning(
                'Inconsistent XLFD dpi properties: dpi=%s but dpi-x=%s and dpi-y=%s.',
                properties['dpi'], xdpi, ydpi
            )
        properties['dpi'] = (xdpi, ydpi)
    # encoding
    try:
        registry = properties.pop('_charset-registry')
        encoding = properties.pop('_charset-encoding')
    except KeyError:
        pass
    else:
        properties['encoding'] = (registry + '-' + encoding).lower()
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
