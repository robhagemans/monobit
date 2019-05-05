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

import sys
import string
import struct
import logging

from .base import VERSION, Glyph, Font, Typeface, ensure_stream, bytes_to_bits, ceildiv

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

_BYTE = 'B'
_WORD = '<H'
_LONG = '<L'


def unpack(format, buffer, offset):
    """Unpack a single value from bytes."""
    return struct.unpack_from(format, buffer, offset)[0]

def asciz(s):
    """Extract null-terminated string from bytes."""
    if b'\0' in s:
        s, _ = s.split(b'\0', 1)
    return s.decode('ascii')


def _read_fnt(fnt):
    """Create an internal font description from a .FNT-shaped string."""
    version = unpack(_WORD, fnt, 0)
    ftype = unpack(_WORD, fnt, 0x42)
    if ftype & 1:
        raise ValueError('This font is a vector font')
    off_facename = unpack(_LONG, fnt, 0x69)
    if off_facename < 0 or off_facename > len(fnt):
        raise ValueError('Face name not contained within font data')
    properties = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': 'WindowsFont [0x{:04x}]'.format(version),
        'name': asciz(fnt[off_facename:]),
        'copyright': asciz(fnt[6:66]),
        'points': unpack(_WORD, fnt, 0x44),
    }
    xdpi, ydpi = struct.unpack_from('<HH', fnt, 0x46)
    properties['dpi'] = ' '.join((str(xdpi), str(ydpi))) if xdpi != ydpi else str(xdpi)
    ascent, int_lead, ext_lead = struct.unpack_from('<HHH', fnt, 0x4A)
    properties['ascent'] = ascent - int_lead
    properties['slant'] = 'italic' if unpack(_BYTE, fnt, 0x50) else 'roman'
    deco = []
    if unpack(_BYTE, fnt, 0x51):
        deco.append('underline')
    if unpack(_BYTE, fnt, 0x52):
        deco.append('strikethrough')
    if deco:
        properties['decoration'] = ' '.join(deco)
    weight = unpack(_WORD, fnt, 0x53)
    if weight:
        weight = max(100, min(900, weight))
        properties['weight'] = _WEIGHT_MAP[round(weight, -2)]
    charset = unpack(_BYTE, fnt, 0x55)
    if charset in _CHARSET_MAP:
        properties['encoding'] = _CHARSET_MAP[charset]
    else:
        properties['_CHARSET'] = str(charset)
    # Read the char table.
    height = unpack(_WORD, fnt, 0x58)
    properties['size'] = height
    # Windows 'ascent' means distance between matrix top and baseline
    properties['bottom'] = ascent - height
    if version == 0x200:
        ctstart = 0x76
        ctsize = 4
    else:
        ctstart = 0x94
        ctsize = 6
    maxwidth = 0
    glyphs = {}
    firstchar, lastchar, defaultchar = struct.unpack_from('BBB', fnt, 0x5F)
    properties['default-char'] = '0x{:x}'.format(defaultchar)
    for i in range(firstchar, lastchar+1):
        entry = ctstart + ctsize * (i-firstchar)
        width = unpack(_WORD, fnt, entry)
        if not width:
            continue
        if ctsize == 4:
            off = unpack(_WORD, fnt, entry+2)
        else:
            off = unpack(_LONG, fnt, entry+2)
        rows = []
        bytewidth = ceildiv(width, 8)
        for j in range(height):
            rowbytes = []
            for k in range(bytewidth):
                bytepos = off + k * height + j
                rowbytes.append(unpack(_BYTE, fnt, bytepos))
            rows.append(bytes_to_bits(rowbytes, width))
        if rows:
            glyphs[i] = Glyph(tuple(rows))
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
        secname = asciz(fon[secentry:secentry+8])
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
        font._properties['source-name'] = name
    return Typeface(fonts)
