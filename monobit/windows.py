"""
monobit.windows - read and write windows font (.fon and .fnt) files

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

import os
import sys
import string
import struct
import logging

from .base import (
    VERSION, Glyph, Font, Typeface,
    ensure_stream, bytes_to_bits, ceildiv, struct_to_dict, bytes_to_str
)


 # https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/0d0b32ac-a836-4bd2-a112-b6000a1b4fc9
 # typedef  enum
 # {
 #   ANSI_CHARSET = 0x00000000,
 #   DEFAULT_CHARSET = 0x00000001,
 #   SYMBOL_CHARSET = 0x00000002,
 #   MAC_CHARSET = 0x0000004D,
 #   SHIFTJIS_CHARSET = 0x00000080,
 #   HANGUL_CHARSET = 0x00000081,
 #   JOHAB_CHARSET = 0x00000082,
 #   GB2312_CHARSET = 0x00000086,
 #   CHINESEBIG5_CHARSET = 0x00000088,
 #   GREEK_CHARSET = 0x000000A1,
 #   TURKISH_CHARSET = 0x000000A2,
 #   VIETNAMESE_CHARSET = 0x000000A3,
 #   HEBREW_CHARSET = 0x000000B1,
 #   ARABIC_CHARSET = 0x000000B2,
 #   BALTIC_CHARSET = 0x000000BA,
 #   RUSSIAN_CHARSET = 0x000000CC,
 #   THAI_CHARSET = 0x000000DE,
 #   EASTEUROPE_CHARSET = 0x000000EE,
 #   OEM_CHARSET = 0x000000FF
 # } CharacterSet;

# this is a guess, I can't find a more precise definition
_CHARSET_MAP = {
    0x00: 'windows-1252', # 'ANSI' - maybe 'iso-8859-1' but I think Windows would use this instead
    0x01: 'windows-1252', # locale dependent :/ ??
    0x02: 'symbol', # don't think this is defined
    0x4d: 'mac-roman',
    0x80: 'windows-932', # shift-jis, but MS probably mean their own extension?
    0x81: 'windows-949', # hangul, assuming euc-kr
    0x82: 'johab',
    0x86: 'windows-936', # gb2312
    0x88: 'windows-950', # big5
    0xa1: 'windows-1253', # greek
    0xa2: 'windows-1254', # turkish
    0xa3: 'windows-1258', # vietnamese
    0xb1: 'windows-1255', # hebrew
    0xb2: 'windows-1256', # arabic
    0xba: 'windows-1257', # baltic
    0xcc: 'windows-1251', # russian
    0xee: 'windows-1250', # eastern europe
    0xff: 'cp437', # 'OEM' - but also "the IBM PC hardware font" as per windows 1.03 sdk docs
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
#
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

# FNT header, common to v1.0, v2.0, v3.0
_FNT_COMMON_FMT ='<HL60s7H3BHBHHBHH4BH4L'
_FNT_COMMON_KEYS = [
    'dfVersion', 'dfSize', 'dfCopyright', 'dfType', 'dfPoints', 'dfVertRes', 'dfHorizRes',
    'dfAscent', 'dfInternalLeading', 'dfExternalLeading',
    'dfItalic', 'dfUnderline', 'dfStrikeOut', 'dfWeight',
    'dfCharSet', 'dfPixWidth', 'dfPixHeight', 'dfPitchAndFamily', 'dfAvgWidth', 'dfMaxWidth',
    'dfFirstChar', 'dfLastChar', 'dfDefaultChar', 'dfBreakChar',
    'dfWidthBytes', 'dfDevice', 'dfFace',
    'dfBitsPointer', 'dfBitsOffset'
]
# FNT header, version specific
_FNT_VERSION_FMT = {0x100: '<L', 0x200: 'B', 0x300: '<BL3HL16s'}
_FNT_VERSION_KEYS = {
    0x100: ['dfCharOffset'], 0x200: ['dfReserved'],
    0x300: [
        'dfReserved', 'dfFlags', 'dfAspace', 'dfBspace', 'dfCspace', 'dfColorPointer', 'dfReserved1'
    ]
}

_BYTE = 'B'
_WORD = '<H'
_LONG = '<L'


def unpack(format, buffer, offset):
    """Unpack a single value from bytes."""
    return struct.unpack_from(format, buffer, offset)[0]


def _read_fnt_header(fnt):
    """Read the header information in the FNT resource."""
    win_props = struct_to_dict(_FNT_COMMON_FMT, _FNT_COMMON_KEYS, fnt)
    common_size = struct.calcsize(_FNT_COMMON_FMT)
    version = win_props['dfVersion']
    version_fmt = _FNT_VERSION_FMT[version]
    version_keys = _FNT_VERSION_KEYS[version]
    win_props.update(struct_to_dict(version_fmt, version_keys, fnt, common_size))
    return win_props

def _read_fnt_chartable(fnt, win_props):
    """Read a WinFont 2.0 or 3.0 character table."""
    if win_props['dfVersion'] == 0x200:
        ct_start = 0x76
        ct_fmt = '<HH'
    else:
        ct_start = 0x94
        ct_fmt = '<HL'
    ct_size = struct.calcsize(ct_fmt)
    glyphs = {}
    height = win_props['dfPixHeight']
    for ord in range(win_props['dfFirstChar'], win_props['dfLastChar']+1):
        entry = ct_start + ct_size * (ord-win_props['dfFirstChar'])
        width, offset = struct.unpack_from(ct_fmt, fnt, entry)
        if not width:
            continue
        bytewidth = ceildiv(width, 8)
        rows = tuple(
            bytes_to_bits(
                [fnt[offset + _col * height + _row] for _col in range(bytewidth)],
                width
            )
            for _row in range(height)
        )
        if rows:
            glyphs[ord] = Glyph(rows)
    return glyphs

def _parse_win_props(fnt, win_props):
    """Convert WinFont properties to yaff properties."""
    version = win_props['dfVersion']
    if win_props['dfType'] & 1:
        raise ValueError('Not a bitmap font')
    properties = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': 'WinFont v{}.{}'.format(*divmod(version, 256)),
        'name': bytes_to_str(fnt[win_props['dfFace']:]),
        'copyright': bytes_to_str(win_props['dfCopyright']),
        'points': win_props['dfPoints'],
        'slant': 'italic' if win_props['dfItalic'] else 'roman',
        'size': win_props['dfPixHeight'],
        # Windows dfAscent means distance between matrix top and baseline
        'ascent': win_props['dfAscent'] - win_props['dfInternalLeading'],
        'bottom': win_props['dfAscent'] - win_props['dfPixHeight'],
        'default-char': win_props['dfDefaultChar'],
    }
    if win_props['dfHorizRes'] != win_props['dfVertRes']:
        properties['dpi'] = '{dfHorizRes} {dfVertRes}'.format(**win_props)
    else:
        properties['dpi'] = win_props['dfHorizRes']
    deco = []
    if win_props['dfUnderline']:
        deco.append('underline')
    if win_props['dfStrikeOut']:
        deco.append('strikethrough')
    if deco:
        properties['decoration'] = ' '.join(deco)
    weight = win_props['dfWeight']
    if weight:
        weight = max(100, min(900, weight))
        properties['weight'] = _WEIGHT_MAP[round(weight, -2)]
    charset = win_props['dfCharSet']
    if charset in _CHARSET_MAP:
        properties['encoding'] = _CHARSET_MAP[charset]
    else:
        properties['_dfCharSet'] = str(charset)
    # append unparsed properties
    # TODO: parse these
    properties['_DeviceName'] = bytes_to_str(fnt[win_props['dfDevice']:])
    for prop in (
            'dfExternalLeading', 'dfPitchAndFamily', 'dfAvgWidth', 'dfMaxWidth', 'dfBreakChar'
        ):
        properties['_' + prop] = win_props[prop]
    if version == 0x300:
        for prop in _FNT_VERSION_KEYS[0x300]:
            properties['_' + prop] = win_props[prop]
    return properties

def _read_fnt(fnt):
    """Create an internal font description from a .FNT-shaped string."""
    win_props = _read_fnt_header(fnt)
    properties = _parse_win_props(fnt, win_props)
    glyphs = _read_fnt_chartable(fnt, win_props)
    return Font(glyphs, comments={}, properties=properties)

def _read_ne_fon(fon, neoff):
    """Finish splitting up a NE-format FON file."""
    ret = []
    # Find the resource table.
    rtable = neoff + unpack(_WORD, fon, neoff + 0x24)
    # Read the shift count out of the resource table.
    shift = unpack(_WORD, fon, rtable)
    # Now loop over the rest of the resource table.
    p = rtable + 2
    while True:
        rtype = unpack(_WORD, fon, p)
        if rtype == 0:
            break  # end of resource table
        count = unpack(_WORD, fon, p+2)
        p += 8  # type, count, 4 bytes reserved
        for i in range(count):
            start = unpack(_WORD, fon, p) << shift
            size = unpack(_WORD, fon, p+2) << shift
            if start < 0 or size < 0 or start+size > len(fon):
                raise ValueError('Resource overruns file boundaries')
            if rtype == 0x8008: # this is an actual font
                try:
                    font = _read_fnt(fon[start:start+size])
                except Exception as e:
                    raise ValueError('Failed to read font resource at {:x}: {}'.format(start, e))
                ret.append(font)
            p += 12 # start, size, flags, name/id, 4 bytes reserved
    return ret

def _read_pe_fon(fon, peoff):
    """Finish splitting up a PE-format FON file."""
    dirtables = []
    dataentries = []

    def gotoffset(off, dirtables=dirtables, dataentries=dataentries):
        if off & 0x80000000:
            off &= ~0x80000000
            dirtables.append(off)
        else:
            dataentries.append(off)

    def dodirtable(rsrc, off, rtype, gotoffset=gotoffset):
        number = unpack(_WORD, rsrc, off+12) + unpack(_WORD, rsrc, off+14)
        for i in range(number):
            entry = off + 16 + 8*i
            thetype = unpack(_LONG, rsrc, entry)
            theoff = unpack(_LONG, rsrc, entry+4)
            if rtype == -1 or rtype == thetype:
                gotoffset(theoff)

    # We could try finding the Resource Table entry in the Optional
    # Header, but it talks about RVAs instead of file offsets, so
    # it's probably easiest just to go straight to the section table.
    # So let's find the size of the Optional Header, which we can
    # then skip over to find the section table.
    secentries = unpack(_WORD, fon, peoff+0x06)
    sectable = peoff + 0x18 + unpack(_WORD, fon, peoff+0x14)
    for i in range(secentries):
        secentry = sectable + i * 0x28
        secname = bytes_to_str(fon[secentry:secentry+8])
        secrva = unpack(_LONG, fon, secentry+0x0C)
        secsize = unpack(_LONG, fon, secentry+0x10)
        secptr = unpack(_LONG, fon, secentry+0x14)
        if secname == '.rsrc':
            break
    else:
        raise ValueError('Unable to locate resource section')
    # Now we've found the resource section, let's throw away the rest.
    rsrc = fon[secptr:secptr+secsize]
    # Now the fun begins. To start with, we must find the initial
    # Resource Directory Table and look up type 0x08 (font) in it.
    # If it yields another Resource Directory Table, we stick the
    # address of that on a list. If it gives a Data Entry, we put
    # that in another list.
    dodirtable(rsrc, 0, 0x08)
    # Now process Resource Directory Tables until no more remain
    # in the list. For each of these tables, we accept _all_ entries
    # in it, and if they point to subtables we stick the subtables in
    # the list, and if they point to Data Entries we put those in
    # the other list.
    while len(dirtables) > 0:
        table = dirtables[0]
        del dirtables[0]
        dodirtable(rsrc, table, -1) # accept all entries
    # Now we should be left with Resource Data Entries. Each of these
    # describes a font.
    ret = []
    for off in dataentries:
        rva = unpack(_LONG, rsrc, off)
        size = unpack(_LONG, rsrc, off+4)
        start = rva - secrva
        try:
            font = _read_fnt(rsrc[start:start+size])
        except Exception as e:
            raise ValueError('Failed to read font resource at {:x}: {}'.format(start, e))
        ret = ret + [font]
    return ret

def _read_fon(fon):
    """Split a .FON up into .FNTs and pass each to _read_fnt."""
    # Find the NE header.
    neoff = unpack(_LONG, fon, 0x3C)
    if fon[neoff:neoff+2] == b'NE':
        return _read_ne_fon(fon, neoff)
    elif fon[neoff:neoff+4] == b'PE\0\0':
        return _read_pe_fon(fon, neoff)
    else:
        raise ValueError('NE or PE signature not found')


@Typeface.loads('fnt', 'fon', encoding=None)
def load(infile):
    """Load a Windows .FON or .FNT file."""
    with ensure_stream(infile, 'rb') as instream:
        data = instream.read()
        name = instream.name
    # determine if a file is a .FON or a .FNT format font
    if data[0:2] == b'MZ':
        fonts = _read_fon(data)
    else:
        fonts = [_read_fnt(data)]
    for font in fonts:
        font._properties['source-name'] = os.path.basename(name)
    return Typeface(fonts)
