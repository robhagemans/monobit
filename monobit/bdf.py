"""
monobit.bdf - Adobe Glyph Bitmap Distribution Format

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .typeface import Typeface
from .font import Font, encoding_is_unicode
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
    '',
    'FOUNDRY',
    'FAMILY_NAME',
    'WEIGHT_NAME',
    'SLANT',
    'SETWIDTH_NAME',
    'ADD_STYLE_NAME',
    'PIXEL_SIZE',
    'POINT_SIZE',
    'RESOLUTION_X',
    'RESOLUTION_Y',
    'SPACING',
    'AVERAGE_WIDTH',
    'CHARSET_REGISTRY',
    'CHARSET_ENCODING',
)

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

@Typeface.loads('bdf', name='BDF')
def load(instream):
    """Load font from a .bdf file."""
    nchars, comments, bdf_props, x_props = _read_bdf_global(instream)
    glyphs, glyph_props, labels = _read_bdf_characters(instream)
    # check number of characters, but don't break if no match
    if nchars != len(glyphs):
        logging.warning('Number of characters found does not match CHARS declaration.')
    glyphs, properties = _parse_properties(glyphs, glyph_props, bdf_props, x_props)
    return Typeface([Font(glyphs, labels, comments=comments, properties=properties)])


@Typeface.saves('bdf', multi=False)
def save(font, outstream):
    """Write fonts to a .bdf file."""
    _save_bdf(font, outstream)
    return font


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
    size_prop = bdf_props.pop('SIZE').split()
    if len(size_prop) > 3:
        if size_prop[3] != 1:
            raise ValueError('Anti-aliasing and colour not supported.')
        size_prop = size_prop[:3]
    size, xdpi, ydpi = size_prop
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
    x_props = {**xlfd_name_props, **x_props}
    # PIXEL_SIZE = ROUND((RESOLUTION_Y * POINT_SIZE) / 722.7)
    properties = {
        # FULL_NAME is deprecated
        'name': x_props.pop('FACE_NAME', x_props.pop('FULL_NAME', '')).strip('"'),
        'revision': x_props.pop('FONT_VERSION', '').strip('"'),
        'foundry': x_props.pop('FOUNDRY', '').strip('"'),
        'copyright': x_props.pop('COPYRIGHT', '').strip('"'),
        'notice': x_props.pop('NOTICE', '').strip('"'),
        'family': x_props.pop('FAMILY_NAME', '').strip('"'),
        'style': x_props.pop('ADD_STYLE_NAME', '').strip('"').lower(),
        'ascent': x_props.pop('FONT_ASCENT', None),
        'x-height': x_props.pop('X_HEIGHT', None),
        'cap-height': x_props.pop('CAP_HEIGHT', None),
        'pixel-size': x_props.pop('PIXEL_SIZE', None),
        'default-char': x_props.pop('DEFAULT_CHAR', None),
        'slant': _SLANT_MAP.get(x_props.pop('SLANT', ''), None),
        'spacing': _SPACING_MAP.get(x_props.pop('SPACING', ''), None),
    }
    if 'FONT_DESCENT' in x_props:
        properties['descent'] = -int(x_props.pop('FONT_DESCENT'))
    if 'POINT_SIZE' in x_props:
        properties['point-size'] = str(round(int(x_props.pop('POINT_SIZE')) / 10))
    if 'AVERAGE_WIDTH' in x_props:
        properties['average-advance'] = int(x_props.pop('AVERAGE_WIDTH')) / 10
    # prefer the more precise relative weight and setwidth measures
    if 'RELATIVE_SETWIDTH' in x_props:
        properties['setwidth'] = _SETWIDTH_MAP.get(x_props.pop('RELATIVE_SETWIDTH'), None)
        x_props.pop('SETWIDTH_NAME', None)
    if 'setwidth' not in properties or not properties['setwidth']:
        properties['setwidth'] = x_props.pop('SETWIDTH_NAME', '').strip('"').lower()
    if 'RELATIVE_WEIGHT' in x_props:
        properties['weight'] = _WEIGHT_MAP.get(x_props.pop('RELATIVE_WEIGHT'), None)
        x_props.pop('WEIGHT_NAME', None)
    if 'weight' not in properties or not properties['weight']:
        properties['weight'] = x_props.pop('WEIGHT_NAME', '').strip('"').lower()
    # resolution
    if 'RESOLUTION_X' in x_props and 'RESOLUTION_Y' in x_props:
        properties['dpi'] = (x_props.pop('RESOLUTION_X'), x_props.pop('RESOLUTION_Y'))
        x_props.pop('RESOLUTION', None)
    elif 'RESOLUTION' in x_props:
        # deprecated
        properties['dpi'] = (x_props.get('RESOLUTION'), x_props.pop('RESOLUTION'))
    # encoding
    registry = x_props.pop('CHARSET_REGISTRY', '').strip('"').lower()
    encoding = x_props.pop('CHARSET_ENCODING', '').strip('"').lower()
    if encoding:
        if registry:
            properties['encoding'] = f'{registry}-{encoding}'
        else:
            properties['encoding'] = encoding
    properties = {_k: _v for _k, _v in properties.items() if _v is not None and _v != ''}
    # keep unparsed properties
    if not xlfd_name_props:
        properties['bdf.FONT'] = xlfd_name
    properties.update({'bdf.' + _k: _v.strip('"') for _k, _v in x_props.items()})
    return properties


##############################################################################
# BDF writer

def _create_xlfd_name(xlfd_props):
    """Construct XLFD name from properties."""
    xlfd_fields = [xlfd_props.get(prop, '') for prop in _XLFD_NAME_FIELDS]
    return '-'.join(str(_field).strip('"') for _field in xlfd_fields)

def _quoted_string(unquoted):
    """Return quoted version of string, if any."""
    if unquoted:
        return f'"{unquoted}"'
    return ''

def _create_xlfd_properties(font):
    """Construct XLFD properties."""
    xlfd_props = {
        # rendering hints
        'FONT_ASCENT': font.ascent,
        'FONT_DESCENT': -int(font.descent),
        'X_HEIGHT': font.x_height,
        'CAP_HEIGHT': font.cap_height,
        'RESOLUTION_X': font.dpi.x,
        'RESOLUTION_Y': font.dpi.y,
        'POINT_SIZE': int(font.point_size) * 10,
        'FACE_NAME': _quoted_string(font.name),
        'FONT_VERSION': _quoted_string(font.revision),
        'COPYRIGHT': _quoted_string(font.copyright),
        'NOTICE': _quoted_string(font.notice),
        'FOUNDRY': _quoted_string(font.foundry),
        'FAMILY_NAME': _quoted_string(font.family),
        'WEIGHT_NAME': _quoted_string(font.weight.title()),
        'RELATIVE_WEIGHT': (
            {_v: _k for _k, _v in _WEIGHT_MAP.items()}.get(font.weight, 50)
        ),
        'SLANT': _quoted_string(
            {_v: _k for _k, _v in _SLANT_MAP.items()}.get(font.slant, 'R')
        ),
        'SPACING': _quoted_string(
            {_v: _k for _k, _v in _SPACING_MAP.items()}.get(font.spacing, 'P')
        ),
        'SETWIDTH_NAME': _quoted_string(font.setwidth.title()),
        'RELATIVE_SETWIDTH': (
            # 50 is medium
            {_v: _k for _k, _v in _SETWIDTH_MAP.items()}.get(font.setwidth, 50)
        ),
        'ADD_STYLE_NAME': _quoted_string(font.style.title()),
        'PIXEL_SIZE': font.pixel_size,
        'AVERAGE_WIDTH': int(float(font.average_advance) * 10),
        'DEFAULT_CHAR': font.default_char,
    }
    # modify/summarise values
    if encoding_is_unicode(font.encoding):
        xlfd_props['CHARSET_REGISTRY'] = '"ISO10646"'
        xlfd_props['CHARSET_ENCODING'] = '"1"'
    else:
        registry, *encoding = font.encoding.split('-', 1)
        xlfd_props['CHARSET_REGISTRY'] = _quoted_string(registry.upper())
        if encoding:
            xlfd_props['CHARSET_ENCODING'] = _quoted_string(encoding[0].upper())
    # remove empty properties
    xlfd_props = {_k: _v for _k, _v in xlfd_props.items() if _v}
    # TODO: keep unparsed properties
    return xlfd_props

def _save_bdf(font, outstream):
    """Write one font to X11 BDF 2.1."""
    # property table
    xlfd_props = _create_xlfd_properties(font)
    bdf_props = [
        ('STARTFONT', '2.1'),
    ] + [
        ('COMMENT', _comment) for _comment in font.get_comments()
    ] + [
        ('FONT', _create_xlfd_name(xlfd_props)),
        ('SIZE', f'{font.point_size} {font.dpi.x} {font.dpi.y}'),
        (
            'FONTBOUNDINGBOX',
            f'{font.bounding_box.x} {font.bounding_box.y} {font.bearing_before} {font.offset}'
        )
    ]
    # labels
    glyphs = []
    is_unicode = encoding_is_unicode(font.encoding)
    for labels, glyph in font:
        # default: no encoding, first label
        encoding = -1
        name = labels[0]
        for label in labels:
            # keep the first unicode value encountered
            # FIXME: we can't deal with multiple unicode lables for the same glyph
            if is_unicode and label.is_unicode:
                encoding = ord(label.unicode)
                break
            elif not is_unicode and label.is_ordinal:
                encoding = int(label)
                break
        for label in labels:
            # keep the first text label
            if not label.is_unicode and not label.is_ordinal:
                name = label
                break
        # "The SWIDTH y value should always be zero for a standard X font."
        # "The DWIDTH y value should always be zero for a standard X font."
        swidth_y, dwidth_y = 0, 0
        # SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )
        # DWIDTH specifies the widths in x and y, dwx0 and dwy0, in device pixels.
        # Like SWIDTH , this width information is a vector indicating the position of
        # the next glyph’s origin relative to the origin of this glyph.
        dwidth_x = glyph.width + font.bearing_before + font.bearing_after
        swidth_x = int(round(dwidth_x / (font.point_size / 1000) / (font.dpi.y / 72)))
        # TODO: minimize glyphs to bbx before storing, except "cell" fonts
        offset_x, offset_y = font.bearing_before, font.offset
        hex = glyph.as_hex().upper()
        width = len(hex) // glyph.height
        split_hex = [hex[_offs:_offs+width] for _offs in range(0, len(hex), width)]
        glyphs.append([
            ('STARTCHAR', name),
            ('ENCODING', str(encoding)),
            ('SWIDTH', f'{swidth_x} {swidth_y}'),
            ('DWIDTH', f'{dwidth_x} {dwidth_y}'),
            ('BBX', f'{glyph.width} {glyph.height} {offset_x} {offset_y}'),
            ('BITMAP', '\n' + '\n'.join(split_hex)),
        ])
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
