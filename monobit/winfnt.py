"""
monobit.winfnt - windows 1.x, 2.x and 3.x .FNT files

based on Simon Tatham's dewinfont; see MIT-style licence below.
changes (c) 2019 Rob Hagemans and released under the same licence.

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

from .binary import friendlystruct, bytes_to_bits, ceildiv, align
from .formats import Loaders, Savers
from .font import Font, Coord
from .glyph import Glyph


##############################################################################
# windows .FNT format definitions
#
# https://web.archive.org/web/20120215123301/http://support.microsoft.com/kb/65123
# https://ffenc.blogspot.com/2008/04/fnt-font-file-format.html


# https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/0d0b32ac-a836-4bd2-a112-b6000a1b4fc9
# most of this is a guess, I can't find a more precise definition
_CHARSET_MAP = {
    # ANSI_CHARSET = 0x00000000 - maybe 'iso-8859-1' but I think Windows would use this instead
    0x00: 'windows-ansi-2.0',
    # DEFAULT_CHARSET = 0x00000001 - locale dependent :/ ??
    0x01: 'windows-ansi-2.0',
    # SYMBOL_CHARSET = 0x00000002
    0x02: 'mac-symbol',
    # MAC_CHARSET = 0x0000004D
    0x4d: 'mac-roman',
    # SHIFTJIS_CHARSET = 0x00000080 - MS probably mean their own Shift-JIS extension?
    0x80: 'windows-932',
    # HANGUL_CHARSET = 0x00000081 - assuming euc-kr
    0x81: 'windows-949',
    # JOHAB_CHARSET = 0x00000082
    0x82: 'johab',
    # GB2312_CHARSET = 0x00000086,
    0x86: 'windows-936',
    # CHINESEBIG5_CHARSET = 0x00000088
    0x88: 'windows-950',
    # GREEK_CHARSET = 0x000000A1
    0xa1: 'windows-1253',
    # TURKISH_CHARSET = 0x000000A2
    0xa2: 'windows-1254',
    # VIETNAMESE_CHARSET = 0x000000A3
    0xa3: 'windows-1258',
    # HEBREW_CHARSET = 0x000000B1
    0xb1: 'windows-1255',
    # ARABIC_CHARSET = 0x000000B2
    0xb2: 'windows-1256',
    # BALTIC_CHARSET = 0x000000BA
    0xba: 'windows-1257',
    # RUSSIAN_CHARSET = 0x000000CC
    0xcc: 'windows-1251',
    # THAI_CHARSET = 0x000000DE
    0xde: 'windows-874',
    # EASTEUROPE_CHARSET = 0x000000EE
    0xee: 'windows-1250',
    # OEM_CHARSET = 0x000000FF
    # Specifies a mapping to one of the OEM code pages, according to the current system locale setting
    # - also "the IBM PC hardware font" as per windows 1.03 sdk docs
    0xff: 'cp437',
}

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
_FNT_HEADER = friendlystruct(
    'le',
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
_FNT_HEADER_1 = friendlystruct('le')
_FNT_HEADER_2 = friendlystruct('le', dfReserved='byte')
_FNT_HEADER_3 = friendlystruct(
    'le',
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
_GLYPH_ENTRY_1 = friendlystruct(
    'le',
    geOffset='word',
)
_GLYPH_ENTRY_2 = friendlystruct(
    'le',
    geWidth='word',
    geOffset='word',
)
_GLYPH_ENTRY_3 = friendlystruct(
    'le',
    geWidth='word',
    geOffset='dword',
)
# for ABCFIXED and ABCPROPORTIONAL; for reference, not used in v3.00 (i.e. not used at all)
_GLYPH_ENTRY_3ABC = friendlystruct(
    'le',
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
# top level functions

@Loaders.register('fnt', name='Windows FNT', binary=True)
def load(instream):
    """Load a Windows .FNT file."""
    font = parse_fnt(instream.read())
    return font

@Savers.register('fnt', binary=True, multi=False)
def save(font, outstream, version:int=2):
    """Write font to a Windows .FNT file."""
    outstream.write(create_fnt(font, version*0x100))
    return font


##############################################################################
# windows .FNT reader

def parse_fnt(fnt):
    """Create an internal font description from a .FNT-shaped string."""
    win_props = _parse_header(fnt)
    properties = _parse_win_props(fnt, win_props)
    glyphs = _parse_chartable(fnt, win_props)
    return Font(glyphs, properties=properties)

def _parse_header(fnt):
    """Read the header information in the FNT resource."""
    win_props = _FNT_HEADER.from_bytes(fnt)
    header_ext = _FNT_HEADER_EXT[win_props.dfVersion]
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
        glyph_entry_array = _GLYPH_ENTRY[win_props.dfVersion] * (n_chars+1)
        entries = glyph_entry_array.from_buffer_copy(fnt, ct_start)
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
        # don't store empty glyphs but count them for ordinals
        if rows:
            glyphs.append(Glyph(rows), codepoint=win_props.dfFirstChar + ord)
    return glyphs

def _parse_chartable_v2(fnt, win_props):
    """Read a WinFont 2.0 or 3.0 character table."""
    n_chars = win_props.dfLastChar - win_props.dfFirstChar + 1
    glyph_entry_array = _GLYPH_ENTRY[win_props.dfVersion] * n_chars
    ct_start = _FNT_HEADER_SIZE[win_props.dfVersion]
    glyphs = []
    height = win_props.dfPixHeight
    entries = glyph_entry_array.from_buffer_copy(fnt, ct_start)
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
        glyphs.append(Glyph.from_bytes(glyph_data, entry.geWidth).set_annotations(codepoint=ord))
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
        'ascent': win_props.dfAscent - win_props.dfInternalLeading,
        'descent': win_props.dfPixHeight - win_props.dfAscent,
        'offset': Coord(0, win_props.dfAscent - win_props.dfPixHeight),
        'leading': win_props.dfExternalLeading,
        'default-char': win_props.dfDefaultChar + win_props.dfFirstChar,
    }
    if win_props.dfPixWidth:
        properties['spacing'] = 'monospace'
    else:
        properties['spacing'] = 'proportional'
        # this can be extracted from the font - will be dropped if consistent
        # Windows documentation defines this as 'width of the character "X."'
        # for 1.0 system fonts, it is consistent with the advance width of LATIN CAPITAL LETTER X.
        # for 2.0+ system fonts, this appears to be set to the average advance width.
        # fontforge follows the "new" definition while mkwinfont follows the "old".
        # we'll make it depend on the version
        if version == 0x100:
            properties['cap-advance'] = win_props.dfAvgWidth
        else:
            properties['average-advance'] = win_props.dfAvgWidth
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
    if charset in _CHARSET_MAP:
        properties['encoding'] = _CHARSET_MAP[charset]
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
# windows .FNT writer

def create_fnt(font, version=0x200):
    """Create .FNT from properties."""
    weight_map = dict(reversed(_item) for _item in _WEIGHT_MAP.items())
    charset_map = dict(reversed(_item) for _item in _CHARSET_MAP.items())
    style_map = dict(reversed(_item) for _item in _STYLE_MAP.items())
    if font.spacing == 'proportional':
        # width of uppercase X
        x_width = int(font.x_width)
        # low bit set for proportional
        pitch_and_family = 0x01 | style_map.get(font.style, 0)
        pix_width = 0
        v3_flags = _DFF_PROPORTIONAL
    else:
        # CHECK: is this really always set for fixed-pitch?
        pitch_and_family = _FF_MODERN
        # x_width should equal average width
        x_width = pix_width = font.bounding_box.x
        v3_flags = _DFF_FIXED
    space_index = 0
    # use only native encoding for now
    encoding = None
    # char table
    ord_glyphs = [_glyph for _, _glyph in enumerate(font.glyphs)]
    min_ord = 0
    max_ord = len(ord_glyphs) - 1
    # add the guaranteed-blank glyph
    ord_glyphs.append(Glyph.empty(pix_width, font.bounding_box.y))
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
        dfAscent=font.offset.y + font.bounding_box.y,
        #'ascent': win_props.dfAscent - win_props.dfInternalLeading,
        dfInternalLeading=font.offset.y + font.bounding_box.y - font.ascent,
        dfExternalLeading=font.leading,
        dfItalic=(font.slant in ('italic', 'oblique')),
        dfUnderline=('underline' in font.decoration),
        dfStrikeOut=('strikethrough' in font.decoration),
        dfWeight=weight_map.get(font.weight, weight_map['regular']),
        dfCharSet=charset_map.get(font.encoding, 0xff),
        dfPixWidth=pix_width,
        dfPixHeight=font.bounding_box.y,
        dfPitchAndFamily=pitch_and_family,
        # for 2.0+, we use actual average advance here (like fontforge but unlike mkwinfont)
        dfAvgWidth=round(font.average_advance),
        # max advance width
        dfMaxWidth=font.bounding_box.x + font.tracking + font.offset_x,
        dfFirstChar=min_ord,
        dfLastChar=max_ord,
        dfDefaultChar=font.get_ordinal(font.default_char) - min_ord,
        dfBreakChar=font.get_ordinal(font.word_boundary) - min_ord,
        # round up to multiple of 2 bytes to word-align v1.0 strikes (not used for v2.0+ ?)
        dfWidthBytes=align(ceildiv(font.bounding_box.x, 8), 1),
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
