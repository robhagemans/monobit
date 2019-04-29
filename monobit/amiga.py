"""
monobit.amiga - read Amiga font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import struct
import logging

from .base import VERSION, Font, ensure_stream


# amiga header constants
_MAXFONTPATH = 256
_MAXFONTNAME = 32

# hunk ids
# http://amiga-dev.wikidot.com/file-format:hunk
_HUNK_HEADER = 0x3f3
_HUNK_CODE = 0x3e9
_HUNK_RELOC32 = 0x3ec
_HUNK_END = 0x3f2


_FLAGS_MAP = {
    # I don't think the rom/disk flags are relevant
    #0x01: 'ROMFONT', # font is in rom
    #0x02: 'DISKFONT', # font is from diskfont.library
    # accounted for in direction variable
    #0x04: 'REVPATH', # This font is designed to be printed from from right to left
    0x08: 'TALLDOT', # This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
    0x10: 'WIDEDOT', # This font was designed for a Lores Interlaced screen (320x400 NTSC)
    # this is accounted for in the spacing variable
    #0x20: 'PROPORTIONAL', # character sizes can vary from nominal
    # this is always set
    #0x40: 'DESIGNED', # size explicitly designed, not constructed
    # not relevant
    #0x80: 'REMOVED', # the font has been removed
}


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
    props = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-name': '/'.join(f.name.split(os.sep)[-2:]),
        'source-format': 'Amiga',
    }
    # the file name tends to be the name as given in the .font anyway
    props['name'] = props['source-name']
    reader = _FileUnpacker(f)
    # number of longs in this hunk
    # ? apparently this is also ULONG dfh_NextSegment;
    # ? as per http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node05F9.html#line61
    num_longs, = reader.unpack('>I') # 4 bytes
    loc = f.tell()
    # immediate return code for accidental runs
    # this is ULONG dfh_ReturnCode;
    # MOVEQ  #-1,D0    ; Provide an easy exit in case this file is
    # RTS              ; "Run" instead of merely loaded.
    reader.unpack('>HH') # 2 statements: 4 bytes
    # struct Node
    # pln_succ, pln_pred, ln_type, ln_pri, pln_name
    reader.unpack('>IIBbI') # 14b
    # rev may be the revision number of the font
    # but name is only a placeholder, usually seems to be empty, but some of the bytes get used for versioning tags
    # fileid == 0f80, like a magic number for font files
    fileid, rev, seg, name = reader.unpack('>HHi%ds' % (_MAXFONTNAME,)) # 8+32b
    if b'\0' in name:
        name, name2 = name.split(b'\0', 1)
    else:
        name2 = b''
    if name:
        props['name'] = name.decode('latin-1')
    props['revision'] = rev
    # struct Message at start of struct TextFont
    # struct TextFont http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03DE.html
    # struct Message http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    # pln_succ, pln_pred, ln_type, ln_pri, pln_name, pmn_replyport, mn_length
    reader.unpack('>IIBbIIH') # 20b
    # font properties
    ysize, style, flags, xsize, baseline, boldsmear, accessors, lochar, hichar = reader.unpack('>HBBHHHHBB') #, f.read(2+2+4*2+2))
    props['bottom'] = -(ysize-baseline)
    props['size'] = ysize
    props['weight'] = 'bold' if style & 0x02 else 'medium'
    props['slant'] = 'italic' if style & 0x04 else 'roman'
    props['setwidth'] = 'expanded' if style & 0x08 else 'medium'
    proportional = bool(flags & 0x20)
    props['spacing'] = 'proportional' if proportional else 'monospace'
    if flags & 0x04:
        props['direction'] = 'right-to-left'
        logging.warning('right-to-left fonts are not correctly implemented yet')
    # preserve unparsed properties
    # tf_BoldSmear; /* smear to affect a bold enhancement */
    # use the most common value 1 as a default
    if boldsmear != 1:
        props['_BOLDSMEAR'] = boldsmear
    # preserve tags stored in name field after \0
    if name2.replace(b'\0', b''):
        props['_TAG'] = name2.replace(b'\0', b'').decode('latin-1')
    # preserve unparsed flags
    flag_tags = ' '.join(tag for mask, tag in _FLAGS_MAP.items() if flags & mask)
    if style & 0x01:
        flag_tags = ' '.join(('UNDERLINED', flag_tags))
    if flag_tags:
        props['_PROPERTIES'] = flag_tags
    # data structure parameters
    tf_chardata, tf_modulo, tf_charloc, tf_charspace, tf_charkern = reader.unpack('>IHIII') #, f.read(18))
    glyphs, min_kern = _read_strike(
        f, xsize, ysize, proportional, tf_modulo, lochar, hichar,
        tf_chardata+loc, tf_charloc+loc, tf_charspace+loc, tf_charkern+loc
    )
    if min_kern < 0:
        props['offset-before'] = min_kern
    # default glyph doesn't have an encoding value
    default = max(glyphs)
    glyphs['default'] = glyphs[default]
    del glyphs[default]
    props['encoding'] = 'iso8859-1'
    props['default-char'] = 'default'
    return Font(glyphs, properties=props)

def _read_strike(
        f, xsize, ysize, proportional, modulo, lochar, hichar,
        pos_chardata, pos_charloc, pos_charspace, pos_charkern
    ):
    """Read and interpret the font strike and related tables."""
    reader = _FileUnpacker(f)
    # char data
    f.seek(pos_chardata, 0)
    rows = [
        ''.join(
            '{:08b}'.format(_c)
            for _c in reader.read(modulo)
        )
        for _ in range(ysize)
    ]
    rows = [
        [_c != '0' for _c in _row]
        for _row in rows
    ]
    # location data
    f.seek(pos_charloc, 0)
    nchars = hichar - lochar + 1 + 1 # one additional glyph at end for undefined chars
    locs = [reader.unpack('>HH') for  _ in range(nchars)]
    font = [
        [_row[_offs: _offs+_width] for _row in rows]
        for _offs, _width in locs
    ]
    # spacing data, can be negative
    if proportional:
        f.seek(pos_charspace, 0)
        spacing = reader.unpack('>%dh' % (nchars,))
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
        f.seek(pos_charkern, 0)
        kerning = reader.unpack('>%dh' % (nchars,))

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
    font = [
        [[False] * _kern + _row + [False] * (_width - _kern - len(_row)) for _row in _char]
        for _char, _width, _kern in zip(font, spacing, kerning)
    ]
    glyphs = dict(enumerate(font, lochar))
    return glyphs, min_kern


@Font.loads('amiga')
def load(f):
    """Read Amiga disk font file."""
    with ensure_stream(f, 'rb'):
        # read & ignore header
        _read_header(f)
        if _read_ulong(f) != _HUNK_CODE:
            raise ValueError('Not an Amiga font data file: no code hunk found (id %04x)' % hunk_id)
        return _read_font_hunk(f)
