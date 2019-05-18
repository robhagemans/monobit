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
import itertools

from .base import (
    VERSION, Glyph, Font, Typeface, friendlystruct,
    bytes_to_bits, ceildiv, pad, bytes_to_str
)


##############################################################################
# windows .FON and .FNT format definitions


# https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/0d0b32ac-a836-4bd2-a112-b6000a1b4fc9
# most of this is a guess, I can't find a more precise definition
_CHARSET_MAP = {
    # ANSI_CHARSET = 0x00000000 - maybe 'iso-8859-1' but I think Windows would use this instead
    0x00: 'windows-1252',
    # DEFAULT_CHARSET = 0x00000001 - locale dependent :/ ??
    0x01: 'windows-1252',
    # SYMBOL_CHARSET = 0x00000002
    0x02: 'symbol',
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
    # OEM_CHARSET = 0x000000FF - also "the IBM PC hardware font" as per windows 1.03 sdk docs
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

# pitch and family
# low bit: 1 - proportional 0 - monospace
# upper bits: family (like bdf add_style_name)
_STYLE_MAP = {
    0: '', #FF_DONTCARE (0<<4)   Don't care or don't know.
    1: 'serif', # FF_ROMAN (1<<4)      Proportionally spaced fonts with serifs.
    2: 'sans serif', # FF_SWISS (2<<4)      Proportionally spaced fonts without serifs.
    3: '', # FF_MODERN (3<<4)     Fixed-pitch fonts. - but this is covered by `spacing`?
    4: 'script', # FF_SCRIPT (4<<4)
    5: 'decorated', # FF_DECORATIVE (5<<4)
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


# FNT header - the part common to v1.0, v2.0, v3.0
_FNT_HEADER = friendlystruct(
    '<',
### this part is also common to FontDirEntry
    dfVersion='H',
    dfSize='L',
    dfCopyright='60s',
    dfType='H',
    dfPoints='H',
    dfVertRes='H',
    dfHorizRes='H',
    dfAscent='H',
    dfInternalLeading='H',
    dfExternalLeading='H',
    dfItalic='B',
    dfUnderline='B',
    dfStrikeOut='B',
    dfWeight='H',
    dfCharSet='B',
    dfPixWidth='H',
    dfPixHeight='H',
    dfPitchAndFamily='B',
    dfAvgWidth='H',
    dfMaxWidth='H',
    dfFirstChar='B',
    dfLastChar='B',
    dfDefaultChar='B',
    dfBreakChar='B',
    dfWidthBytes='H',
    dfDevice='L',
    dfFace='L',
###
    dfBitsPointer='L',
    dfBitsOffset='L',
)

# version-specific header extensions
_FNT_HEADER_1 = friendlystruct('<')
_FNT_HEADER_2 = friendlystruct('<', dfReserved='B')
_FNT_HEADER_3 = friendlystruct(
    '<',
    dfReserved='B',
    dfFlags='L',
    dfAspace='H',
    dfBspace='H',
    dfCspace='H',
    dfColorPointer='L',
    dfReserved1='16s',
)
_FNT_VERSION_HEADER = {
    0x100: _FNT_HEADER_1,
    0x200: _FNT_HEADER_2,
    0x300: _FNT_HEADER_3,
}
# total size
# {'0x100': '0x75', '0x200': '0x76', '0x300': '0x94'}
_FNT_HEADER_SIZE = {
    _ver: _FNT_HEADER.size + _header.size
    for _ver, _header in _FNT_VERSION_HEADER.items()
}

# char table header
_CT_HEADER_1 = friendlystruct(
    '<',
    offset='H',
)
_CT_HEADER_2 = friendlystruct(
    '<',
    width='H',
    offset='H',
)
_CT_HEADER_3 = friendlystruct(
    '<',
    width='H',
    offset='L',
)
_CT_VERSION_HEADER = {
    0x200: _CT_HEADER_2,
    0x300: _CT_HEADER_3,
}


##############################################################################
# top level functions

@Typeface.loads('fnt', 'fon', encoding=None)
def load(instream):
    """Load a Windows .FON or .FNT file."""
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

@Typeface.saves('fnt', 'fon', encoding=None)
def save(typeface, outstream):
    """Write fonts to a Windows .FON or .FNT file."""
    if outstream.name.endswith('.fnt'):
        if len(typeface._fonts) > 1:
            raise ValueError('Saving multiple fonts to Windows .fnt not possible')
        outstream.write(_create_fnt(typeface._fonts[0]))
    else:
        outstream.write(_create_fon(typeface))
    return typeface



##############################################################################
# windows .FNT resource reader and parser

def unpack(format, buffer, offset):
    """Unpack a single value from bytes."""
    return struct.unpack_from(format, buffer, offset)[0]


def _read_fnt_header(fnt):
    """Read the header information in the FNT resource."""
    win_props = _FNT_HEADER.from_bytes(fnt)
    version = win_props.dfVersion
    header_ext = _FNT_VERSION_HEADER[version]
    win_props += header_ext.from_bytes(fnt, offset=_FNT_HEADER.size)
    return win_props


def _read_fnt_chartable(fnt, win_props):
    """Read a WinFont character table."""
    if win_props['dfVersion'] == 0x100:
        return _read_fnt_chartable_v1(fnt, win_props)
    return _read_fnt_chartable_v2(fnt, win_props)

def _read_fnt_chartable_v1(fnt, win_props):
    """Read a WinFont 1.0 character table."""
    n_chars = win_props['dfLastChar'] - win_props['dfFirstChar'] + 1
    if not win_props['dfPixWidth']:
        # proportional font
        ct_start = _FNT_HEADER_SIZE[0x100]
        ct_size = _CT_HEADER_1.size
        offsets = [
            _CT_HEADER_1.from_bytes(fnt, offset=ct_start + _ord * ct_size)[0]
            for _ord in range(n_chars+1)
        ]
    else:
        offsets = [
            win_props['dfPixWidth'] * _ord
            for _ord in range(n_chars+1)
        ]
    height = win_props['dfPixHeight']
    bytewidth = win_props['dfWidthBytes']
    offset = win_props['dfBitsOffset']
    strikerows = tuple(
        bytes_to_bits(fnt[offset+_row*bytewidth : offset+(_row+1)*bytewidth])
        for _row in range(height)
    )
    glyphs = []
    labels = {}
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
            glyphs.append(Glyph(rows))
            labels[win_props['dfFirstChar'] + ord] = len(glyphs) - 1
    return glyphs, labels

def _read_fnt_chartable_v2(fnt, win_props):
    """Read a WinFont 2.0 or 3.0 character table."""
    ct_start = _FNT_HEADER_SIZE[win_props['dfVersion']]
    ct_header = _CT_VERSION_HEADER[win_props['dfVersion']]
    ct_size = ct_header.size
    glyphs = []
    labels = {}
    height = win_props['dfPixHeight']
    for ord in range(win_props['dfFirstChar'], win_props['dfLastChar']+1):
        entry = ct_start + ct_size * (ord-win_props['dfFirstChar'])
        width, offset = ct_header.from_bytes(fnt, offset=entry)
        # don't store empty glyphs but count them for ordinals
        if not width:
            continue
        bytewidth = ceildiv(width, 8)
        rows = tuple(
            #FIXME: replace with Glyph.from_bytes
            bytes_to_bits(
                [fnt[offset + _col * height + _row] for _col in range(bytewidth)],
                width
            )
            for _row in range(height)
        )
        glyphs.append(Glyph(rows))
        labels[ord] = len(glyphs) - 1
    return glyphs, labels

def _parse_win_props(fnt, win_props):
    """Convert WinFont properties to yaff properties."""
    version = win_props['dfVersion']
    if win_props['dfType'] & 1:
        raise ValueError('Not a bitmap font')
    properties = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': 'WinFont v{}.{}'.format(*divmod(version, 256)),
        'family': bytes_to_str(fnt[win_props['dfFace']:]),
        'copyright': bytes_to_str(win_props['dfCopyright']),
        'points': win_props['dfPoints'],
        'slant': 'italic' if win_props['dfItalic'] else 'roman',
        # Windows dfAscent means distance between matrix top and baseline
        'ascent': win_props['dfAscent'] - win_props['dfInternalLeading'],
        'bottom': win_props['dfAscent'] - win_props['dfPixHeight'],
        'leading': win_props['dfExternalLeading'],
        'default-char': '0x{:x}'.format(win_props['dfDefaultChar']),
    }
    if win_props['dfPixWidth']:
        properties['spacing'] = 'monospace'
        properties['size'] = '{} {}'.format(win_props['dfPixWidth'], win_props['dfPixHeight'])
    else:
        properties['spacing'] = 'proportional'
        properties['size'] = win_props['dfPixHeight']
        # this can all be extracted from the font - drop if consistent?
        properties['x-width'] = win_props['dfAvgWidth']
    # check prop/fixed flag
    if bool(win_props['dfPitchAndFamily'] & 1) != bool(properties['spacing'] == 'proportional'):
        logging.warning('inconsistent spacing properties.')
    if win_props['dfHorizRes'] != win_props['dfVertRes']:
        properties['dpi'] = '{} {}'.format(win_props.dfHorizRes, win_props.dfVertRes)
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
    properties['style'] = _STYLE_MAP[win_props['dfPitchAndFamily'] >> 4]
    properties['word-boundary'] = '0x{:x}'.format(win_props['dfFirstChar'] + win_props['dfBreakChar'])
    # append unparsed properties
    properties['device'] = bytes_to_str(fnt[win_props['dfDevice']:])
    # dfMaxWidth - but this can be calculated from the matrices
    if version == 0x300:
        if win_props['dfFlags'] & _DFF_COLORFONT:
            raise ValueError('ColorFont not supported')
        # yet another prop/fixed flag
        if bool(win_props['dfFlags'] & _DFF_PROP) != properties['spacing'] == 'proportional':
            logging.warning('inconsistent spacing properties.')
        if win_props['dfFlags'] & _DFF_ABC:
            properties['offset-before'] = win_props['dfAspace']
            properties['offset-after'] = win_props['dfCspace']
            # dfBspace - 'width of the character' - i assume not used for proportional
            # and duplicated for fixed-width
    name = [properties['family']]
    if properties['weight'] != 'regular':
        name.append(properties['weight'])
    if properties['slant'] != 'roman':
        name.append(properties['slant'])
    name.append('{}pt'.format(properties['points']))
    if properties['spacing'] == 'proportional':
        name.append('{}px'.format(properties['size']))
    else:
        name.append('{}x{}px'.format(*properties['size'].split(' ')))
    properties['name'] = ' '.join(name)
    return properties

def _read_fnt(fnt):
    """Create an internal font description from a .FNT-shaped string."""
    win_props = _read_fnt_header(fnt)
    properties = _parse_win_props(fnt, win_props)
    glyphs, labels = _read_fnt_chartable(fnt, win_props)
    return Font(glyphs, labels, comments={}, properties=properties)


##############################################################################
# .FON (NE/PE executable) file reader

def _read_ne_fon(fon, neoff):
    """Finish splitting up a NE-format FON file."""
    ret = []
    # Find the resource table.
    rtable = neoff + unpack('<H', fon, neoff + 0x24)
    # Read the shift count out of the resource table.
    shift = unpack('<H', fon, rtable)
    # Now loop over the rest of the resource table.
    p = rtable + 2
    while True:
        rtype = unpack('<H', fon, p)
        if rtype == 0:
            break  # end of resource table
        count = unpack('<H', fon, p+2)
        p += 8  # type, count, 4 bytes reserved
        for i in range(count):
            start = unpack('<H', fon, p) << shift
            size = unpack('<H', fon, p+2) << shift
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
        number = unpack('<H', rsrc, off+12) + unpack('<H', rsrc, off+14)
        for i in range(number):
            entry = off + 16 + 8*i
            thetype = unpack('<L', rsrc, entry)
            theoff = unpack('<L', rsrc, entry+4)
            if rtype == -1 or rtype == thetype:
                gotoffset(theoff)

    # We could try finding the Resource Table entry in the Optional
    # Header, but it talks about RVAs instead of file offsets, so
    # it's probably easiest just to go straight to the section table.
    # So let's find the size of the Optional Header, which we can
    # then skip over to find the section table.
    secentries = unpack('<H', fon, peoff+0x06)
    sectable = peoff + 0x18 + unpack('<H', fon, peoff+0x14)
    for i in range(secentries):
        secentry = sectable + i * 0x28
        secname = bytes_to_str(fon[secentry:secentry+8])
        secrva = unpack('<L', fon, secentry+0x0C)
        secsize = unpack('<L', fon, secentry+0x10)
        secptr = unpack('<L', fon, secentry+0x14)
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
        rva = unpack('<L', rsrc, off)
        size = unpack('<L', rsrc, off+4)
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
    neoff = unpack('<L', fon, 0x3C)
    if fon[neoff:neoff+2] == b'NE':
        return _read_ne_fon(fon, neoff)
    elif fon[neoff:neoff+4] == b'PE\0\0':
        return _read_pe_fon(fon, neoff)
    else:
        raise ValueError('NE or PE signature not found')



##############################################################################
# windows .FNT writer

# dfType field values
# vector font, else raster
_FNT_TYPE_VECTOR = 0x0001
# font is in ROM
_FNT_TYPE_MEMORY = 0x0004
# 'realised by a device' - maybe printer font?
_FNT_TYPE_DEVICE = 0x0080


def _get_prop_x(prop):
    """Get x of property coordinate ('x y' or single size)."""
    split = str(prop).split(' ', 1)
    return int(split[0])

def _get_prop_y(prop):
    """Get y of property coordinate ('x y' or single size)."""
    split = str(prop).split(' ', 1)
    return int(split[-1])

def _create_fnt(font):
    """Create .FNT from properties."""
    weight_map = dict(reversed(_item) for _item in _WEIGHT_MAP.items())
    charset_map = dict(reversed(_item) for _item in _CHARSET_MAP.items())
    style_map = dict(reversed(_item) for _item in _STYLE_MAP.items())
    glyphs = font._glyphs
    properties = font._properties
    try:
        x_width = int(properties['x-width'])
    except KeyError:
        # get width of uppercase X
        # TODO: this is correct for monospace but for proportional commonly the ink width is chosen
        # also, for fixed this should take into account pre- and post-offsets?
        xord = ord('X')
        try:
            #FIXME: convert all labels / props to lowercase?
            x_width = glyphs['u+{:04x}'.format(xord)].width
        except KeyError:
            # assume ascii-based encoding
            try:
                x_width = glyphs[xord].width
            except KeyError:
                x_width = 0
    if not font.fixed:
        pitch_and_family = style_map.get(properties['style'], 0) << 4
        pitch_and_family |= 1 # low bit set for proportional
        pix_width = 0
        v3_flags = _DFF_PROPORTIONAL
    else:
        # FF_MODERN - FIXME: is this really always set for fixed-pitch?
        pitch_and_family = 3<<4
        # x_with should equal average width
        # FIXME: take from glyph diemnsions
        x_width = pix_width = _get_prop_x(properties['size'])
        v3_flags = _DFF_FIXED
    # FIXME: set ABC flag if offsets are nonzero
    # FIXME: get from glyphs
    pix_height = _get_prop_y(properties['size'])
    # FIXME: find ordinal of space character (word-boundary); here we assume font starts at 32
    space_index = 0
    # char table
    ord_glyphs = [
        font.get_glyph(_ord)
        for _ord in range(min(font.ordinals), max(font.ordinals)+1)
    ]
    # add the guaranteed-blank glyph
    ord_glyphs.append(Glyph.empty(pix_width, pix_height))
    offset_chartbl = _FNT_HEADER.size + _FNT_HEADER_3.size
    ct_header = _CT_VERSION_HEADER[0x300]
    offset_bitmaps = offset_chartbl + len(ord_glyphs) * ct_header.size

    bitmaps = [
        _glyph.as_bytes()
        for _glyph in ord_glyphs
    ]
    # bytewise transpose - .FNT stores as contiguous 8-pixel columns
    bitmaps = [
        b''.join(
            _bm[_col::len(_bm)//_glyph.height]
            for _col in range(len(_bm)//_glyph.height)
        )
        for _glyph, _bm in zip(ord_glyphs, bitmaps)
    ]
    glyph_offsets = [0] + list(itertools.accumulate(len(_bm) for _bm in bitmaps))
    char_table = [
        bytes(ct_header(_glyph.width, offset_bitmaps + _glyph_offset))
        for _glyph, _glyph_offset in zip(ord_glyphs, glyph_offsets)
    ]
    file_size = offset_bitmaps + glyph_offsets[-1] #+ len(bitmaps[-1]) ## WHY NOT??

    face_name_offset = file_size
    face_name = properties['family'].encode('latin-1', 'replace') + b'\0'
    device_name_offset = face_name_offset + len(face_name)
    device_name = b'' #properties.get('device', '').encode('latin-1', 'replace') + b'\0'

    file_size = device_name_offset + len(device_name)

    if not device_name:
        # set device name pointer to zero for 'generic font'
        device_name_offset = 0

    win_props = _FNT_HEADER(
        dfVersion=0x300,
        dfSize=file_size,
        dfCopyright=properties['copyright'].encode('ascii', 'replace')[:60].ljust(60, b'\0'),
        dfType=0, # raster, not in memory
        dfPoints=int(properties['points']),
        dfVertRes=_get_prop_y(properties['dpi']),
        dfHorizRes=_get_prop_x(properties['dpi']),
        dfAscent=int(properties['ascent']),
        dfInternalLeading=0,
        dfExternalLeading=int(properties['leading']),
        dfItalic=(properties['slant'] in ('italic', 'oblique')),
        dfUnderline=('decoration' in properties and 'underline' in properties['decoration']),
        dfStrikeOut=('decoration' in properties and 'strikethrough' in properties['decoration']),
        dfWeight=weight_map.get(properties['weight'], weight_map['regular']),
        dfCharSet=charset_map.get(properties['encoding'], properties['encoding']),
        dfPixWidth=pix_width,
        dfPixHeight=pix_height,
        dfPitchAndFamily=pitch_and_family,
        dfAvgWidth=x_width,
        dfMaxWidth=font.max_width,
        dfFirstChar=min(font.ordinals),
        dfLastChar=max(font.ordinals),
        dfDefaultChar=int(properties.get('default-char', 0), 0), # 0 is default if none provided
        dfBreakChar=int(properties.get('word-boundary', 0), space_index),
        # round up to multiple of 2 bytes to word-align v1.0 strikes (not used for v2.0+ ?)
        dfWidthBytes=pad(ceildiv(font.max_width, 8), 1),
        dfDevice=device_name_offset,
        dfFace=face_name_offset,
        dfBitsPointer=0, # used on loading
        dfBitsOffset=offset_bitmaps,
    )
    # version-specific header extensions
    v3_header_ext = _FNT_HEADER_3(
        dfReserved=0,
        dfFlags=v3_flags,
        dfAspace=properties.get('offset-before', 0),
        dfBspace=0,
        dfCspace=properties.get('offset-after', 0),
        dfColorPointer=0,
        dfReserved1=b'\0'*16,
    )
    fnt = (
        bytes(win_props) + bytes(v3_header_ext) + b''.join(char_table)
        + b''.join(bitmaps)
        + face_name + device_name
    )
    assert offset_chartbl == len(bytes(win_props) + bytes(v3_header_ext)), 'chtblofs'
    assert offset_bitmaps == len(bytes(win_props) + bytes(v3_header_ext) + b''.join(char_table)), 'btmofs'

    assert len(fnt) == file_size, repr((len(fnt), file_size))
    return fnt




##############################################################################
# windows .FON writer


_STUB_CODE = bytes((
  0xBA, 0x0E, 0x00, # mov dx,0xe
  0x0E,             # push cs
  0x1F,             # pop ds
  0xB4, 0x09,       # mov ah,0x9
  0xCD, 0x21,       # int 0x21
  0xB8, 0x01, 0x4C, # mov ax,0x4c01
  0xCD, 0x21        # int 0x21
))
_STUB_MSG = b'This is a Windows font file.\r\n'

_MZ_HEADER = friendlystruct(
    '<',
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

_NE_HEADER = friendlystruct(
    '<',
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

def _dos_stub():
    """Create a small MZ executable."""
    dos_stub_size = _MZ_HEADER.size + len(_STUB_CODE) + len(_STUB_MSG) + 1
    num_pages = ceildiv(dos_stub_size, 512)
    last_page_length = dos_stub_size % 512
    mod = dos_stub_size % 16
    if mod:
        padding = b'\0' * (16-mod)
    else:
        padding = b''
    ne_offset = dos_stub_size + len(padding)
    mz_header = _MZ_HEADER(
        magic=b'MZ',
        last_page_length=last_page_length,
        num_pages=num_pages,
        num_relocations=0,
        header_size=4,
        # 16 extra para for stack
        min_allocation=0x10,
        # maximum extra paras: LOTS
        max_allocation=0xffff,
        initial_ss=0,
        initial_sp=0x100,
        checksum=0,
        # CS:IP = 0:0, start at beginning
        initial_csip=0,
        relocation_table_offset=0x40,
        overlay_number=0,
        reserved_0=b'\0'*4,
        behavior_bits=0,
        reserved_1=b'\0'*26,
        ne_offset=ne_offset
    )
    dos_stub = bytes(mz_header) + _STUB_CODE + _STUB_MSG + b'$' + padding
    return dos_stub


_TYPEINFO = friendlystruct(
    '<',
    rtTypeID='H',
    rtResourceCount='H',
    rtReserved='L',
    #rtNameInfo=_NAMEINFO * rtResourceCount
)

_NAMEINFO = friendlystruct(
    '<',
    rnOffset='H',
    rnLength='H',
    rnFlags='H',
    rnID='H',
    rnHandle='H',
    rnUsage='H',
)
# type ID values that matter to us
_RT_FONTDIR = 0x8007
_RT_FONT = 0x8008


def _create_fontdirentry(fnt, properties):
    """Return the FONTDIRENTRY, given the data in a .FNT file."""
    face_name = properties['family'].encode('latin-1', 'replace') + b'\0'
    device_name = properties.get('device', '').encode('latin-1', 'replace') + b'\0'
    return (
        fnt[0:0x71] +
        device_name +
        face_name
    )

def _create_fon(typeface):
    """Create a .FON font library, given a bunch of .FNT file contents."""

    # use font-familt name of first font
    name = typeface._fonts[0]._properties['family']

    # construct the FNT resources
    fonts = [_create_fnt(_font) for _font in typeface._fonts]

    # The MZ stub.
    stubdata = _dos_stub()

    # Non-resident name table should contain a FONTRES line.
    # FIXME: are these dpi numbers?
    nonres = b'FONTRES 100,96,96 : ' + name.encode('ascii')
    nonres = struct.pack('B', len(nonres)) + nonres + b'\0\0\0'

    # Resident name table should just contain a module name.
    mname = bytes(
        _c for _c in name.encode('ascii', 'ignore')
        if _c in set(string.ascii_letters + string.digits)
    )
    res = struct.pack('B', len(mname)) + mname + b'\0\0\0'

    # Entry table / imported names table should contain a zero word.
    entry = struct.pack('<H', 0)

    # Compute length of resource table.
    # 12 (2 for the shift count, plus 2 for end-of-table, plus 8 for the
    #    "FONTDIR" resource name), plus
    # 20 for FONTDIR (TYPEINFO and NAMEINFO), plus
    # 8 for font entry TYPEINFO, plus
    # 12 for each font's NAMEINFO

    # Resources are currently one FONTDIR plus n fonts.
    resrcsize = 12 + 20 + 8 + 12 * len(fonts)
    resrcpad = ((resrcsize + 15) & ~15) - resrcsize

    # Now position all of this after the NE header.
    off_segtable = off_restable = _NE_HEADER.size # 0x40
    off_res = off_restable + resrcsize + resrcpad
    off_modref = off_import = off_entry = off_res + len(res)
    off_nonres = off_modref + len(entry)
    size_unpadded = off_nonres + len(nonres)
    pad = ((size_unpadded + 15) & ~15) - size_unpadded
    # Now q is file offset where the real resources begin.
    real_resource_offset = size_unpadded + pad + len(stubdata)

    # Construct the FONTDIR.
    fontdir = struct.pack('<H', len(fonts))
    for i in range(len(fonts)):
        fontdir += struct.pack('<H', i+1) + _create_fontdirentry(
            fonts[i], typeface._fonts[i]._properties
        )
    resdata = fontdir
    while len(resdata) % 16: # 2 << rscAlignShift
        resdata = resdata + b'\0'
    font_start = [len(resdata)]

    # The FONT resources.
    for i in range(len(fonts)):
        resdata = resdata + fonts[i]
        while len(resdata) % 16:
            resdata = resdata + b'\0'
        font_start.append(len(resdata))


    # The FONTDIR resource table entry
    typeinfo_fontdir = _TYPEINFO(
        rtTypeID=_RT_FONTDIR,
        rtResourceCount=1,
        rtReserved=0,
    )
    # this should be an array, but with only one element...
    nameinfo_fontdir = _NAMEINFO(
        rnOffset=real_resource_offset >> 4, # >> rscAlignShift
        rnLength=len(resdata) >> 4,
        rnFlags=0x0c50, # PRELOAD=0x0040 | MOVEABLE=0x0010 | 0x0c00
        rnID=resrcsize-8,
        rnHandle=0,
        rnUsage=0,
    )

    # FONT resource table entry
    typeinfo_font = _TYPEINFO(
        rtTypeID=_RT_FONT,
        rtResourceCount=len(fonts),
        rtReserved=0,
    )
    nameinfo_font = [
        _NAMEINFO(
            rnOffset=(real_resource_offset+font_start[_i]) >> 4, # >> rscAlignShift
            rnLength=(font_start[_i+1]-font_start[_i]) >> 4,
            rnFlags=0x1c30, # PURE=0x0020 | MOVEABLE=0x0010 | 0x1c00
            rnID=0x8001+_i,
            rnHandle=0,
            rnUsage=0,
        )
        for _i in range(len(fonts))
    ]

    # construct the resource table
    rscAlignShift = struct.pack('<H', 4) # rscAlignShift: shift count 2<<n
    rscTypes = (
        bytes(typeinfo_fontdir) + bytes(nameinfo_fontdir)
        + bytes(typeinfo_font) + b''.join(bytes(_ni) for _ni in nameinfo_font)
    )
    rscEndTypes = b'\0\0' # The zero word.
    rscResourceNames = b'\x07FONTDIR'
    rscEndNames = b'\0'
    restable = rscAlignShift + rscTypes + rscEndTypes + rscResourceNames + rscEndNames

    # resrcsize underestimates struct length by 1
    restable = restable + b'\0' * (resrcpad-1)

    assert resrcsize == (
        12 + # len(rscAlignShift) + len(rscEndTypes) + len(rscResourceNames)
        20 +  #_TYPEINFO.size + _NAMEINFO.size * 1 (for FONTDIR)
        8 + # TYPEINFO.size (for FONTS)
        12 * len(fonts) # _NAMEINFO.size * len(fonts)
    )

    ne_header = _NE_HEADER(
        magic=b'NE',
        linker_major_version=5,
        linker_minor_version=10,
        entry_table_offset=off_entry,
        entry_table_length=len(entry),
        file_load_crc=0,
        program_flags=0x08,
        application_flags=0x83,
        auto_data_seg_index=0,
        initial_heap_size=0,
        initial_stack_size=0,
        entry_point_csip=0,
        initial_stack_pointer_sssp=0,
        segment_count=0,
        module_ref_count=0,
        nonresident_names_table_size=len(nonres),
        seg_table_offset=off_segtable,
        res_table_offset=off_restable,
        resident_names_table_offset=off_res,
        module_ref_table_offset=off_modref,
        imp_names_table_offset=off_import,
        nonresident_names_table_offset=len(stubdata) + off_nonres,
        movable_entry_point_count=0,
        file_alignment_size_shift_count=4,
        number_res_table_entries=0,
        target_os=2,
        other_os2_exe_flags=8,
        return_thunks_offset=0,
        seg_ref_thunks_offset=0,
        min_code_swap_size=0,
        expected_windows_version=0x300
    )

    file = stubdata + bytes(ne_header) + restable + res + entry + nonres + b'\0' * pad + resdata
    return file
