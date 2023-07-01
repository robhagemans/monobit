"""
monobit.formats.windows.fnt - Windows FNT resource

`monobit.formats.windows` is copyright 2019--2023 Rob Hagemans
`mkwinfont` is copyright 2001 Simon Tatham. All rights reserved.
`dewinfont` is copyright 2001,2017 Simon Tatham. All rights reserved.

See `LICENSE.md` in this package's directory.
"""


import io
import string
import logging
import itertools
from types import SimpleNamespace

from ...binary import bytes_to_bits, ceildiv, align
from ...struct import little_endian as le
from ...properties import reverse_dict
from ...magic import FileFormatError
from ...properties import Props
from ...font import Font
from ...glyph import Glyph
from ...raster import Raster
from ...vector import StrokePath

FNT_MAGIC_1 = b'\0\1'
FNT_MAGIC_2 = b'\0\2'
FNT_MAGIC_3 = b'\0\3'


##############################################################################
# windows .FNT format definitions
#
# https://web.archive.org/web/20120215123301/http://support.microsoft.com/kb/65123
# https://ffenc.blogspot.com/2008/04/fnt-font-file-format.html


# fallback values for font file writer
# use OEM charset value; "default" charset 0x01 is not a valid value per freetype docs
_FALLBACK_CHARSET = 0xff
# "dfDefaultChar should indicate a special character in the font which is not a space."
# codepoint 0x80 is unmapped in windows-ansi-2.0 and commonly used for default
_FALLBACK_DEFAULT = 0x80
# "dfBreakChar is normally (32 - dfFirstChar), which is an ASCII space."
_FALLBACK_BREAK = 0x20

# despite the presence of MBCS character set codes,
# FNT can only hold single-byte codepoints
# as firstChar and lastChar are byte-sized
_FNT_RANGE = range(256)

# official but vague documentation:
# https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/0d0b32ac-a836-4bd2-a112-b6000a1b4fc9
#
# The CharacterSet Enumeration defines the possible sets of character glyphs that are defined in fonts for graphics output.
#      typedef  enum
#      {
#        ANSI_CHARSET = 0x00000000,
#        DEFAULT_CHARSET = 0x00000001,
#        SYMBOL_CHARSET = 0x00000002,
#        MAC_CHARSET = 0x0000004D,
#        SHIFTJIS_CHARSET = 0x00000080,
#        HANGUL_CHARSET = 0x00000081,
#        JOHAB_CHARSET = 0x00000082,
#        GB2312_CHARSET = 0x00000086,
#        CHINESEBIG5_CHARSET = 0x00000088,
#        GREEK_CHARSET = 0x000000A1,
#        TURKISH_CHARSET = 0x000000A2,
#        VIETNAMESE_CHARSET = 0x000000A3,
#        HEBREW_CHARSET = 0x000000B1,
#        ARABIC_CHARSET = 0x000000B2,
#        BALTIC_CHARSET = 0x000000BA,
#        RUSSIAN_CHARSET = 0x000000CC,
#        THAI_CHARSET = 0x000000DE,
#        EASTEUROPE_CHARSET = 0x000000EE,
#        OEM_CHARSET = 0x000000FF
#      } CharacterSet;
#
# ANSI_CHARSET: Specifies the English character set.
# DEFAULT_CHARSET: Specifies a character set based on the current system locale; for example, when the system locale is United States English, the default character set is ANSI_CHARSET.
# SYMBOL_CHARSET: Specifies a character set of symbols.
# MAC_CHARSET: Specifies the Apple Macintosh character set.<6>
# SHIFTJIS_CHARSET: Specifies the Japanese character set.
# HANGUL_CHARSET: Also spelled "Hangeul". Specifies the Hangul Korean character set.
# JOHAB_CHARSET: Also spelled "Johap". Specifies the Johab Korean character set.
# GB2312_CHARSET: Specifies the "simplified" Chinese character set for People's Republic of China.
# CHINESEBIG5_CHARSET: Specifies the "traditional" Chinese character set, used mostly in Taiwan and in the Hong Kong and Macao Special Administrative Regions.
# GREEK_CHARSET: Specifies the Greek character set.
# TURKISH_CHARSET: Specifies the Turkish character set.
# VIETNAMESE_CHARSET: Specifies the Vietnamese character set.
# HEBREW_CHARSET: Specifies the Hebrew character set
# ARABIC_CHARSET: Specifies the Arabic character set
# BALTIC_CHARSET: Specifies the Baltic (Northeastern European) character set
# RUSSIAN_CHARSET: Specifies the Russian Cyrillic character set.
# THAI_CHARSET: Specifies the Thai character set.
# EASTEUROPE_CHARSET: Specifies a Eastern European character set.
# OEM_CHARSET: Specifies a mapping to one of the OEM code pages, according to the current system locale setting.

# MS Windows SDK 1.03 Programmer's reference, Appendix C Font Files, p. 427:
#   "One byte specifying the character set defined by this font. The IBM@ PC hardware font has been
#   assigned the designation 377 octal (FF hexadecimal or 255 decimal)."

# below we follow the more useful info at https://www.freetype.org/freetype2/docs/reference/ft2-winfnt_fonts.html
# from freetype freetype/ftwinfnt.h:
#define FT_WinFNT_ID_CP1252    0
#define FT_WinFNT_ID_DEFAULT   1
#define FT_WinFNT_ID_SYMBOL    2
#define FT_WinFNT_ID_MAC      77
#define FT_WinFNT_ID_CP932   128
#define FT_WinFNT_ID_CP949   129
#define FT_WinFNT_ID_CP1361  130
#define FT_WinFNT_ID_CP936   134
#define FT_WinFNT_ID_CP950   136
#define FT_WinFNT_ID_CP1253  161
#define FT_WinFNT_ID_CP1254  162
#define FT_WinFNT_ID_CP1258  163
#define FT_WinFNT_ID_CP1255  177
#define FT_WinFNT_ID_CP1256  178
#define FT_WinFNT_ID_CP1257  186
#define FT_WinFNT_ID_CP1251  204
#define FT_WinFNT_ID_CP874   222
#define FT_WinFNT_ID_CP1250  238
#define FT_WinFNT_ID_OEM     255
# some of their notes:
#   SYMBOL - There is no known mapping table available.
#   OEM - as opposed to ANSI, denotes the second default codepage that most international versions of Windows have.
#         It is one of the OEM codepages from https://docs.microsoft.com/en-us/windows/desktop/intl/code-page-identifiers
#   DEFAULT	- This is used for font enumeration and font creation as a ‘don't care’ value. Valid font files don't contain this value.
#   Exact mapping tables for the various ‘cpXXXX’ encodings (except for ‘cp1361’) can be found at
#   ‘ftp://ftp.unicode.org/Public/’ in the MAPPINGS/VENDORS/MICSFT/WINDOWS subdirectory.
#   ‘cp1361’ is roughly a superset of MAPPINGS/OBSOLETE/EASTASIA/KSC/JOHAB.TXT.
#
CHARSET_MAP = {
    0x00: 'windows-1252',
    # no codepage
    0x01: '',
    0x02: 'windows-symbol',
    0x4d: 'mac-roman',
    0x80: 'windows-932',
    0x81: 'windows-949',
    0x82: 'windows-1361',
    0x86: 'windows-936',
    0x88: 'windows-950',
    0xa1: 'windows-1253',
    0xa2: 'windows-1254',
    0xa3: 'windows-1258',
    0xb1: 'windows-1255',
    0xb2: 'windows-1256',
    0xba: 'windows-1257',
    0xcc: 'windows-1251',
    0xde: 'windows-874',
    0xee: 'windows-1250',
    # could be any OEM codepage
    0xff: '',
}
CHARSET_REVERSE_MAP = reverse_dict(CHARSET_MAP)
CHARSET_REVERSE_MAP.update({
    # different windows versions used different definitions of windows-1252
    # see https://www.aivosto.com/articles/charsets-codepages-windows.html
    'windows-ansi-1.0': 0x00,
    'windows-ansi-2.0': 0x00,
    'windows-ansi-3.1': 0x00,
    'windows-1252': 0x00,
    # windows-1252 agrees with iso-8859-1 (u+0000--u+00ff) except for controls 0x7F-0x9F
    # furthermore, often the control range 0x00-0x19 is set to IBM graphics in windows-1252
    'latin-1': 0x00,
    'unicode': 0x00,
    # use OEM as fallback for undefined as "valid font files don't contain 0x01"
    '': 0xff,
})

# https://web.archive.org/web/20120215123301/http://support.microsoft.com/kb/65123
# dfWeight: 2 bytes specifying the weight of the characters in the character definition data, on a scale of 1 to 1000.
# A dfWeight of 400 specifies a regular weight.
#
# https://docs.microsoft.com/en-gb/windows/desktop/api/wingdi/ns-wingdi-taglogfonta
# The weight of the font in the range 0 through 1000. For example, 400 is normal and 700 is bold.
# If this value is zero, a default weight is used.
# Value	Weight
# FW_DONTCARE	0
# FW_THIN	100
# FW_EXTRALIGHT	200
# FW_ULTRALIGHT	200
# FW_LIGHT	300
# FW_NORMAL	400
# FW_REGULAR	400
# FW_MEDIUM	500
# FW_SEMIBOLD	600
# FW_DEMIBOLD	600
# FW_BOLD	700
# FW_EXTRABOLD	800
# FW_ULTRABOLD	800
# FW_HEAVY	900
# FW_BLACK	900
WEIGHT_MAP = {
    0: '', # undefined/unknown
    100: 'thin', # bdf 'ultra-light' is windows' 'thin'
    200: 'extra-light', # windows 'ultralight' equals 'extralight'
    300: 'light',
    400: 'regular', # 'regular' is 'normal' but less than 'medium' :/ ... bdf has a semi-light here
    500: 'medium',
    600: 'semi-bold',
    700: 'bold',
    800: 'extra-bold', # windows 'ultrabold' equals 'extrabold'
    900: 'heavy', # bdf 'ultra-bold' is 'heavy'
}
WEIGHT_REVERSE_MAP = reverse_dict(WEIGHT_MAP)

# pitch and family
# low bit: 1 - proportional 0 - monospace
# upper bits: family (like bdf add_style_name)
#
# Don't care or don't know.
_FF_DONTCARE = 0<<4
# Proportionally spaced fonts with serifs.
_FF_ROMAN = 1<<4
# Proportionally spaced fonts without serifs.
_FF_SWISS = 2<<4
# Fixed-pitch fonts.
_FF_MODERN = 3<<4
_FF_SCRIPT = 4<<4
_FF_DECORATIVE = 5<<4
# map to yaff styles
_STYLE_MAP = {
    _FF_DONTCARE: '',
    _FF_ROMAN: 'serif',
    _FF_SWISS: 'sans serif',
    _FF_MODERN: 'modern',
    _FF_SCRIPT: 'script',
    _FF_DECORATIVE: 'decorative',
}
_STYLE_REVERSE_MAP = reverse_dict(_STYLE_MAP)

# dfFlags
_DFF_FIXED = 0x01 # font is fixed pitch
_DFF_PROPORTIONAL = 0x02 # font is proportional pitch
_DFF_ABCFIXED = 0x04 # font is an ABC fixed font
_DFF_ABCPROPORTIONAL = 0x08 # font is an ABC proportional font
_DFF_1COLOR = 0x10 # font is one color
_DFF_16COLOR = 0x20 # font is 16 color
_DFF_256COLOR = 0x40 # font is 256 color
_DFF_RGBCOLOR = 0x80 # font is RGB color
# convenience
_DFF_PROP = _DFF_PROPORTIONAL | _DFF_ABCPROPORTIONAL
_DFF_COLORFONT = _DFF_16COLOR | _DFF_256COLOR | _DFF_RGBCOLOR
_DFF_ABC = _DFF_ABCFIXED | _DFF_ABCPROPORTIONAL


# dfType field values
# vector font, else raster
_FNT_TYPE_VECTOR = 0x0001
# font is in ROM
_FNT_TYPE_MEMORY = 0x0004
# 'realised by a device' - maybe printer font?
_FNT_TYPE_DEVICE = 0x0080


# FNT header - the part common to v1.0, v2.0, v3.0
_FNT_HEADER = le.Struct(
    ### this part is also common to FontDirEntry
    dfVersion='word',
    dfSize='dword',
    dfCopyright='60s',
    dfType='word',
    dfPoints='word',
    dfVertRes='word',
    dfHorizRes='word',
    dfAscent='word',
    dfInternalLeading='word',
    dfExternalLeading='word',
    dfItalic='byte',
    dfUnderline='byte',
    dfStrikeOut='byte',
    dfWeight='word',
    dfCharSet='byte',
    dfPixWidth='word',
    dfPixHeight='word',
    dfPitchAndFamily='byte',
    dfAvgWidth='word',
    dfMaxWidth='word',
    dfFirstChar='byte',
    dfLastChar='byte',
    dfDefaultChar='byte',
    dfBreakChar='byte',
    dfWidthBytes='word',
    dfDevice='dword',
    dfFace='dword',
###
    dfBitsPointer='dword',
    dfBitsOffset='dword',
)

# version-specific header extensions
_FNT_HEADER_1 = le.Struct()
_FNT_HEADER_2 = le.Struct(dfReserved='byte')
_FNT_HEADER_3 = le.Struct(
    dfReserved='byte',
    dfFlags='dword',
    dfAspace='word',
    dfBspace='word',
    dfCspace='word',
    dfColorPointer='dword',
    dfReserved1='16s',
)
_FNT_HEADER_EXT = {
    0x100: _FNT_HEADER_1,
    0x200: _FNT_HEADER_2,
    0x300: _FNT_HEADER_3,
}
# total size
# {'0x100': '0x75', '0x200': '0x76', '0x300': '0x94'}
_FNT_HEADER_SIZE = {
    _ver: _FNT_HEADER.size + _header.size
    for _ver, _header in _FNT_HEADER_EXT.items()
}


# GlyphEntry structures for char table
# see e.g. https://web.archive.org/web/20120215123301/http://support.microsoft.com/kb/65123
_GLYPH_ENTRY_1 = le.Struct(
    geOffset='word',
)
_GLYPH_ENTRY_2 = le.Struct(
    geWidth='word',
    geOffset='word',
)
_GLYPH_ENTRY_3 = le.Struct(
    geWidth='word',
    geOffset='dword',
)
# for ABCFIXED and ABCPROPORTIONAL; for reference, not used in v3.00 (i.e. not used at all)
_GLYPH_ENTRY_3ABC = le.Struct(
    geWidth='word',
    geOffset='dword',
    geAspace='dword',
    geBspace='dword',
    geCspace='word',
)
_GLYPH_ENTRY = {
    0x100: _GLYPH_ENTRY_1,
    0x200: _GLYPH_ENTRY_2,
    0x300: _GLYPH_ENTRY_3,
}

# proportional vector font
# these have width and offset swapped compared to the v2 bitmap format
_GLYPH_ENTRY_PVECTOR = le.Struct(
    geOffset='word',
    geWidth='word',
)


##############################################################################
# windows .FNT reader

def convert_win_fnt_resource(data):
    """Convert Windows FNT resource to monobit Font."""
    win_props = _extract_win_props(data)
    properties = _convert_win_props(data, win_props)
    glyphs = _extract_glyphs(data, win_props)
    font = Font(glyphs, **properties)
    font = font.label()
    return font

def _extract_win_props(data):
    """Read the header information in the FNT resource."""
    header = _FNT_HEADER.from_bytes(data)
    try:
        header_ext_type = _FNT_HEADER_EXT[header.dfVersion]
    except KeyError:
        raise FileFormatError(
            'Not a Windows .FNT resource or unsupported version'
            f' (0x{header.dfVersion:04x}).'
        ) from None
    extension = header_ext_type.from_bytes(data, _FNT_HEADER.size)
    win_props = SimpleNamespace(**vars(header), **vars(extension))
    return win_props

def _extract_glyphs(data, win_props):
    """Read a WinFont character table."""
    if win_props.dfType & 1:
        return _extract_vector_glyphs(data, win_props)
    if win_props.dfVersion == 0x100:
        return _extract_glyphs_v1(data, win_props)
    return _extract_glyphs_v2(data, win_props)

def _extract_glyphs_v1(data, win_props):
    """Read a WinFont 1.0 character table."""
    n_chars = win_props.dfLastChar - win_props.dfFirstChar + 1
    if not win_props.dfPixWidth:
        # proportional font
        ct_start = _FNT_HEADER_SIZE[win_props.dfVersion]
        glyph_entry_array = _GLYPH_ENTRY[win_props.dfVersion].array(n_chars+1)
        entries = glyph_entry_array.from_bytes(data, ct_start)
        offsets = [_entry.geOffset for _entry in entries]
    else:
        offsets = [
            win_props.dfPixWidth * _ord
            for _ord in range(n_chars+1)
        ]
    bytewidth = win_props.dfWidthBytes
    offset = win_props.dfBitsOffset
    strikerows = tuple(
        bytes_to_bits(data[offset+_row*bytewidth : offset+(_row+1)*bytewidth])
        for _row in range(win_props.dfPixHeight)
    )
    glyphs = []
    for ord in range(n_chars):
        offset = offsets[ord]
        width = offsets[ord+1] - offset
        if not width:
            continue
        rows = tuple(
            _srow[offset:offset+width]
            for _srow in strikerows
        )
        glyph = Glyph(rows, codepoint=(win_props.dfFirstChar + ord,))
        glyphs.append(glyph)
    return glyphs

def _extract_glyphs_v2(data, win_props):
    """Read a WinFont 2.0 or 3.0 character table."""
    n_chars = win_props.dfLastChar - win_props.dfFirstChar + 1
    glyph_entry_array = _GLYPH_ENTRY[win_props.dfVersion].array(n_chars)
    ct_start = _FNT_HEADER_SIZE[win_props.dfVersion]
    glyphs = []
    height = win_props.dfPixHeight
    entries = glyph_entry_array.from_bytes(data, ct_start)
    for ord, entry in enumerate(entries, win_props.dfFirstChar):
        # don't store empty glyphs but count them for ordinals
        if not entry.geWidth:
            continue
        bytewidth = ceildiv(entry.geWidth, 8)
        # transpose byte-columns to contiguous rows
        glyph_data = bytes(
            data[entry.geOffset + _col * height + _row]
            for _row in range(height)
            for _col in range(bytewidth)
        )
        glyph = Glyph.from_bytes(glyph_data, entry.geWidth).modify(codepoint=(ord,))
        glyphs.append(glyph)
    return glyphs


def _extract_vector_glyphs(data, win_props):
    """Read a vector character table."""
    n_chars = win_props.dfLastChar - win_props.dfFirstChar + 1
    ct_start = _FNT_HEADER_SIZE[win_props.dfVersion]
    if not win_props.dfPixWidth:
        # proportional font
        # always 2x2 bytes for prop. vector
        glyph_entry_array = _GLYPH_ENTRY_PVECTOR.array(n_chars+1)
    else:
        # fixed-width vector font
        glyph_entry_array = _GLYPH_ENTRY_1.array(n_chars+1)
    entries = glyph_entry_array.from_bytes(data, ct_start)
    offsets = tuple(_entry.geOffset for _entry in entries)
    if not win_props.dfPixWidth:
        widths = tuple(_entry.geWidth for _entry in entries)
    else:
        widths = tuple(win_props.dfPixWidth) * (n_chars+1)
    offset = win_props.dfBitsOffset
    glyphbytes = tuple(
        data[offset+_offset:offset+_next]
        for _offset, _next in zip(offsets, offsets[1:])
    )
    glyphdata = tuple(
        Props(codepoint=_cp, width=_w, code=_b)
        for _cp, (_w, _b) in enumerate(
            zip(widths, glyphbytes),
            win_props.dfFirstChar
        )
    )
    return _convert_vector_glyphs(glyphdata, win_props)


def _convert_vector_glyphs(glyphdata, win_props):
    """Convert a vector character table to paths."""
    glyphs = []
    for i, glyphrec in enumerate(glyphdata):
        # \x80 (-128) is the pen-up sentinel
        # all other bytes form signed int8 coordinate pairs
        code = le.int8.array(len(glyphrec.code)).from_bytes(glyphrec.code)
        it = iter(code)
        ink = StrokePath.LINE
        path = []
        for x in it:
            if x == -128:
                ink = StrokePath.MOVE
                continue
            try:
                y = next(it)
            except StopIteration:
                logging.warning('Vector glyph has truncated path definition')
                break
            path.append((ink, x, y))
            ink = StrokePath.LINE
        # Windows uses top-left coordinates
        path = StrokePath(path).flip().shift(0, win_props.dfAscent)
        glyphs.append(Glyph.from_path(
            path, advance_width=glyphrec.width, codepoint=glyphrec.codepoint
        ))
    return glyphs


def bytes_to_str(s, encoding='latin-1'):
    """Extract null-terminated string from bytes."""
    s, _, _ = s.partition(b'\0')
    return s.decode(encoding, errors='replace')

def _convert_win_props(data, win_props):
    """Convert WinFont properties to yaff properties."""
    version = win_props.dfVersion
    vector = win_props.dfType & 1
    if vector:
        logging.info('This is a vector font')
    logging.info('Windows FNT properties:')
    for key, value in win_props.__dict__.items():
        logging.info('    {}: {}'.format(key, value))
    properties = {
        'source_format': 'Windows FNT v{}.{}'.format(*divmod(version, 256)),
        'family': bytes_to_str(data[win_props.dfFace:]),
        'copyright': bytes_to_str(win_props.dfCopyright),
        'point_size': win_props.dfPoints,
        'slant': 'italic' if win_props.dfItalic else 'roman',
        # Windows dfAscent means distance between matrix top and baseline
        # and it calls the space where accents go the dfInternalLeading
        # which is specified to be 'inside the bounds set by dfPixHeight'
        'ascent': win_props.dfAscent - win_props.dfInternalLeading,
        # the dfPixHeight is the 'height of the character bitmap', i.e. our raster-size.y
        # and dfAscent is the distance between the raster top and the baseline,
        'descent': win_props.dfPixHeight - win_props.dfAscent,
        # dfExternalLeading is the 'amount of extra leading ... the application add between rows'
        'line_height': win_props.dfPixHeight + win_props.dfExternalLeading,
        'default_char': win_props.dfDefaultChar + win_props.dfFirstChar,
    }
    if not vector:
        # vector font determines shift-up (which only applies to raster) from path
        properties['shift_up'] = -properties['descent']
    if win_props.dfPixWidth:
        properties['spacing'] = 'character-cell'
    else:
        properties['spacing'] = 'proportional'
        # this can be extracted from the font - will be dropped if consistent
        # Windows documentation defines this as 'width of the character "X."'
        # for 1.0 system fonts, it is consistent with the advance width of LATIN CAPITAL LETTER X.
        # for 2.0+ system fonts, this appears to be set to the average advance width.
        # fontforge follows the "new" definition while mkwinfont follows the "old".
        # we'll make it depend on the version
        if version == 0x100:
            properties['cap_width'] = win_props.dfAvgWidth
        else:
            properties['average_width'] = win_props.dfAvgWidth
    # check prop/fixed flag
    if bool(win_props.dfPitchAndFamily & 1) == bool(win_props.dfPixWidth):
        logging.warning(
            'Inconsistent spacing properties: dfPixWidth=={} dfPitchAndFamily=={:04x}'.format(
                win_props.dfPixWidth, win_props.dfPitchAndFamily
            )
        )
    properties['dpi'] = (win_props.dfHorizRes, win_props.dfVertRes)
    deco = []
    if win_props.dfUnderline:
        deco.append('underline')
    if win_props.dfStrikeOut:
        deco.append('strikethrough')
    if deco:
        properties['decoration'] = ' '.join(deco)
    weight = win_props.dfWeight
    if weight:
        weight = max(100, min(900, weight))
        properties['weight'] = WEIGHT_MAP.get(round(weight, -2), None)
    charset = win_props.dfCharSet
    if charset in CHARSET_MAP:
        properties['encoding'] = CHARSET_MAP[charset]
    else:
        properties['windows.dfCharSet'] = str(charset)
    properties['style'] = _STYLE_MAP.get(win_props.dfPitchAndFamily & 0xff00, None)
    if win_props.dfBreakChar:
        properties['word_boundary'] = win_props.dfFirstChar + win_props.dfBreakChar
    properties['device'] = bytes_to_str(data[win_props.dfDevice:])
    # unparsed properties: dfMaxWidth - but this can be calculated from the matrices
    if version == 0x300:
        # https://github.com/letolabs/fontforge/blob/master/fontforge/winfonts.c
        # /* These fields are not present in 2.0 and are not meaningful in 3.0 */
        # /*  they are there for future expansion */
        # yet another prop/fixed flag
        if bool(win_props.dfFlags & _DFF_PROP) != (win_props.dfPixWidth == 0):
            logging.warning(
                'Inconsistent spacing properties: dfPixWidth=={} dfFlags=={:04x}'.format(
                    win_props.dfPixWidth, win_props.dfFlags
                )
            )
        # https://web.archive.org/web/20120215123301/http://support.microsoft.com/kb/65123
        # NOTE: The only formats supported in Windows 3.0 will be DFF_FIXED and DFF_PROPORTIONAL.
        if win_props.dfFlags & _DFF_COLORFONT:
            raise FileFormatError('ColorFont not supported')
        if win_props.dfFlags & _DFF_ABC:
            # https://ffenc.blogspot.com/2008/04/fnt-font-file-format.html
            # For Windows 3.00, the font-file header includes six new fields:
            # dFlags, dfAspace, dfBspace, dfCspace, dfColorPointer, and dfReserved1.
            # These fields are not used in Windows 3.00. To ensure compatibility with future
            # versions of Windows, these fields should be set to zero.
            raise FileFormatError('ABC spacing properties not supported')
    return properties


##############################################################################
# windows .FNT writer


def _make_contiguous(font):
    """Fill out a contiguous range of glyphs."""
    # x_width should equal average width
    # this is 0 for proportional fonts
    pix_width = font.cell_size.x
    # blank glyph of standard size
    blank = Glyph.blank(pix_width, font.raster_size.y)
    # char table; we need a contiguous range between the min and max codepoints
    codepoints = font.get_codepoints()
    ord_glyphs = [
        font.get_glyph(_codepoint, missing=blank)
        for _codepoint in range(min(codepoints)[0], max(codepoints)[0]+1)
    ]
    # add the guaranteed-blank glyph
    ord_glyphs.append(blank)
    font = font.modify(ord_glyphs)
    return font


def create_fnt(font, version=0x200, vector=False):
    """Create .FNT from monobit font."""
    # ensure codepoint values are set, if possible
    font = font.label(codepoint_from=font.encoding)
    # only include single-byte encoded glyphs
    # as firstChar and lastChar are byte-sized
    font = font.subset(codepoints=_FNT_RANGE)
    font = _make_contiguous(font)
    # bring to equal-height, equal-upshift, padded normal form
    font = font.equalise_horizontal()
    bitmaps, char_table, offset_bitmaps, byte_width = _convert_to_fnt_glyphs(
        font, version, vector
    )
    bitmap_size = sum(len(_b) for _b in bitmaps)
    win_props, header_ext, stringtable = _convert_to_fnt_props(
        font, version, vector,
        offset_bitmaps, bitmap_size, byte_width,
    )
    data = (
        bytes(win_props) + bytes(header_ext)
        + b''.join(char_table)
        + b''.join(bitmaps)
        + b''.join(stringtable)
    )
    return data


def _convert_to_fnt_props(
        font, version, vector,
        offset_bitmaps, bitmap_size, byte_width,
    ):
    """Convert font to FNT headers."""
    upshifts = set(_g.shift_up for _g in font.glyphs)
    shift_up, *remainder = upshifts
    assert not remainder
    # get lowest and highest codepoints (contiguous glyphs followed by blank)
    min_ord = font.glyphs[0].codepoint[0]
    max_ord = font.glyphs[-2].codepoint[0]
    # if encoding is compatible, use it; otherwise set to fallback value
    charset = CHARSET_REVERSE_MAP.get(font.encoding, _FALLBACK_CHARSET)
    default = font.get_glyph(font.default_char, missing='empty').codepoint
    if len(default) == 1:
        default_ord, = default
    else:
        default_ord = _FALLBACK_DEFAULT
    word_break = font.get_glyph(font.word_boundary, missing='empty').codepoint
    if len(word_break) == 1:
        break_ord, = word_break
    else:
        break_ord = _FALLBACK_BREAK
    if font.spacing == 'proportional' or vector:
        # low bit set for proportional
        pitch_and_family = 0x01 | _STYLE_REVERSE_MAP.get(font.style, 0)
        v3_flags = _DFF_PROPORTIONAL
        pix_width = 0
    else:
        # CHECK: is this really always set for fixed-pitch?
        pitch_and_family = _FF_MODERN
        v3_flags = _DFF_FIXED
        # x_width should equal average width
        pix_width = font.raster_size.x
    # add name and device strings
    face_name_offset = offset_bitmaps + bitmap_size
    face_name = font.family.encode('latin-1', 'replace') + b'\0'
    device_name_offset = face_name_offset + len(face_name)
    device_name = font.device.encode('latin-1', 'replace') + b'\0'
    file_size = device_name_offset + len(device_name)
    # set device name pointer to zero for 'generic font'
    if not device_name or device_name == b'\0':
        device_name_offset = 0
    try:
        weight = WEIGHT_REVERSE_MAP[font.weight]
    except KeyError:
        logging.warning(
            f'Weight `{font.weight}` not supported by Windows FNT resource format, '
            '`regular` will be used instead.'
        )
        weight = WEIGHT_REVERSE_MAP['regular']
    # create FNT file
    win_props = _FNT_HEADER(
        dfVersion=version,
        dfSize=file_size,
        dfCopyright=font.copyright.encode('ascii', 'replace')[:60].ljust(60, b'\0'),
        dfType=1 if vector else 0,
        dfPoints=int(font.point_size),
        dfVertRes=font.dpi.y,
        dfHorizRes=font.dpi.x,
        # Windows dfAscent means distance between matrix top and baseline
        # common shift_up is negative or zero in padded normal form
        dfAscent=font.raster_size.y + shift_up,
        #'ascent': win_props.dfAscent - win_props.dfInternalLeading,
        dfInternalLeading=font.raster_size.y + shift_up - font.ascent,
        #'line_height': win_props.dfPixHeight + win_props.dfExternalLeading,
        dfExternalLeading=font.line_height-font.raster_size.y,
        dfItalic=(font.slant in ('italic', 'oblique')),
        dfUnderline=('underline' in font.decoration),
        dfStrikeOut=('strikethrough' in font.decoration),
        dfWeight=WEIGHT_REVERSE_MAP.get(
            font.weight, WEIGHT_REVERSE_MAP['regular']
        ),
        dfCharSet=charset,
        dfPixWidth=pix_width,
        dfPixHeight=font.raster_size.y,
        dfPitchAndFamily=pitch_and_family,
        # for 2.0+, we use actual average advance here (like fontforge but unlike mkwinfont)
        dfAvgWidth=round(font.average_width),
        # max advance width
        dfMaxWidth=font.max_width,
        dfFirstChar=min_ord,
        dfLastChar=max_ord,
        dfDefaultChar=default_ord - min_ord,
        dfBreakChar=break_ord - min_ord,
        # strike width in bytes. not used for vector. (not used for v2.0+ ?)
        dfWidthBytes=byte_width,
        dfDevice=device_name_offset,
        dfFace=face_name_offset,
        dfBitsPointer=0, # used on loading
        dfBitsOffset=offset_bitmaps,
    )
    # version-specific header extension
    header_ext = _FNT_HEADER_EXT[version]()
    if version == 0x300:
        # all are zeroes (default) except the flags for v3
        header_ext.dfFlags = v3_flags
    stringtable = face_name, device_name
    return win_props, header_ext, stringtable


def _convert_to_fnt_glyphs(font, version, vector):
    """Convert glyphs to FNT bitmaps and offset tables."""
    if vector:
        upshifts = set(_g.shift_up for _g in font.glyphs)
        shift_up, *remainder = upshifts
        assert not remainder
        # vector glyph data
        # this should equal the dfAscent value
        win_ascent = font.raster_size.y + shift_up
        bitmaps = _convert_vector_glyphs_to_fnt(font.glyphs, win_ascent)
        byte_width = 0
    elif version == 0x100:
        strike = Raster.concatenate(*(_g.pixels for _g in font.glyphs))
        # spacer to ensure we'll be word-aligned (as_bytes will byte-align)
        spacer = Raster.blank(width=16-(strike.width%16), height=strike.height)
        strike = Raster.concatenate(strike, spacer)
        bitmaps = (strike.as_bytes(),)
        byte_width = ceildiv(strike.width, 8)
    else:
        # create the bitmaps
        bitmaps = (_glyph.as_bytes() for _glyph in font.glyphs)
        # bytewise transpose - .FNT stores as contiguous 8-pixel columns
        bitmaps = tuple(
            b''.join(
                _bm[_col::len(_bm)//_glyph.height]
                for _col in range(len(_bm)//_glyph.height)
            )
            for _glyph, _bm in zip(font.glyphs, bitmaps)
        )
        # not sure if this gets used for v2, as it isn't really useful there
        # using the logic from mkwinfont, max bytewidth aligned to multiple of 2
        byte_width = ceildiv(max(_g.width for _g in font.glyphs), 8)
        byte_width = align(byte_width, 1)
    if version == 0x100 and not vector:
        glyph_offsets = [0] + list(
            itertools.accumulate(_g.width for _g in font.glyphs)
        )
    else:
        glyph_offsets = [0] + list(
            itertools.accumulate(len(_bm) for _bm in bitmaps)
        )
    base_offset = _FNT_HEADER.size + _FNT_HEADER_EXT[version].size
    if not vector:
        glyph_entry = _GLYPH_ENTRY[version]
    else:
        glyph_entry = _GLYPH_ENTRY_PVECTOR
    # vector format and v1 do not include dfBitmapOffset in the table
    glyph_table_size = len(font.glyphs) * glyph_entry.size
    if version == 0x100 and font.spacing == 'character-cell':
        char_table = (b'',)
        offset_bitmaps = base_offset
    elif vector or version == 0x100:
        char_table = (
            bytes(glyph_entry(
                geWidth=_glyph.width,
                geOffset=_glyph_offset
            ))
            for _glyph, _glyph_offset in zip(font.glyphs, glyph_offsets)
        )
        offset_bitmaps = base_offset + glyph_table_size
    else:
        offset_bitmaps = base_offset + glyph_table_size
        char_table = (
            bytes(glyph_entry(
                geWidth=_glyph.width,
                geOffset=offset_bitmaps + _glyph_offset
            ))
            for _glyph, _glyph_offset in zip(font.glyphs, glyph_offsets)
        )
    return bitmaps, char_table, offset_bitmaps, byte_width


def _convert_vector_glyphs_to_fnt(glyphs, win_ascent):
    """Convert paths to a vector character table."""
    glyphdata = []
    for glyph in glyphs:
        path = glyph.path.shift(0, -win_ascent).flip()
        code = (
            (-128, _x, _y) if _ink == StrokePath.MOVE else (_x, _y)
            for _ink, _x, _y in path.as_moves()
        )
        code = tuple(_b for _tuple in code for _b in _tuple)
        code = le.int8.array(len(code))(*code)
        glyphdata.append(bytes(code))
    return glyphdata
