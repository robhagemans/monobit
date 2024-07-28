"""
monobit.storage.formats.common - tables common to various formats

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import reverse_dict
from monobit.encoding import EncodingName


###############################################################################
# Windows charset values

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
CHARSET_REVERSE_MAP = {
    EncodingName(_k): _v
    for _k, _v in CHARSET_REVERSE_MAP.items()
}


###############################################################################
# Windows weight values

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


###############################################################################
# Mac encoding values

# based on:
# [1] Apple Technotes (As of 2002)/te/te_02.html
# [2] https://developer.apple.com/library/archive/documentation/mac/Text/Text-367.html#HEADING367-0
MAC_ENCODING = {
    0: 'mac-roman',
    1: 'mac-japanese',
    2: 'mac-trad-chinese',
    3: 'mac-korean',
    4: 'mac-arabic',
    5: 'mac-hebrew',
    6: 'mac-greek',
    7: 'mac-cyrillic', # [1] russian
    # 8: [2] right-to-left symbols
    9: 'mac-devanagari',
    10: 'mac-gurmukhi',
    11: 'mac-gujarati',
    21: 'mac-thai',
    23: 'mac-georgian',
    24: 'mac-armenian',
    25: 'mac-simp-chinese', # [1] maldivian
    29: 'mac-centraleurope', # [1] non-cyrillic slavic
    # I don't have a codepage for the following Apple scripts
    # - as Gurmukhi and Gujarati are ISCII-based
    # perhaps we can infer the other ISCII scripts?
    12: 'mac-oriya',
    13: 'mac-bengali',
    14: 'mac-tamil',
    15: 'mac-telugu',
    16: 'mac-kannada',
    17: 'mac-malayalam',
    18: 'mac-sinhalese',
    19: 'mac-burmese',
    20: 'mac-khmer',
    22: 'mac-laotian',
    26: 'mac-tibetan',
    27: 'mac-mongolian',
    28: 'mac-ethiopic', # [2] == geez
    30: 'mac-vietnamese',
    31: 'mac-sindhi', # [2] == ext-arabic
    #32: [1] [2] 'uninterpreted symbols'
}


###############################################################################
# Mac style values

# interpretation of head.macStyle flags
STYLE_MAP = {
    0: 'bold',
    1: 'italic',
    2: 'underline',
    3: 'outline',
    4: 'shadow',
    5: 'condensed',
    6: 'extended',
}

def mac_style_name(font_style):
    """Get human-readable representation of font style."""
    return ' '.join(
        _tag for _bit, _tag in STYLE_MAP.items() if font_style & (1 << _bit)
    )


###############################################################################
# PostScript name

def to_postscript_name(name):
    """Postscript name must be printable ascii, no [](){}<>/%, max 63 chars."""
    ps_name = ''.join(
        _c if _c.isalnum() and _c.isascii() else '-'
        for _c in name
    )
    ps_name = ps_name[:63]
    # expected to be Title-Cased (at least on Mac, see FontForge code comments)
    return ps_name.title()
