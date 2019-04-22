"""
monobit.amiga - read Amiga font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import struct
import logging

from .base import Font, ensure_stream


# amiga header constants
_MAXFONTPATH = 256
_MAXFONTNAME = 32

# hunk ids
# http://amiga-dev.wikidot.com/file-format:hunk
_HUNK_HEADER = 0x3f3
_HUNK_CODE = 0x3e9
_HUNK_RELOC32 = 0x3ec
_HUNK_END = 0x3f2


class _FileUnpacker:
    """Wrapper for struct.unpack."""

    def __init__(self, stream):
        """Start at start."""
        self._stream = stream
        self._offset = 0

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
    # in theory this is font/file metadata
    # but name is only a placeholder, seems to be empty
    fileid, rev, seg, name = reader.unpack('>HHi%ds' % (_MAXFONTNAME,)) # 8+32b
    if b'\0' in name:
        name, _ = name.split(b'\0', 1)
    logging.info('id: %d revision: %d name: "%s"', fileid, rev, name.decode('latin-1'))
    # struct Message at start of struct TextFont
    # pln_succ, pln_pred, ln_type, ln_pri, pln_name, pmn_replyport, mn_length
    reader.unpack('>IIBbIIH') # 20b
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03DE.html
    # struct TextFont {
    #     struct Message tf_Message;  /* reply message for font removal */
    #     UWORD   tf_YSize;
    #     UBYTE   tf_Style;
    #     UBYTE   tf_Flags;
    #     UWORD   tf_XSize;
    #     UWORD   tf_Baseline;
    #     UWORD   tf_BoldSmear; /* smear to affect a bold enhancement */
    #
    #     UWORD   tf_Accessors;
    #     UBYTE   tf_LoChar;
    #     UBYTE   tf_HiChar;
    #     APTR    tf_CharData;  /* the bit character data */
    #
    #     UWORD   tf_Modulo;  /* the row modulo for the strike font data  */
    #     APTR    tf_CharLoc; /* ptr to location data for the strike font */
    #                         /*   2 words: bit offset then size          */
    #     APTR    tf_CharSpace;
    #                        /* ptr to words of proportional spacing data */
    #     APTR    tf_CharKern; /* ptr to words of kerning data            */
    # };

    # struct Message
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    # struct Message {
    #     struct Node     mn_Node;
    #     struct MsgPort *mn_ReplyPort;
    #     UWORD           mn_Length;
    # };
    # font properties
    ysize, style, flags, xsize, baseline, boldsmear, accessors, lochar, hichar = reader.unpack('>HBBHHHHBB') #, f.read(2+2+4*2+2))
    logging.info(
        'x: %d y: %d style: %02x flags: %02x baseline: %d boldsmear: %d',
        xsize, ysize, style, flags, baseline, boldsmear
    )
    proportional = bool(flags & 0x20)
    logging.info('proportional: %r', proportional)
    # data structure parameters
    tf_chardata, tf_modulo, tf_charloc, tf_charspace, tf_charkern = reader.unpack('>IHIII') #, f.read(18))
    # char data
    f.seek(tf_chardata+loc, 0)
    assert f.tell() - loc == tf_chardata
    rows = [
        ''.join(
            '{:08b}'.format(_c)
            for _c in reader.read(tf_modulo)
        )
        for _ in range(ysize)
    ]
    rows = [
        [
            _c != '0'
            for _c in _row
        ]
        for _row in rows
    ]
    # location data
    f.seek(tf_charloc+loc, 0)
    #assert f.tell() - loc == tf_charloc
    nchars = hichar - lochar + 1 + 1 # one additional glyph at end for undefined chars
    locs = [reader.unpack('>HH') for  _ in range(nchars)]
    # spacing data, can be negative
    f.seek(tf_charspace+loc, 0)
    #assert f.tell() - loc == tf_charspace
    spacing = reader.unpack('>%dh' % (nchars,))
    # kerning data, can be negative
    f.seek(tf_charkern+loc, 0)
    #assert f.tell() - loc == tf_charkern
    kerning = reader.unpack('>%dh' % (nchars,))
    #assert reader.unpack('>H') == (0,)
    #assert f.tell() - loc == num_longs*4
    # apparently followed by _HUNK_RELOC32 and _HUNK_END
    font = [
        [_row[_offs: _offs+_width] for _row in rows]
        for _offs, _width in locs
    ]
    if proportional:
        # apply spacing
        for i, sp in enumerate(spacing):
            if sp < 0:
                logging.info('warning: negative spacing in %dth character' % (i,))
        font = [
            [_row + [False] * (_width - len(_row)) for _row in _char]
            for _char, _width in zip(font, spacing)
        ]
    logging.info('kerning table: %r', kerning)
    glyphs = dict(enumerate(font, lochar))
    return Font(glyphs)


@Font.loads('amiga')
def load(f):
    """Read Amiga disk font file."""
    with ensure_stream(f, 'rb'):
        # read & ignore header
        _read_header(f)
        if _read_ulong(f) != _HUNK_CODE:
            raise ValueError('Not an Amiga font data file: no code hunk found (id %04x)' % hunk_id)
        return _read_font_hunk(f)
