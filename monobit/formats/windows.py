"""
monobit.formats.windows - windows 1.x, 2.x and 3.x .FON and .FNT files

based on Simon Tatham's dewinfont; see MIT-style licence below.
changes (c) 2019--2022 Rob Hagemans and released under the same licence.

dewinfont is copyright 2001,2017 Simon Tatham. All rights reserved.

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import string
import logging
import itertools

from ..binary import bytes_to_bits, ceildiv, align
from ..struct import reverse_dict, little_endian as le
from .. import struct
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font, Coord
from ..glyph import Glyph


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
_WEIGHT_MAP = {
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


##############################################################################
# MZ (DOS) executable headers

_STUB_MSG = b'This is a Windows font file.\r\n'

# stub 16-bit DOS executable
_STUB_CODE = bytes((
    0xBA, 0x0E, 0x00, # mov dx,0xe
    0x0E,             # push cs
    0x1F,             # pop ds
    0xB4, 0x09,       # mov ah,0x9
    0xCD, 0x21,       # int 0x21
    0xB8, 0x01, 0x4C, # mov ax,0x4c01
    0xCD, 0x21        # int 0x21
))

# DOS executable (MZ) header
_MZ_HEADER = le.Struct(
    # EXE signature, 'MZ' or 'ZM'
    magic='2s',
    # number of bytes in last 512-byte page of executable
    last_page_length='H',
    # total number of 512-byte pages in executable
    num_pages='H',
    num_relocations='H',
    header_size='H',
    min_allocation='H',
    max_allocation='H',
    initial_ss='H',
    initial_sp='H',
    checksum='H',
    initial_csip='L',
    relocation_table_offset='H',
    overlay_number='H',
    reserved_0='4s',
    behavior_bits='H',
    reserved_1='26s',
    # NE offset is at 0x3c
    ne_offset='L',
)

##############################################################################
# NE (16-bit) executable structures

# align on 16-byte (1<<4) boundaries
_ALIGN_SHIFT = 4

# Windows executable (NE) header
_NE_HEADER = le.Struct(
    magic='2s',
    linker_major_version='B',
    linker_minor_version='B',
    entry_table_offset='H',
    entry_table_length='H',
    file_load_crc='L',
    program_flags='B',
    application_flags='B',
    auto_data_seg_index='H', # says 1 byte in table, but offsets make it clear it should be 2 bytes
    initial_heap_size='H',
    initial_stack_size='H',
    entry_point_csip='L',
    initial_stack_pointer_sssp='L',
    segment_count='H',
    module_ref_count='H',
    nonresident_names_table_size='H',
    seg_table_offset='H',
    res_table_offset='H',
    resident_names_table_offset='H',
    module_ref_table_offset='H',
    imp_names_table_offset='H',
    nonresident_names_table_offset='L',
    movable_entry_point_count='H',
    file_alignment_size_shift_count='H',
    number_res_table_entries='H',
    target_os='B',
    other_os2_exe_flags='B',
    return_thunks_offset='H',
    seg_ref_thunks_offset='H',
    min_code_swap_size='H',
    expected_windows_version='H',
)

# TYPEINFO structure and components

_NAMEINFO = le.Struct(
    rnOffset='word',
    rnLength='word',
    rnFlags='word',
    rnID='word',
    rnHandle='word',
    rnUsage='word',
)

def type_info_struct(rtResourceCount=0):
    """TYPEINFO structure."""
    return le.Struct(
        rtTypeID='word',
        rtResourceCount='word',
        rtReserved='dword',
        rtNameInfo=_NAMEINFO * rtResourceCount
    )

# type ID values that matter to us
# https://docs.microsoft.com/en-us/windows/desktop/menurc/resource-types
_RT_FONTDIR = 0x8007
_RT_FONT = 0x8008

# resource table structure (fixed head only)
_RES_TABLE_HEAD = le.Struct(
    rscAlignShift='word',
    #rscTypes=[type_info ...],
    #rscEndTypes='word',
    #rscResourceNames=struct.char * len_names,
    #rscEndNames='byte'
)

# https://docs.microsoft.com/en-us/windows/desktop/menurc/direntry
# this is immediately followed by FONTDIRENTRY
# https://docs.microsoft.com/en-us/windows/desktop/menurc/fontdirentry
# which is just a copy of part of the FNT header, plus name and device
_DIRENTRY = le.Struct(
    fontOrdinal='word',
)

# default module name in resident names table
_MODULE_NAME = b'FONTLIB'


##############################################################################
# PE (32-bit) executable structures

# PE header (winnt.h _IMAGE_FILE_HEADER)
_PE_HEADER = le.Struct(
    # PE\0\0 magic:
    Signature='4s',
    # struct _IMAGE_FILE_HEADER:
    Machine='word',
    NumberOfSections='word',
    TimeDateStamp='dword',
    PointerToSymbolTable='dword',
    NumberOfSymbols='dword',
    SizeOfOptionalHeader='word',
    Characteristics='word',
    # followed by the non-optional Optional Header
    # which we don't care about for now
)

_IMAGE_SECTION_HEADER = le.Struct(
    Name='8s',
    VirtualSize='dword',
    VirtualAddress='dword',
    SizeOfRawData='dword',
    PointerToRawData='dword',
    PointerToRelocations='dword',
    PointerToLinenumbers='dword',
    NumberOfRelocations='word',
    NumberOfLinenumbers='word',
    Characteristics='dword',
)

_IMAGE_RESOURCE_DIRECTORY = le.Struct(
    Characteristics='dword',
    TimeDateStamp='dword',
    MajorVersion='word',
    MinorVersion='word',
    NumberOfNamedEntries='word',
    NumberOfIdEntries='word',
)
_IMAGE_RESOURCE_DIRECTORY_ENTRY = le.Struct(
    Id='dword', # technically a union with NameOffset, but meh
    OffsetToData='dword', # or OffsetToDirectory, if high bit set
)

_ID_FONTDIR = 0x07
_ID_FONT = 0x08

_IMAGE_RESOURCE_DATA_ENTRY = le.Struct(
    OffsetToData='dword',
    Size='dword',
    CodePage='dword',
    Reserved='dword',
)


##############################################################################
# top level functions

@loaders.register(
    #'fnt',
    magic=(b'\0\x01', b'\0\x02', b'\0\x03'),
    name='win-fnt',
)
def load_win_fnt(instream, where=None):
    """Load font from a Windows .FNT resource."""
    font = parse_fnt(instream.read())
    return font

@savers.register(linked=load_win_fnt)
def save_win_fnt(fonts, outstream, where=None, version:int=2):
    """
    Save font to a Windows .FNT resource.

    version: Windows font format version
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to Windows font resource.')
    font = fonts[0]
    outstream.write(create_fnt(font, version*0x100))
    return font


@loaders.register(
    'fon',
    magic=(b'MZ',),
    name='win-fon',
)
def load_win_fon(instream, where=None):
    """Load fonts from a Windows .FON container."""
    data = instream.read()
    mz_header = _MZ_HEADER.from_bytes(data)
    if mz_header.magic not in (b'MZ', b'ZM'):
        raise FileFormatError('MZ signature not found. Not a Windows .FON file')
    ne_magic = data[mz_header.ne_offset:mz_header.ne_offset+2]
    if ne_magic == b'NE':
        fonts = _parse_ne(data, mz_header.ne_offset)
    elif ne_magic == b'PE':
        # PE magic should be padded by \0\0 but I'll believe it at this stage
        fonts = _parse_pe(data, mz_header.ne_offset)
    else:
        raise FileFormatError(
            'Executable signature is `{}`, not NE or PE. Not a Windows .FON file'.format(
                ne_magic.decode('latin-1', 'replace')
            )
        )
    fonts = [
        font.modify(
            source_format=font.source_format+' ({} FON container)'.format(ne_magic.decode('ascii'))
        )
        for font in fonts
    ]
    return fonts

@savers.register(linked=load_win_fon)
def save_win_fon(fonts, outstream, where=None, version:int=2):
    """
    Save fonts to a Windows .FON container.

    version: Windows font format version
    """
    outstream.write(_create_fon(fonts, version*0x100))


##############################################################################

##############################################################################
# windows .FNT reader

def parse_fnt(fnt):
    """Create an internal font description from a .FNT-shaped string."""
    win_props = _parse_header(fnt)
    properties = _parse_win_props(fnt, win_props)
    glyphs = _parse_chartable(fnt, win_props)
    font = Font(glyphs, **properties)
    font = font.label(_record=False)
    return font

def _parse_header(fnt):
    """Read the header information in the FNT resource."""
    win_props = _FNT_HEADER.from_bytes(fnt)
    try:
        header_ext = _FNT_HEADER_EXT[win_props.dfVersion]
    except KeyError:
        raise ValueError(
            f'Not a Windows .FNT resource or unsupported version (0x{win_props.dfVersion:04x}).'
            ) from None
    win_props += header_ext.from_bytes(fnt, _FNT_HEADER.size)
    return win_props

def _parse_chartable(fnt, win_props):
    """Read a WinFont character table."""
    if win_props.dfVersion == 0x100:
        return _parse_chartable_v1(fnt, win_props)
    return _parse_chartable_v2(fnt, win_props)

def _parse_chartable_v1(fnt, win_props):
    """Read a WinFont 1.0 character table."""
    n_chars = win_props.dfLastChar - win_props.dfFirstChar + 1
    if not win_props.dfPixWidth:
        # proportional font
        ct_start = _FNT_HEADER_SIZE[win_props.dfVersion]
        glyph_entry_array = _GLYPH_ENTRY[win_props.dfVersion].array(n_chars+1)
        entries = glyph_entry_array.from_bytes(fnt, ct_start)
        offsets = [_entry.geOffset for _entry in entries]
    else:
        offsets = [
            win_props.dfPixWidth * _ord
            for _ord in range(n_chars+1)
        ]
    bytewidth = win_props.dfWidthBytes
    offset = win_props.dfBitsOffset
    strikerows = tuple(
        bytes_to_bits(fnt[offset+_row*bytewidth : offset+(_row+1)*bytewidth])
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
        glyphs.append(Glyph(rows, codepoint=(win_props.dfFirstChar + ord,)))
    return glyphs

def _parse_chartable_v2(fnt, win_props):
    """Read a WinFont 2.0 or 3.0 character table."""
    n_chars = win_props.dfLastChar - win_props.dfFirstChar + 1
    glyph_entry_array = _GLYPH_ENTRY[win_props.dfVersion].array(n_chars)
    ct_start = _FNT_HEADER_SIZE[win_props.dfVersion]
    glyphs = []
    height = win_props.dfPixHeight
    entries = glyph_entry_array.from_bytes(fnt, ct_start)
    for ord, entry in enumerate(entries, win_props.dfFirstChar):
        # don't store empty glyphs but count them for ordinals
        if not entry.geWidth:
            continue
        bytewidth = ceildiv(entry.geWidth, 8)
        # transpose byte-columns to contiguous rows
        glyph_data = bytes(
            fnt[entry.geOffset + _col * height + _row]
            for _row in range(height)
            for _col in range(bytewidth)
        )
        glyph = Glyph.from_bytes(glyph_data, entry.geWidth).modify(codepoint=(ord,))
        glyphs.append(glyph)
    return glyphs

def bytes_to_str(s, encoding='latin-1'):
    """Extract null-terminated string from bytes."""
    if b'\0' in s:
        s, _ = s.split(b'\0', 1)
    return s.decode(encoding, errors='replace')

def _parse_win_props(fnt, win_props):
    """Convert WinFont properties to yaff properties."""
    version = win_props.dfVersion
    if win_props.dfType & 1:
        raise ValueError('Not a bitmap font')
    logging.info('Windows FNT properties:')
    for key, value in win_props.__dict__.items():
        logging.info('    {}: {}'.format(key, value))
    properties = {
        'source-format': 'Windows FNT v{}.{}'.format(*divmod(version, 256)),
        'family': bytes_to_str(fnt[win_props.dfFace:]),
        'copyright': bytes_to_str(win_props.dfCopyright),
        'point-size': win_props.dfPoints,
        'slant': 'italic' if win_props.dfItalic else 'roman',
        # Windows dfAscent means distance between matrix top and baseline
        # and it calls the space where accents go the dfInternalLeading
        # which is specified to be 'inside the bounds set by dfPixHeight'
        'ascent': win_props.dfAscent - win_props.dfInternalLeading,
        # the dfPixHeight is the 'height of the character bitmap', i.e. our raster-size.y
        # and dfAscent is the distance between the raster top and the baseline,
        #'descent': win_props.dfPixHeight - win_props.dfAscent,
        'shift-up': win_props.dfAscent - win_props.dfPixHeight,
        # dfExternalLeading is the 'amount of extra leading ... the application add between rows'
        'line-height': win_props.dfPixHeight + win_props.dfExternalLeading,
        'default-char': win_props.dfDefaultChar + win_props.dfFirstChar,
    }
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
            properties['cap-width'] = win_props.dfAvgWidth
        else:
            properties['average-width'] = win_props.dfAvgWidth
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
        properties['weight'] = _WEIGHT_MAP[round(weight, -2)]
    charset = win_props.dfCharSet
    if charset in CHARSET_MAP:
        properties['encoding'] = CHARSET_MAP[charset]
    else:
        properties['windows.dfCharSet'] = str(charset)
    properties['style'] = _STYLE_MAP[win_props.dfPitchAndFamily & 0xff00]
    if win_props.dfBreakChar:
        properties['word-boundary'] = win_props.dfFirstChar + win_props.dfBreakChar
    properties['device'] = bytes_to_str(fnt[win_props.dfDevice:])
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
            raise ValueError('ColorFont not supported')
        if win_props.dfFlags & _DFF_ABC:
            # https://ffenc.blogspot.com/2008/04/fnt-font-file-format.html
            # For Windows 3.00, the font-file header includes six new fields:
            # dFlags, dfAspace, dfBspace, dfCspace, dfColorPointer, and dfReserved1.
            # These fields are not used in Windows 3.00. To ensure compatibility with future
            # versions of Windows, these fields should be set to zero.
            raise ValueError('ABC spacing properties not supported')
    return properties


##############################################################################
# .FON (NE executable) file reader

def _parse_ne(data, ne_offset):
    """Parse an NE-format FON file."""
    header = _NE_HEADER.from_bytes(data, ne_offset)
    # parse the first elements of the resource table
    res_table = _RES_TABLE_HEAD.from_bytes(data, ne_offset+header.res_table_offset)
    # loop over the rest of the resource table until exhausted - we don't know the number of entries
    fonts = []
    # skip over rscAlignShift word
    ti_offset = ne_offset + header.res_table_offset + _RES_TABLE_HEAD.size
    while True:
        # parse typeinfo excluding nameinfo array (of as yet unknown size)
        type_info_head = type_info_struct(0)
        type_info = type_info_head.from_bytes(data, ti_offset)
        if type_info.rtTypeID == 0:
            # end of resource table
            break
        # type, count, 4 bytes reserved
        nameinfo_array = _NAMEINFO.array(type_info.rtResourceCount)
        for name_info in nameinfo_array.from_bytes(data, ti_offset + type_info_head.size):
            # the are offsets w.r.t. the file start, not the NE header
            # they could be *before* the NE header for all we know
            start = name_info.rnOffset << res_table.rscAlignShift
            size = name_info.rnLength << res_table.rscAlignShift
            if start < 0 or size < 0 or start + size > len(data):
                raise ValueError('Resource overruns file boundaries')
            if type_info.rtTypeID == _RT_FONT:
                try:
                    fonts.append(parse_fnt(data[start : start+size]))
                except ValueError as e:
                    # e.g. not a bitmap font
                    # don't raise exception so we can continue with other resources
                    logging.error('Failed to read font resource at {:x}: {}'.format(start, e))
        # rtResourceCount * 12
        ti_offset += type_info_head.size + nameinfo_array.size
    return fonts


##############################################################################
# .FON (PE executable) file reader
#
# https://docs.microsoft.com/en-gb/windows/desktop/Debug/pe-format
# https://github.com/deptofdefense/SalSA/wiki/PE-File-Format
# https://source.winehq.org/source/include/winnt.h

def _parse_pe(fon, peoff):
    """Parse a PE-format FON file."""
    # We could try finding the Resource Table entry in the Optional
    # Header, but it talks about RVAs instead of file offsets, so
    # it's probably easiest just to go straight to the section table.
    # So let's find the size of the Optional Header, which we can
    # then skip over to find the section table.
    pe_header = _PE_HEADER.from_bytes(fon, peoff)
    section_table_offset = peoff + _PE_HEADER.size + pe_header.SizeOfOptionalHeader
    section_table_array = _IMAGE_SECTION_HEADER.array(pe_header.NumberOfSections)
    section_table = section_table_array.from_bytes(fon, section_table_offset)
    # find the resource section
    for section in section_table:
        if section.Name == b'.rsrc':
            break
    else:
        raise ValueError('Unable to locate resource section')
    # Now we've found the resource section, let's throw away the rest.
    rsrc = fon[section.PointerToRawData : section.PointerToRawData+section.SizeOfRawData]
    # Now the fun begins. To start with, we must find the initial
    # Resource Directory Table and look up type 0x08 (font) in it.
    # If it yields another Resource Directory Table, we recurse
    # into that; below the top level of type font we accept all Ids
    dataentries = _traverse_dirtable(rsrc, 0, _ID_FONT)
    # Each of these describes a font.
    ret = []
    for data_entry in dataentries:
        start = data_entry.OffsetToData - section.VirtualAddress
        try:
            font = parse_fnt(rsrc[start : start+data_entry.Size])
        except ValueError as e:
            raise ValueError('Failed to read font resource at {:x}: {}'.format(start, e))
        ret = ret + [font]
    return ret

def _traverse_dirtable(rsrc, off, rtype):
    """Recursively traverse the dirtable, returning all data entries under the given type id."""
    # resource directory header
    resdir = _IMAGE_RESOURCE_DIRECTORY.from_bytes(rsrc, off)
    number = resdir.NumberOfNamedEntries + resdir.NumberOfIdEntries
    # followed by resource directory entries
    direntry_array = _IMAGE_RESOURCE_DIRECTORY_ENTRY * number
    direntries = direntry_array.from_bytes(rsrc, off+_IMAGE_RESOURCE_DIRECTORY.size)
    dataentries = []
    for entry in direntries:
        if rtype in (entry.Id, None):
            off = entry.OffsetToData
            if off & (1<<31):
                # if it's a subdir, traverse recursively
                dataentries.extend(
                    _traverse_dirtable(rsrc, off & ~(1<<31), None)
                )
            else:
                # if it's a data entry, get the data
                dataentries.append(
                    _IMAGE_RESOURCE_DATA_ENTRY.from_bytes(rsrc, off)
                )
    return dataentries


##############################################################################

##############################################################################
# windows .FNT writer

def create_fnt(font, version=0x200):
    """Create .FNT from properties."""
    weight_map = dict(reversed(_item) for _item in _WEIGHT_MAP.items())
    charset_map = CHARSET_REVERSE_MAP
    style_map = dict(reversed(_item) for _item in _STYLE_MAP.items())
    if font.spacing == 'proportional':
        # low bit set for proportional
        pitch_and_family = 0x01 | style_map.get(font.style, 0)
        pix_width = 0
        v3_flags = _DFF_PROPORTIONAL
    else:
        # CHECK: is this really always set for fixed-pitch?
        pitch_and_family = _FF_MODERN
        # x_width should equal average width
        pix_width = font.raster_size.x
        v3_flags = _DFF_FIXED
    space_index = 0
    # if encoding is compatible, use it; otherwise set to fallback value
    charset = charset_map.get(font.encoding, _FALLBACK_CHARSET)
    # ensure codepoint values are set, if possible
    font = font.label(codepoint_from=font.encoding)
    # only include single-byte encoded glyphs
    codepoints = tuple(_cp[0] for _cp in font.get_codepoints() if len(_cp) == 1)
    if not codepoints:
        raise FileFormatError(
            'Windows font can only encode glyphs with single-byte codepoints; none found in font.'
        )
    # FNT can hold at most the codepoints 0..256 as these fields are byte-sized
    min_ord = min(codepoints)
    max_ord = min(255, max(codepoints))
    # char table; we need a contiguous range between the min and max codepoints
    ord_glyphs = [
        font.get_glyph(_codepoint, missing='empty')
        for _codepoint in range(min_ord, max_ord+1)
    ]
    default = font.get_glyph(font.default_char).codepoint
    if len(default) == 1:
        default_ord, = default
    else:
        default_ord = _FALLBACK_DEFAULT
    word_break = font.get_glyph(font.word_boundary).codepoint
    if len(word_break) == 1:
        break_ord, = word_break
    else:
        break_ord = _FALLBACK_BREAK
    # add the guaranteed-blank glyph
    ord_glyphs.append(Glyph.blank(pix_width, font.raster_size.y))
    # create the bitmaps
    bitmaps = [_glyph.as_bytes() for _glyph in ord_glyphs]
    # bytewise transpose - .FNT stores as contiguous 8-pixel columns
    bitmaps = [
        b''.join(
            _bm[_col::len(_bm)//_glyph.height]
            for _col in range(len(_bm)//_glyph.height)
        )
        for _glyph, _bm in zip(ord_glyphs, bitmaps)
    ]
    glyph_offsets = [0] + list(itertools.accumulate(len(_bm) for _bm in bitmaps))
    glyph_entry = _GLYPH_ENTRY[version]
    fnt_header_ext = _FNT_HEADER_EXT[version]
    offset_bitmaps = _FNT_HEADER.size + fnt_header_ext.size + len(ord_glyphs)*glyph_entry.size
    char_table = [
        bytes(glyph_entry(_glyph.width, offset_bitmaps + _glyph_offset))
        for _glyph, _glyph_offset in zip(ord_glyphs, glyph_offsets)
    ]
    file_size = offset_bitmaps + glyph_offsets[-1]
    # add name and device strings
    face_name_offset = file_size
    face_name = font.family.encode('latin-1', 'replace') + b'\0'
    device_name_offset = face_name_offset + len(face_name)
    device_name = font.device.encode('latin-1', 'replace') + b'\0'
    file_size = device_name_offset + len(device_name)
    # set device name pointer to zero for 'generic font'
    if not device_name or device_name == b'\0':
        device_name_offset = 0
    try:
        weight = weight_map[font.weight]
    except KeyError:
        logging.warning(
            f'Weight `{font.weight}` not supported by Windows FNT resource format, '
            '`regular` will be used instead.'
        )
        weight = weight_map['regular']
    # create FNT file
    win_props = _FNT_HEADER(
        dfVersion=version,
        dfSize=file_size,
        dfCopyright=font.copyright.encode('ascii', 'replace')[:60].ljust(60, b'\0'),
        dfType=0, # raster, not in memory
        dfPoints=int(font.point_size),
        dfVertRes=font.dpi.y,
        dfHorizRes=font.dpi.x,
        # Windows dfAscent means distance between matrix top and baseline
        dfAscent=font.shift_up + font.raster_size.y,
        #'ascent': win_props.dfAscent - win_props.dfInternalLeading,
        dfInternalLeading=font.shift_up + font.raster_size.y - font.ascent,
        #'line-height': win_props.dfPixHeight + win_props.dfExternalLeading,
        dfExternalLeading=font.line_height-font.raster_size.y,
        dfItalic=(font.slant in ('italic', 'oblique')),
        dfUnderline=('underline' in font.decoration),
        dfStrikeOut=('strikethrough' in font.decoration),
        dfWeight=weight_map.get(font.weight, weight_map['regular']),
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
        # round up to multiple of 2 bytes to word-align v1.0 strikes (not used for v2.0+ ?)
        dfWidthBytes=align(ceildiv(font.raster_size.x, 8), 1),
        dfDevice=device_name_offset,
        dfFace=face_name_offset,
        dfBitsPointer=0, # used on loading
        dfBitsOffset=offset_bitmaps,
    )
    # version-specific header extension
    header_ext = fnt_header_ext()
    if version == 0x300:
        # all are zeroes (default) except the flags for v3
        header_ext.dfFlags = v3_flags
    fnt = (
        bytes(win_props) + bytes(header_ext) + b''.join(char_table)
        + b''.join(bitmaps)
        + face_name + device_name
    )
    assert len(fnt) == file_size
    return fnt


##############################################################################
# windows .FON (NE executable) writer
#
# NE format:
#   http://www.csn.ul.ie/~caolan/pub/winresdump/winresdump/doc/winexe.txt
#   http://www.fileformat.info/format/exe/corion-ne.htm
#   https://wiki.osdev.org/NE
#   http://benoit.papillault.free.fr/c/disc2/exefmt.txt
#
# MZ header:
#   http://www.delorie.com/djgpp/doc/exe/
#   https://wiki.osdev.org/MZ


def _create_mz_stub():
    """Create a small MZ executable."""
    dos_stub_size = _MZ_HEADER.size + len(_STUB_CODE) + len(_STUB_MSG) + 1
    ne_offset = align(dos_stub_size, _ALIGN_SHIFT)
    mz_header = _MZ_HEADER(
        magic=b'MZ',
        last_page_length=dos_stub_size % 512,
        num_pages=ceildiv(dos_stub_size, 512),
        # 4-para header, where a paragraph == 16 bytes
        header_size=ceildiv(_MZ_HEADER.size, 16),
        # 16 extra para for stack
        min_allocation=0x10,
        # maximum extra paras: LOTS
        max_allocation=0xffff,
        initial_ss=0,
        initial_sp=0x100,
        # CS:IP = 0:0, start at beginning
        initial_csip=0,
        # we have no relocations, but if we did, they'd be right after this header
        relocation_table_offset=_MZ_HEADER.size,
        ne_offset=ne_offset,
    )
    return (bytes(mz_header) + _STUB_CODE + _STUB_MSG + b'$').ljust(ne_offset, b'\0')


def _create_fontdirentry(ordinal, fnt, font):
    """Return the DIRENTRY+FONTDIRENTRY, given the data in a .FNT file."""
    direntry = _DIRENTRY(ordinal)
    face_name = font.family.encode('latin-1', 'replace') + b'\0'
    device_name = font.device.encode('latin-1', 'replace') + b'\0'
    return (
        bytes(direntry)
        + fnt[0:0x71]
        + device_name
        + face_name
    )

def _create_resource_table(header_size, post_size, resdata_size, n_fonts, font_start):
    """Build the resource table."""
    res_names = b'\x07FONTDIR'
    # dynamic-size struct types
    typeinfo_fontdir_struct = type_info_struct(1)
    typeinfo_font_struct = type_info_struct(n_fonts)
    res_table_struct = le.Struct(
        rscAlignShift='word',
        # rscTypes is a list of non-equal TYPEINFO entries
        rscTypes_fontdir=typeinfo_fontdir_struct,
        rscTypes_font=typeinfo_font_struct,
        rscEndTypes='word', # 0
        rscResourceNames=struct.char * len(res_names),
        rscEndNames='byte', # 0
    )
    # calculate offset to resource data
    res_size_aligned = align(res_table_struct.size, _ALIGN_SHIFT)
    resdata_offset = align(header_size + res_size_aligned + post_size, _ALIGN_SHIFT)
    # FONTDIR resource table entry
    typeinfo_fontdir = typeinfo_fontdir_struct(
        rtTypeID=_RT_FONTDIR,
        rtResourceCount=1,
        rtNameInfo=(_NAMEINFO*1)(
            _NAMEINFO(
                rnOffset=resdata_offset >> _ALIGN_SHIFT,
                rnLength=resdata_size >> _ALIGN_SHIFT,
                # PRELOAD=0x0040 | MOVEABLE=0x0010 | 0x0c00 ?
                rnFlags=0x0c50,
                # rnID is set below
            )
        )
    )
    # FONT resource table entry
    typeinfo_font = typeinfo_font_struct(
        rtTypeID=_RT_FONT,
        rtResourceCount=n_fonts,
        rtNameInfo=(_NAMEINFO*n_fonts)(*(
            _NAMEINFO(
                rnOffset=(resdata_offset+font_start[_i]) >> _ALIGN_SHIFT,
                rnLength=(font_start[_i+1]-font_start[_i]) >> _ALIGN_SHIFT,
                # PURE=0x0020 | MOVEABLE=0x0010 | 0x1c00 ?
                rnFlags=0x1c30,
                rnID=0x8001 + _i,
            )
            for _i in range(n_fonts)
        ))
    )
    # Resource ID. This is an integer type if the high-order
    # bit is set (8000h), otherwise it is the offset to the
    # resource string, the offset is relative to the
    # beginning of the resource table.
    # -- i.e. offset to FONTDIR string
    typeinfo_fontdir.rtNameInfo[0].rnID = res_table_struct.size - len(res_names) - 1
    res_table = res_table_struct(
        rscAlignShift=_ALIGN_SHIFT,
        rscTypes_fontdir=typeinfo_fontdir,
        rscTypes_font=typeinfo_font,
        rscResourceNames=res_names,
    )
    return bytes(res_table).ljust(res_size_aligned, b'\0')


def _create_nonresident_name_table(pack):
    """Non-resident name tabe containing the FONTRES line."""
    # get name, dpi of first font
    # FONTRES is probably largely ignored anyway
    families = list(set(font.family for font in pack if font.family))
    if not families:
        names = list(set(font.name for font in pack if font.name))
        if not names:
            name = 'NoName'
        else:
            name, *_ = names[0].split(' ')
    else:
        name = families[0]
        if len(families) > 1:
            logging.warning('More than one font family name in container. Using `%s`.', name)
    resolutions = list(set(font.dpi for font in pack))
    if len(resolutions) > 1:
        logging.warning('More than one resolution in container. Using `%s`.', resolutions[0])
    dpi = resolutions[0]
    xdpi, ydpi = dpi.x, dpi.y
    points = [_font.point_size for _font in pack]
    # FONTRES Aspect, LogPixelsX, LogPixelsY : Name Pts0,Pts1,... (Device res.)
    nonres = ('FONTRES %d,%d,%d : %s %s' % (
        (100 * xdpi) // ydpi, xdpi, ydpi,
        name, ','.join(str(_pt) for _pt in sorted(points))
    )).encode('ascii', 'ignore')
    return bytes([len(nonres)]) + nonres + b'\0\0\0'


def _create_resident_name_table(pack):
    """Resident name table containing the module name."""
    # use font-family name of first font
    families = list(set(font.family.upper() for font in pack if font.family))
    if not families:
        name = _MODULE_NAME.upper()
    else:
        name = families[0]
    # Resident name table should just contain a module name.
    mname = ''.join(
        _c for _c in name
        if _c in set(string.ascii_letters + string.digits)
    )
    return bytes([len(mname)]) + mname.encode('ascii') + b'\0\0\0'


def _create_resource_data(pack, version):
    """Store the actual font resources."""
    # construct the FNT resources
    fonts = [create_fnt(_font, version) for _font in pack]
    # construct the FONTDIR (FONTGROUPHDR)
    # https://docs.microsoft.com/en-us/windows/desktop/menurc/fontgrouphdr
    fontdir_struct = le.Struct(
        NumberOfFonts='word',
        # + array of DIRENTRY/FONTDIRENTRY structs
    )
    fontdir = bytes(fontdir_struct(len(fonts))) + b''.join(
        _create_fontdirentry(_i+1, fonts[_i], _font)
        for _i, _font in enumerate(pack)
    )
    resdata = fontdir.ljust(align(len(fontdir), _ALIGN_SHIFT), b'\0')
    font_start = [len(resdata)]
    # append FONT resources
    for i in range(len(fonts)):
        resdata = resdata + fonts[i]
        resdata = resdata.ljust(align(len(resdata), _ALIGN_SHIFT), b'\0')
        font_start.append(len(resdata))
    return resdata, font_start


def _create_fon(pack, version=0x200):
    """Create a .FON font library."""
    n_fonts = len(pack)
    # MZ DOS executable stub
    stubdata = _create_mz_stub()
    # (non)resident name tables
    nonres = _create_nonresident_name_table(pack)
    res = _create_resident_name_table(pack)
    # entry table / imported names table should contain a zero word.
    entry = b'\0\0'
    # the actual font data
    resdata, font_start = _create_resource_data(pack, version)
    # create resource table and align
    header_size = len(stubdata) + _NE_HEADER.size
    post_size = len(res) + len(entry) + len(nonres)
    restable = _create_resource_table(header_size, post_size, len(resdata), n_fonts, font_start)
    # calculate offsets of stuff after the NE header.
    off_res = _NE_HEADER.size + len(restable)
    off_entry = off_res + len(res)
    off_nonres = off_entry + len(entry)
    size_aligned = align(off_nonres + len(nonres), _ALIGN_SHIFT)
    # create the NE header and put everything in place
    ne_header = _NE_HEADER(
        magic=b'NE',
        linker_major_version=5,
        linker_minor_version=10,
        entry_table_offset=off_entry,
        entry_table_length=len(entry),
        # 1<<3: protected mode only
        program_flags=0x08,
        # 0x03: uses windows/p.m. api | 1<<7: dll or driver
        application_flags=0x83,
        nonresident_names_table_size=len(nonres),
        # seg table is empty
        seg_table_offset=_NE_HEADER.size,
        res_table_offset=_NE_HEADER.size,
        resident_names_table_offset=off_res,
        # point to empty table
        module_ref_table_offset=off_entry,
        # point to empty table
        imp_names_table_offset=off_entry,
        # nonresident names table offset is w.r.t. file start
        nonresident_names_table_offset=len(stubdata) + off_nonres,
        file_alignment_size_shift_count=_ALIGN_SHIFT,
        # target Windows 3.0
        target_os=2,
        expected_windows_version=0x300
    )
    return (
        stubdata
        + (bytes(ne_header) + restable + res + entry + nonres).ljust(size_aligned, b'\0')
        + resdata
    )
