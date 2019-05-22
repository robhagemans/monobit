"""
monobit.amiga - read Amiga font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import struct
import logging

from .base import VERSION, Glyph, Font, Typeface, friendlystruct, bytes_to_bits


# amiga header constants
_MAXFONTPATH = 256
_MAXFONTNAME = 32

# hunk ids
# http://amiga-dev.wikidot.com/file-format:hunk
_HUNK_HEADER = 0x3f3
_HUNK_CODE = 0x3e9
_HUNK_RELOC32 = 0x3ec
_HUNK_END = 0x3f2

# tf_Flags values
# font is in rom
_FPF_ROMFONT = 0x01
# font is from diskfont.library
_FPF_DISKFONT = 0x02
# This font is designed to be printed from from right to left
_FPF_REVPATH = 0x04
# This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
_FPF_TALLDOT = 0x08
# This font was designed for a Lores Interlaced screen (320x400 NTSC)
_FPF_WIDEDOT = 0x10
# character sizes can vary from nominal
_FPF_PROPORTIONAL = 0x20
# size explicitly designed, not constructed
_FPF_DESIGNED = 0x40
# the font has been removed
_FPF_REMOVED = 0x80

# tf_Style values
# underlined (under baseline)
_FSF_UNDERLINED	= 0x01
# bold face text (ORed w/ shifted)
_FSF_BOLD = 0x02
# italic (slanted 1:2 right)
_FSF_ITALIC	= 0x04
# extended face (wider than normal)
_FSF_EXTENDED = 0x08
# this uses ColorTextFont structure
_FSF_COLORFONT = 0x40
# the TextAttr is really a TTextAttr
_FSF_TAGGED = 0x80

# disk font header
_AMIGA_HEADER = friendlystruct(
    '>',
    # struct DiskFontHeader
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node05F9.html#line61
    dfh_NextSegment='I',
    dfh_ReturnCode='I',
    # struct Node
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    dfh_ln_Succ='I',
    dfh_ln_Pred='I',
    dfh_ln_Type='B',
    dfh_ln_Pri='b',
    dfh_ln_Name='I',
    dfh_FileID='H',
    dfh_Revision='H',
    dfh_Segment='i',
    dfh_Name='{}s'.format(_MAXFONTNAME),
    # struct Message at start of struct TextFont
    # struct Message http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    tf_ln_Succ='I',
    tf_ln_Pred='I',
    tf_ln_Type='B',
    tf_ln_Pri='b',
    tf_ln_Name='I',
    tf_mn_ReplyPort='I',
    tf_mn_Length='H',
    # struct TextFont http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03DE.html
    tf_YSize='H',
    tf_Style='B',
    tf_Flags='B',
    tf_XSize='H',
    tf_Baseline='H',
    tf_BoldSmear='H',
    tf_Accessors='H',
    tf_LoChar='B',
    tf_HiChar='B',
    tf_CharData='I',
    tf_Modulo='H',
    tf_CharLoc='I',
    tf_CharSpace='I',
    tf_CharKern='I',
)


@Typeface.loads('amiga', encoding=None)
def load(f):
    """Read Amiga disk font file."""
    # read & ignore header
    _read_header(f)
    hunk_id = _read_ulong(f)
    if hunk_id != _HUNK_CODE:
        raise ValueError('Not an Amiga font data file: no code hunk found (id %04x)' % hunk_id)
    glyphs, labels, props = _read_font_hunk(f)
    return Typeface([Font(glyphs, labels, properties=props)])


class _FileUnpacker:
    """Wrapper for struct.unpack."""

    def __init__(self, stream):
        """Start at start."""
        self._stream = stream

    def unpack(self, format):
        """Read the next data specified by format string."""
        return struct.unpack(format, self._stream.read(struct.calcsize(format)))

    def read(self, n_bytes=-1):
        """Read number of raw bytes."""
        return self._stream.read(n_bytes)


def _read_ulong(f):
    """Read a 32-bit unsigned long."""
    return struct.unpack('>I', f.read(4))[0]

def _read_string(f):
    num_longs = _read_ulong(f)
    if num_longs < 1:
        return b''
    string = f.read(num_longs * 4)
    idx = string.find(b'\0')
    return string[:idx]

def _read_header(f):
    """Read file header."""
        # read header id
    if _read_ulong(f) != _HUNK_HEADER:
        raise ValueError('Not an Amiga font data file: incorrect magic constant')
    # null terminated list of strings
    library_names = []
    while True:
        s = _read_string(f)
        if not s:
            break
        library_names.append(s)
    table_size, first_slot, last_slot = struct.unpack('>III', f.read(12))
    # list of memory sizes of hunks in this file (in number of ULONGs)
    # this seems to exclude overhead, so not useful to determine disk sizes
    num_sizes = last_slot - first_slot + 1
    hunk_sizes = struct.unpack('>%dI' % (num_sizes,), f.read(4 * num_sizes))
    return library_names, table_size, first_slot, last_slot, hunk_sizes

def _read_font_hunk(f):
    """Parse the font data blob."""
    #loc = f.tell() + 4
    amiga_props = _AMIGA_HEADER.read_from(f)
    # the reference point for locations in the hunk is just after the ReturnCode
    loc = - _AMIGA_HEADER.size + 4
    # remainder is the font strike
    data = f.read()
    # read character data
    glyphs, labels, min_kern = _read_strike(
        data, amiga_props.tf_XSize, amiga_props.tf_YSize,
        amiga_props.tf_Flags & _FPF_PROPORTIONAL,
        amiga_props.tf_Modulo, amiga_props.tf_LoChar, amiga_props.tf_HiChar,
        amiga_props.tf_CharData + loc, amiga_props.tf_CharLoc + loc,
        amiga_props.tf_CharSpace + loc, amiga_props.tf_CharKern + loc
    )
    props = _parse_amiga_props(amiga_props, min_kern)
    props['source-name'] = '/'.join(f.name.split(os.sep)[-2:])
    # the file name tends to be the name as given in the .font anyway
    if 'name' not in props:
        props['name'] = props['source-name']
    props['family'] = props['name'].split('/')[0].split(' ')[0]
    return glyphs, labels, props

def _parse_amiga_props(amiga_props, min_kern):
    """Convert AmigaFont properties into yaff properties."""
    if amiga_props.tf_Style & _FSF_COLORFONT:
        raise ValueError('Amiga ColorFont not supported')
    props = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': 'AmigaFont',
    }
    # preserve tags stored in name field after \0
    name, *tags = amiga_props.dfh_Name.decode('latin-1').split('\0')
    for i, tag in enumerate(tags):
        props['amiga.dfh_Name.{}'.format(i+1)] = tag
    if name:
        props['name'] = name
    props['revision'] = amiga_props.dfh_Revision
    props['bottom'] = -(amiga_props.tf_YSize - amiga_props.tf_Baseline)
    props['size'] = amiga_props.tf_YSize
    # tf_Style
    props['weight'] = 'bold' if amiga_props.tf_Style & _FSF_BOLD else 'medium'
    props['slant'] = 'italic' if amiga_props.tf_Style & _FSF_ITALIC else 'roman'
    props['setwidth'] = 'expanded' if amiga_props.tf_Style & _FSF_EXTENDED else 'medium'
    if amiga_props.tf_Style & _FSF_UNDERLINED:
        props['decoration'] = 'underline'
    # tf_Flags
    props['spacing'] = (
        'proportional' if amiga_props.tf_Flags & _FPF_PROPORTIONAL else 'monospace'
    )
    if amiga_props.tf_Flags & _FPF_REVPATH:
        props['direction'] = 'right-to-left'
        logging.warning('right-to-left fonts are not correctly implemented yet')
    if amiga_props.tf_Flags & _FPF_TALLDOT and not amiga_props.tf_Flags & _FPF_WIDEDOT:
        # TALLDOT: This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
        props['dpi'] = '96 48'
    elif amiga_props.tf_Flags & _FPF_WIDEDOT and not amiga_props.tf_Flags & _FPF_TALLDOT:
        # WIDEDOT: This font was designed for a Lores Interlaced screen (320x400 NTSC)
        props['dpi'] = '48 96'
    else:
        props['dpi'] = 96
    if min_kern < 0:
        props['offset-before'] = min_kern
    props['encoding'] = 'iso8859-1'
    props['default-char'] = 'default'
    # preserve unparsed properties
    # tf_BoldSmear; /* smear to affect a bold enhancement */
    # use the most common value 1 as a default
    if amiga_props.tf_BoldSmear != 1:
        props['amiga.tf_BoldSmear'] = amiga_props.tf_BoldSmear
    return props

def _read_strike(
        data, xsize, ysize, proportional, modulo, lochar, hichar,
        pos_chardata, pos_charloc, pos_charspace, pos_charkern
    ):
    """Read and interpret the font strike and related tables."""
    rows = [
        bytes_to_bits(data[pos_chardata + _item*modulo : pos_chardata + (_item+1)*+modulo])
        for _item in range(ysize)
    ]
    # location data
    nchars = hichar - lochar + 1 + 1 # one additional glyph at end for undefined chars
    loc_struct = friendlystruct('>', offset='H', width='H')
    locs = [
        loc_struct.from_bytes(data, pos_charloc+_i*loc_struct.size)
        for _i in range(nchars)
    ]
    font = [
        [_row[_loc.offset: _loc.offset+_loc.width] for _row in rows]
        for _loc in locs
    ]
    # spacing data, can be negative
    if proportional:
        spc_struct = friendlystruct('>', space='h')
        spacing = [
            spc_struct.from_bytes(data, pos_charspace+_i*spc_struct.size).space
            for _i in range(nchars)
        ]
        # apply spacing
        for i, sp in enumerate(spacing):
            if sp < 0:
                logging.warning('negative spacing of %d in %dth character' % (sp, i,))
            if abs(sp) > xsize*2:
                logging.error('very high values in spacing table')
                spacing = (xsize,) * len(font)
                break
    else:
        spacing = (xsize,) * len(font)
    if pos_charkern is not None:
        # kerning data, can be negative
        kern_struct = friendlystruct('>', kern='h')
        kerning = [
            kern_struct.from_bytes(data, pos_charkern+_i*kern_struct.size).kern
            for _i in range(nchars)
        ]
        for i, sp in enumerate(kerning):
            if abs(sp) > xsize*2:
                logging.error('very high values in kerning table')
                kerning = (0,) * len(font)
                break
    else:
        kerning = (0,) * len(font)
    # deal with negative kerning by turning it into a global negative offset
    min_kern = min(kerning)
    if min_kern < 0:
        kerning = (_kern - min_kern for _kern in kerning)
    glyphs = [
        Glyph(tuple((False,) * _kern + _row + (False,) * (_width-_kern-len(_row)) for _row in _char))
        for _char, _width, _kern in zip(font, spacing, kerning)
    ]
    # default glyph doesn't have an encoding value
    labels = {
        _i + lochar: _i for _i in range(len(glyphs)-1)
    }
    labels['default'] = len(glyphs) - 1
    return glyphs, labels, min_kern
