"""
monobit.formats.xlfd.xlfd - X11 Logical Font Description

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...encoding import charmaps
from ...labels import Char


# dot property namespace for unrecognised properties
CUSTOM_PROP = 'custom'


##############################################################################
# specification

# XLFD conventions: https://www.x.org/releases/X11R7.6/doc/xorg-docs/specs/XLFD/xlfd.html
# charset and property registry: https://github.com/freedesktop/xorg-docs/blob/master/registry

# https://github.com/freedesktop/xorg-docs/blob/master/registry
#
# 14. FONT CHARSET (REGISTRY AND ENCODING) NAMES
#
# See Sections 3.1.2.12 of the XLFD.  For ISO standards, the format
# will generally be: "ISO" + <standard-number> + "-" + <part-number>
#
# Name						Reference
# ----						---------
# "DEC"						[27]
# 	registry prefix
# "DEC.CNS11643.1986-2"				[53]
# 	CNS11643 2-plane using the encoding
# 	suggested in that standard
# "DEC.DTSCS.1990-2"				[54]
# 	DEC Taiwan Supplemental Character Set
# "fujitsu.u90x01.1991-0"				[87]
# "fujitsu.u90x03.1991-0"				[87]
# "GB2312.1980-0"					[39],[12]
# 	China (PRC) Hanzi, GL encoding
# "GB2312.1980-1"					[39]
# 	(deprecated)
# 	China (PRC) Hanzi, GR encoding
# "HP-Arabic8"					[36]
# 	HPARABIC8 8-bit character set
# "HP-East8"					[36]
# 	HPEAST8 8-bit character set
# "HP-Greek8"					[36]
# 	HPGREEK8 8-bit character set
# "HP-Hebrew8"					[36]
# 	HPHEBREW8 8-bit character set
# "HP-Japanese15"					[36]
# 	HPJAPAN15 15-bit characer set,
# 	modified from industry defacto
# 	standard Shift-JIS
# "HP-Kana8"					[36]
# 	HPKANA8 8-bit character set
# "HP-Korean15"					[36]
# 	HPKOREAN15 15-bit character set
# "HP-Roman8"					[36]
# 	HPROMAN8 8-bit character set
# "HP-SChinese15"					[36]
# 	HPSCHINA15 15-bit character set for
# 	support of Simplified Chinese
# "HP-TChinese15"					[36]
# 	HPTCHINA15 15-bit character set for
# 	support of Traditional Chinese
# "HP-Turkish8"					[36]
# 	HPTURKISH8 8-bit character set
# "IPSYS"						[59]
# 	registry prefix
# "IPSYS.IE-1"					[59]
# "ISO2022"<REG>"-"<ENC>				[44]
# "ISO646.1991-IRV"				[107]
# 	ISO 646 International Reference Version
# "ISO8859-1"					[15],[12]
# 	ISO Latin alphabet No. 1
# "ISO8859-2"					[15],[12]
# 	ISO Latin alphabet No. 2
# "ISO8859-3"					[15],[12]
# 	ISO Latin alphabet No. 3
# "ISO8859-4"					[15],[12]
# 	ISO Latin alphabet No. 4
# "ISO8859-5"					[15],[12]
# 	ISO Latin/Cyrillic alphabet
# "ISO8859-6"					[15],[12]
# 	ISO Latin/Arabic alphabet
# "ISO8859-7"					[15],[12]
# 	ISO Latin/Greek alphabet
# "ISO8859-8"					[15],[12]
# 	ISO Latin/Hebrew alphabet
# "ISO8859-9"					[15],[12]
# 	ISO Latin alphabet No. 5
# "ISO8859-10"					[15],[12]
# 	ISO Latin alphabet No. 6
# "ISO8859-13"					[15],[12]
# 	ISO Latin alphabet No. 7
# "ISO8859-14"					[15],[12]
# 	ISO Latin alphabet No. 8
# "ISO8859-15"					[15],[12]
# 	ISO Latin alphabet No. 9
# "ISO8859-16"					[15],[12]
# 	ISO Latin alphabet No. 10
# "FCD8859-15"					[7]
# 	(deprecated)
# 	ISO Latin alphabet No. 9, Final Committee Draft
# "ISO10646-1"					[133]
# 	Unicode Universal Multiple-Octet Coded Character Set
# "ISO10646-MES"					[133]
# 	(deprecated)
# 	Unicode Minimum European Subset
# "JISX0201.1976-0"				[38],[12]
# 	8-Bit Alphanumeric-Katakana Code
# "JISX0208.1983-0"				[40],[12]
# 	Japanese Graphic Character Set,
# 	GL encoding
# "JISX0208.1990-0"				[71]
# 	Japanese Graphic Character Set,
# 	GL encoding
# "JISX0208.1983-1"				[40]
# 	(deprecated)
# 	Japanese Graphic Character Set,
# 	GR encoding
# "JISX0212.1990-0"				[72]
# 	Supplementary Japanese Graphic Character Set,
# 	GL encoding
# "KOI8-R"					[119]
# 	Cyrillic alphabet
# "KSC5601.1987-0"				[41],[12]
# 	Korean Graphic Character Set,
# 	GL encoding
# "KSC5601.1987-1"				[41]
# 	(deprecated)
# 	Korean Graphic Character Set,
# 	GR encoding
# "omron_CNS11643-0"				[45]
# "omron_CNS11643-1"				[45]
# "omron_BIG5-0"					[45]
# "omron_BIG5-1"					[45]
# "wn.tamil.1993"					[103]


# https://www.freshports.org/x11-fonts/encodings/
#
# share/fonts/encodings/adobe-dingbats.enc.gz
# share/fonts/encodings/adobe-standard.enc.gz
# share/fonts/encodings/adobe-symbol.enc.gz
# share/fonts/encodings/armscii-8.enc.gz
# share/fonts/encodings/ascii-0.enc.gz
# share/fonts/encodings/dec-special.enc.gz
# share/fonts/encodings/encodings.dir
# share/fonts/encodings/ibm-cp437.enc.gz
# share/fonts/encodings/ibm-cp850.enc.gz
# share/fonts/encodings/ibm-cp852.enc.gz
# share/fonts/encodings/ibm-cp866.enc.gz
# share/fonts/encodings/iso8859-11.enc.gz
# share/fonts/encodings/iso8859-13.enc.gz
# share/fonts/encodings/iso8859-16.enc.gz
# share/fonts/encodings/iso8859-6.16.enc.gz
# share/fonts/encodings/iso8859-6.8x.enc.gz
# share/fonts/encodings/large/big5.eten-0.enc.gz
# share/fonts/encodings/large/big5hkscs-0.enc.gz
# share/fonts/encodings/large/cns11643-1.enc.gz
# share/fonts/encodings/large/cns11643-2.enc.gz
# share/fonts/encodings/large/cns11643-3.enc.gz
# share/fonts/encodings/large/encodings.dir
# share/fonts/encodings/large/gb18030-0.enc.gz
# share/fonts/encodings/large/gb18030.2000-0.enc.gz
# share/fonts/encodings/large/gb18030.2000-1.enc.gz
# share/fonts/encodings/large/gb2312.1980-0.enc.gz
# share/fonts/encodings/large/gbk-0.enc.gz
# share/fonts/encodings/large/jisx0201.1976-0.enc.gz
# share/fonts/encodings/large/jisx0208.1990-0.enc.gz
# share/fonts/encodings/large/jisx0212.1990-0.enc.gz
# share/fonts/encodings/large/ksc5601.1987-0.enc.gz
# share/fonts/encodings/large/ksc5601.1992-3.enc.gz
# share/fonts/encodings/large/sun.unicode.india-0.enc.gz
# share/fonts/encodings/microsoft-cp1250.enc.gz
# share/fonts/encodings/microsoft-cp1251.enc.gz
# share/fonts/encodings/microsoft-cp1252.enc.gz
# share/fonts/encodings/microsoft-cp1253.enc.gz
# share/fonts/encodings/microsoft-cp1254.enc.gz
# share/fonts/encodings/microsoft-cp1255.enc.gz
# share/fonts/encodings/microsoft-cp1256.enc.gz
# share/fonts/encodings/microsoft-cp1257.enc.gz
# share/fonts/encodings/microsoft-cp1258.enc.gz
# share/fonts/encodings/microsoft-win3.1.enc.gz
# share/fonts/encodings/mulearabic-0.enc.gz
# share/fonts/encodings/mulearabic-1.enc.gz
# share/fonts/encodings/mulearabic-2.enc.gz
# share/fonts/encodings/mulelao-1.enc.gz
# share/fonts/encodings/suneu-greek.enc.gz
# share/fonts/encodings/tcvn-0.enc.gz
# share/fonts/encodings/tis620-2.enc.gz
# share/fonts/encodings/viscii1.1-1.enc.gz

# https://x.org/releases/X11R7.7/doc/xorg-docs/fonts/fonts.html
# > Specifying an encoding value of
# > adobe-fontspecific for a Type 1 font disables the encoding mechanism. This is useful with symbol
# > and incorrectly encoded fonts (see Hints about using badly encoded fonts below).
#
# > In the case of Type 1 fonts, the font designer can specify a default encoding; this encoding is
# > requested by using the “adobe-fontspecific” encoding in the XLFD name.

# some more encodings mentioned here:
# https://www.x.org/releases/X11R6.9.0/doc/html/fonts3.html
# https://www.x.org/releases/X11R6.9.0/doc/html/fonts4.html
#
# ISO10646-1 = unicode
# ISO8859-1 (etc)  = latin-1
# KOI8-R (-U -RU -UNI -E)
# fontspecific-0
# microsoft-symbol
# apple-roman
# ibm-cp437
# adobe-standard
# adobe-dingbats
# adobe-symbol
# adobe-fontspecific
# microsoft-cp1252
# microsoft-win3.1
# jisx0208.1990-0
# jisx0201.1976-0
# big5.eten-0
# gb2312.1980-0

# X11 / BDF undefined
# these are mapped to "no encoding"
# "no encoding" is mapped to the first name provided here
_UNDEFINED_ENCODINGS = [
    'fontspecific-0',
    'adobe-fontspecific',
    'fontspecific',
]

# names to be used when writing bdf
_UNIX_ENCODINGS = {
    '': _UNDEFINED_ENCODINGS[0],
    'unicode': 'ISO10646-1',
    'ascii': 'ascii-0',

    'latin-1': 'ISO8859-1',
    'latin-2': 'ISO8859-2',
    'latin-3': 'ISO8859-3',
    'latin-4': 'ISO8859-4',
    'iso8859-5': 'ISO8859-5',
    'iso8859-6': 'ISO8859-6',
    'iso8859-7': 'ISO8859-7',
    'iso8859-8': 'ISO8859-8',
    'iso8859-9': 'ISO8859-9',
    'iso8859-10': 'ISO8859-10',
    'iso8859-11': 'ISO8859-11',
    'iso8859-13': 'ISO8859-13',
    'iso8859-14': 'ISO8859-14',
    'iso8859-15': 'ISO8859-15',
    'iso8859-16': 'ISO8859-16',

    'koi8-r': 'KOI8-R',
    'koi8-u': 'KOI8-U',
    'koi8-ru': 'KOI8-RU',
    'koi8-e': 'KOI8-E',
    'koi8-unified': 'KOI8-UNI',

    'mac-symbol': 'microsoft-symbol',
    'mac-roman': 'apple-roman',
    'cp437': 'ibm-cp437',
    'cp850': 'ibm-cp850',
    'cp852': 'ibm-cp852',
    'cp866': 'ibm-cp866',

    # adobe, dec encodings have standard names

    'windows-1250': 'microsoft-cp1250',
    'windows-1251': 'microsoft-cp1251',
    'windows-1252': 'microsoft-cp1252',
    'windows-1253': 'microsoft-cp1253',
    'windows-1254': 'microsoft-cp1254',
    'windows-1255': 'microsoft-cp1255',
    'windows-1256': 'microsoft-cp1256',
    'windows-1257': 'microsoft-cp1257',
    'windows-1258': 'microsoft-cp1258',
    'windows-3.1': 'microsoft-win3.1',

    'hp-roman8': 'HP-Roman8',
    'hp-greek8': 'HP-Greek8',
    'hp-thai8': 'HP-Thai8',
    'hp-turkish8': 'HP-Turkish8',

    'jis-x0201': 'jisx0201.1976-0',

    'big5-hkscs': 'big5hkscs-0',
    'windows-936': 'gbk-0',

    # johab
    'windows-1361': 'ksc5601.1992-3',
    # ksc5601.1987-0

    'tis-620': 'tis620-0',
    'viscii': 'viscii1.1-1',
    # tcvn-0 ?

    # big5.eten-0
    # gb2312.1980-0
    # cns11643-1
    # cns11643-2
    # cns11643-3
    # gb18030-0
    # gb18030.2000-0
    # gb18030.2000-1

    # jisx0208.1990-0
    # jisx0212.1990-0
}

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
    'C': 'character-cell',
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
    # key name is unofficial but in widespread use
    'FONTNAME_REGISTRY',
    # official field name matches
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
    # average cap/lower width, in tenths of pixels, negative for rtl
    'AVG_CAPITAL_WIDTH',
    'AVG_LOWERCASE_WIDTH',
    # width of a quad (em) space. deprecated.
    'QUAD_WIDTH',
    # for boxing/voiding glyphs
    'STRIKEOUT_ASCENT',
    'STRIKEOUT_DESCENT',
    # the nominal posture angle of the typeface design, in 1/64 degrees, measured from the
    # glyph origin counterclockwise from the three o’clock position.
    'ITALIC_ANGLE',
    # the calculated weight of the font, computed as the ratio of capital stem width to CAP_HEIGHT,
    # in the range 0 to 1000, where 0 is the lightest weight.
    'WEIGHT',
    # the format of the font data as they are read from permanent storage by the current font source
    # 'Bitmap', 'Prebuilt', 'Type 1', 'TrueType', 'Speedo', 'F3'
    'FONT_TYPE',
    # the specific name of the rasterizer that has performed some rasterization operation
    #(such as scaling from out- lines) on this font.
    'RASTERIZER_NAME',
    # the formal or informal version of a font rasterizer.
    'RASTERIZER_VERSION',
    #'RAW_*',
    # axes of a polymorphic font
    'AXIS_NAMES',
    'AXIS_LIMITS',
    'AXIS_TYPES',
    # key name is not in the spec but in widespread use and in bdflib
    'FONTNAME_REGISTRY',
    'CHARSET_COLLECTIONS',
    'DEVICE_FONT_NAME',

    # for fonts with a transformation matrix
    'RAW_ASCENT',
    'RAW_AVERAGE_WIDTH',
    'RAW_AVG_CAPITAL_WIDTH',
    'RAW_AVG_LOWERCASE_WIDTH',
    'RAW_CAP_HEIGHT',
    'RAW_DESCENT',
    'RAW_END_SPACE',
    'RAW_FIGURE_WIDTH',
    'RAW_MAX_SPACE',
    'RAW_MIN_SPACE',
    'RAW_NORM_SPACE',
    'RAW_PIXEL_SIZE',
    'RAW_POINT_SIZE',
    'RAW_PIXELSIZE',
    'RAW_POINTSIZE',
    'RAW_QUAD_WIDTH',
    'RAW_SMALL_CAP_SIZE',
    'RAW_STRIKEOUT_ASCENT',
    'RAW_STRIKEOUT_DESCENT',
    'RAW_SUBSCRIPT_SIZE',
    'RAW_SUBSCRIPT_X',
    'RAW_SUBSCRIPT_Y',
    'RAW_SUPERSCRIPT_SIZE',
    'RAW_SUPERSCRIPT_X',
    'RAW_SUPERSCRIPT_Y',
    'RAW_UNDERLINE_POSITION',
    'RAW_UNDERLINE_THICKNESS',
    'RAW_X_HEIGHT',
}


def _parse_xlfd_name(xlfd_str):
    """Parse X logical font description font name string."""
    if not xlfd_str:
        # if no name at all that's intentional (used for HBF) - do not warn
        return {}
    xlfd = xlfd_str.split('-')
    if len(xlfd) == 15:
        properties = {
            _key: _value.replace('~', '-')
            for _key, _value in zip(_XLFD_NAME_FIELDS, xlfd)
            if _key and _value
        }
    else:
        logging.warning('Could not parse X font name string `%s`', xlfd_str)
        return {}
    return properties

def from_quoted_string(quoted):
    """Strip quotes"""
    return quoted.strip('"').replace('""', '"')

def _all_ints(*value, to_int=int):
    """Convert all items in tuple to int."""
    return tuple(to_int(_x) for _x in value)

def parse_xlfd_properties(x_props, xlfd_name, to_int=int):
    """Parse X metadata."""
    xlfd_name_props = _parse_xlfd_name(xlfd_name)
    # find fields in XLFD FontName that do not match the FontProperties
    conflicting = '\n'.join(
        f'{_k}={repr(_v)} vs {_k}={repr(x_props[_k])}' for _k, _v in xlfd_name_props.items()
        if _k in x_props and not (
            str(_v) == str(x_props[_k])
            or f'"{_v}"' == str(x_props[_k])
        )
    )
    if conflicting:
        logging.info('Conflicts between XLFD FontName and FontProperties: %s', conflicting)
    # continue with the XLFD FontProperties overriding the XLFD FontName fields if given
    x_props = {**xlfd_name_props, **x_props}
    # PIXEL_SIZE = ROUND((RESOLUTION_Y * POINT_SIZE) / 722.7)
    properties = {
        # FULL_NAME is deprecated
        'name': from_quoted_string(
            x_props.pop('FACE_NAME', x_props.pop('FULL_NAME', ''))
        ),
        'revision': from_quoted_string(x_props.pop('FONT_VERSION', '')),
        'foundry': from_quoted_string(x_props.pop('FOUNDRY', '')),
        'copyright': from_quoted_string(x_props.pop('COPYRIGHT', '')),
        'notice': from_quoted_string(x_props.pop('NOTICE', '')),
        'family': from_quoted_string(x_props.pop('FAMILY_NAME', '')),
        'style': from_quoted_string(x_props.pop('ADD_STYLE_NAME', '')).lower(),
        'ascent': x_props.pop('FONT_ASCENT', None),
        'descent': x_props.pop('FONT_DESCENT', None),
        'x_height': x_props.pop('X_HEIGHT', None),
        'cap_height': x_props.pop('CAP_HEIGHT', None),
        'pixel_size': x_props.pop('PIXEL_SIZE', None),
        'slant': _SLANT_MAP.get(
            from_quoted_string(x_props.pop('SLANT', '')), None
        ),
        'spacing': _SPACING_MAP.get(
            from_quoted_string(x_props.pop('SPACING', '')), None
        ),
        'underline_descent': x_props.pop('UNDERLINE_POSITION', None),
        'underline_thickness': x_props.pop('UNDERLINE_THICKNESS', None),
        'superscript_size': x_props.pop('SUPERSCRIPT_SIZE', None),
        'subscript_size': x_props.pop('SUBSCRIPT_SIZE', None),
        'small_cap_size': x_props.pop('SMALL_CAP_SIZE', None),
        'digit_width': x_props.pop('FIGURE_WIDTH', None),
        'min_word_space': x_props.pop('MIN_SPACE', None),
        'word_space': x_props.pop('NORM_SPACE', None),
        'max_word_space': x_props.pop('MAX_SPACE', None),
        'sentence_space': x_props.pop('END_SPACE', None),
    }
    if 'DESTINATION' in x_props and to_int(x_props['DESTINATION']) < 2:
        dest = to_int(x_props.pop('DESTINATION'))
        properties['device'] = 'screen' if dest else 'printer'
    if 'POINT_SIZE' in x_props:
        properties['point_size'] = round(to_int(x_props.pop('POINT_SIZE')) / 10)
    if 'AVERAGE_WIDTH' in x_props:
        properties['average_width'] = to_int(x_props.pop('AVERAGE_WIDTH')) / 10
    # prefer the more precise relative weight and setwidth measures
    if 'RELATIVE_SETWIDTH' in x_props:
        properties['setwidth'] = _SETWIDTH_MAP.get(
            x_props.pop('RELATIVE_SETWIDTH'), None
        )
        x_props.pop('SETWIDTH_NAME', None)
    if 'setwidth' not in properties or not properties['setwidth']:
        properties['setwidth'] = from_quoted_string(
            x_props.pop('SETWIDTH_NAME', '')
        ).lower()
    if 'RELATIVE_WEIGHT' in x_props:
        properties['weight'] = _WEIGHT_MAP.get(x_props.pop('RELATIVE_WEIGHT'), None)
        x_props.pop('WEIGHT_NAME', None)
    if 'weight' not in properties or not properties['weight']:
        properties['weight'] = from_quoted_string(x_props.pop('WEIGHT_NAME', '')).lower()
    # resolution
    if 'RESOLUTION_X' in x_props and 'RESOLUTION_Y' in x_props:
        properties['dpi'] = _all_ints(
            x_props.pop('RESOLUTION_X'), x_props.pop('RESOLUTION_Y')
        )
        x_props.pop('RESOLUTION', None)
    elif 'RESOLUTION' in x_props:
        # deprecated
        properties['dpi'] = _all_ints(
            x_props.get('RESOLUTION'), x_props.pop('RESOLUTION'), to_int=to_int
        )
    if 'SUPERSCRIPT_X' in x_props and 'SUPERSCRIPT_Y' in x_props:
        properties['superscript_offset'] = _all_ints(
            x_props.pop('SUPERSCRIPT_X'), x_props.pop('SUPERSCRIPT_Y'),
            to_int=to_int
        )
    if 'SUBSCRIPT_X' in x_props and 'SUBSCRIPT_Y' in x_props:
        properties['subscript_offset'] = _all_ints(
            x_props.pop('SUBSCRIPT_X'), x_props.pop('SUBSCRIPT_Y'),
            to_int=to_int
        )
    # encoding
    registry = from_quoted_string(x_props.pop('CHARSET_REGISTRY', '')).lower()
    encoding = from_quoted_string(x_props.pop('CHARSET_ENCODING', '')).lower()
    if registry and encoding and encoding != '0':
        properties['encoding'] = f'{registry}-{encoding}'
    elif registry:
        properties['encoding'] = registry
    elif encoding != '0':
        properties['encoding'] = encoding
    if properties['encoding'] in _UNDEFINED_ENCODINGS:
        properties['encoding'] = ''
    if 'DEFAULT_CHAR' in x_props:
        default_ord = to_int(x_props.pop('DEFAULT_CHAR', None))
        if charmaps.is_unicode(properties['encoding']):
            properties['default_char'] = Char(chr(default_ord))
        else:
            properties['default_char'] = default_ord
    # keep original FontName if invalid or conflicting
    if not xlfd_name_props:
        if not properties['family']:
            properties['family'] = xlfd_name
        else:
            properties['xlfd.font_name'] = xlfd_name
    if conflicting:
        properties['xlfd.font_name'] = xlfd_name
    # keep unparsed but known properties
    for key in _XLFD_UNPARSED:
        try:
            value = x_props.pop(key)
        except KeyError:
            continue
        key = key.lower()
        value = from_quoted_string(value)
        if value:
            properties[f'xlfd.{key}'] = value
    # drop empty known properties
    properties = {
        _k: _v for _k, _v in properties.items()
        if _v is not None and _v != ''
    }
    # keep unrecognised properties but in separate namespace
    # to avoid any clashes with yaff properties
    properties.update({
        f'{CUSTOM_PROP}.{_k}'.lower(): from_quoted_string(_v)
        for _k, _v in x_props.items()
    })
    return properties



##############################################################################

def create_xlfd_name(xlfd_props):
    """Construct XLFD name from properties."""
    # if we stored a font name explicitly, keep it
    try:
        return xlfd_props['FONT_NAME']
    except KeyError:
        pass
    xlfd_fields = [xlfd_props.get(prop, '') for prop in _XLFD_NAME_FIELDS]
    return '-'.join(str(_field).strip('"').replace('-', '~') for _field in xlfd_fields)

def _quoted_string(unquoted):
    """Return quoted version of string, if any."""
    return '"{}"'.format(unquoted.replace('"', '""'))

def create_xlfd_properties(font):
    """Construct XLFD properties."""
    # construct the fields needed for FontName if not defined, leave others optional
    xlfd_props = {
        'FONT_ASCENT': font.get_defined('ascent'),
        'FONT_DESCENT': font.get_defined('descent'),
        'PIXEL_SIZE': font.pixel_size,
        'X_HEIGHT': font.get_defined('x_height'),
        'CAP_HEIGHT': font.get_defined('cap_height'),
        'RESOLUTION_X': font.dpi.x,
        'RESOLUTION_Y': font.dpi.y,
        'POINT_SIZE': int(font.point_size) * 10,
        'FACE_NAME': _quoted_string(font.name) if 'name' in font.get_properties() else None,
        'FONT_VERSION': _quoted_string(font.revision) if 'revision' in font.get_properties() else None,
        'COPYRIGHT': _quoted_string(font.copyright) if 'copyright' in font.get_properties() else None,
        'NOTICE': _quoted_string(font.notice) if 'notice' in font.get_properties() else None,
        'FOUNDRY': _quoted_string(font.foundry),
        'FAMILY_NAME': _quoted_string(font.family),
        'WEIGHT_NAME': _quoted_string(font.weight.title()),
        'RELATIVE_WEIGHT': int(
            {_v: _k for _k, _v in _WEIGHT_MAP.items()}.get(font.weight, 50)
        ),
        'SLANT': _quoted_string(
            {_v: _k for _k, _v in _SLANT_MAP.items()}.get(font.slant, 'R')
        ),
        'SPACING': _quoted_string(
            {_v: _k for _k, _v in _SPACING_MAP.items()}.get(font.spacing, 'P')
        ),
        'SETWIDTH_NAME': _quoted_string(font.setwidth.title()),
        'RELATIVE_SETWIDTH': int(
            # 50 is medium
            {_v: _k for _k, _v in _SETWIDTH_MAP.items()}.get(font.setwidth, 50)
        ),
        'ADD_STYLE_NAME': _quoted_string(font.style.title()),
        'AVERAGE_WIDTH': round(float(font.average_width) * 10),
        # only set if explicitly defined
        'UNDERLINE_POSITION': font.get_defined('underline_descent'),
        'UNDERLINE_THICKNESS': font.get_defined('underline_thickness'),
        'DESTINATION': {'printer': 0, 'screen': 1}.get(font.device.lower(), None),
        'SUPERSCRIPT_SIZE': font.get_defined('superscript_size'),
        'SUBSCRIPT_SIZE': font.get_defined('subscript_size'),
        'SMALL_CAP_SIZE': font.get_defined('small_cap_size'),
        'SUPERSCRIPT_X': font.superscript_offset.x if 'superscript_offset' in font.get_properties() else None,
        'SUPERSCRIPT_Y': font.superscript_offset.y if 'superscript_offset' in font.get_properties() else None,
        'SUBSCRIPT_X': font.subscript_offset.x if 'subscript_offset' in font.get_properties() else None,
        'SUBSCRIPT_Y': font.subscript_offset.y if 'subscript_offset' in font.get_properties() else None,
        'FIGURE_WIDTH': font.get_defined('digit_width'),
        'MIN_SPACE': font.get_defined('min_word_space'),
        'NORM_SPACE': font.get_defined('word_space'),
        'MAX_SPACE': font.get_defined('max_word_space'),
        'END_SPACE': font.get_defined('sentence_space'),
    }
    # encoding dependent values
    default_glyph = font.get_default_glyph()
    if charmaps.is_unicode(font.encoding):
        if default_glyph.char:
            default_codepoint = tuple(ord(_c) for _c in default_glyph.char)
        else:
            default_codepoint = default_glyph.codepoint
        if not len(default_codepoint):
            logging.debug('Cannot store default glyph in BDF without character or codepoint label.')
        elif len(default_codepoint) > 1:
            logging.warning('Cannot store grapheme sequence as a BDF default glyph.')
        else:
            xlfd_props['DEFAULT_CHAR'] = default_codepoint[0]
        # unicode encoding
        xlfd_props['CHARSET_REGISTRY'] = '"ISO10646"'
        xlfd_props['CHARSET_ENCODING'] = '"1"'
    else:
        default_codepoint = default_glyph.codepoint
        if not len(default_codepoint):
            logging.debug('Cannot store default glyph in BDF without character or codepoint label.')
        else:
            xlfd_props['DEFAULT_CHAR'] = int(default_codepoint)
        # try preferred name
        encoding_name = _UNIX_ENCODINGS.get(font.encoding, font.encoding)
        registry, *encoding = encoding_name.split('-', 1)
        # encoding
        xlfd_props['CHARSET_REGISTRY'] = _quoted_string(registry.upper())
        if encoding:
            xlfd_props['CHARSET_ENCODING'] = _quoted_string(encoding[0].upper())
        else:
            xlfd_props['CHARSET_ENCODING'] = '"0"'
    # remove unset properties
    xlfd_props = {_k: _v for _k, _v in xlfd_props.items() if _v is not None}
    # keep unparsed properties
    unparsed = {
        _k.replace('-', '_').upper():
            _quoted_string(' '.join(_v.splitlines()))
        for _k, _v in font.get_properties().items()
        if not font.is_known_property(_k)
    }
    xlfd_props.update({
        _k.removeprefix('XLFD.'): _v
        for _k, _v in unparsed.items()
        if _k.startswith('XLFD.')
    })
    # keep unknown properties
    xlfd_props.update({
        _k.removeprefix(f'{CUSTOM_PROP}.'.upper()): _v
        for _k, _v in unparsed.items()
        if not _k.startswith('XLFD.')
    })
    return xlfd_props
