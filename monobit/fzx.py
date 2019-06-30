"""
monobit.fzx - FZX format

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import ctypes

from .binary import ceildiv, friendlystruct
from .raw import load_aligned
from .typeface import Typeface
from .font import Font, Label
from .glyph import Glyph


# https://faqwiki.zxnet.co.uk/wiki/FZX_format

_FZX_HEADER = friendlystruct(
    'le',
    height='uint8',
    tracking='int8', # 'should normally be a positive number' .. 'may be zero'
    lastchar='uint8',
)

class _CHAR_ENTRY(ctypes.LittleEndianStructure):
    _fields_ = [
        # kern, shift are the high byte
        # but in ctypes, little endian ordering also seems to hold for bit fields
        ('offset', ctypes.c_uint16, 14),
        ('kern', ctypes.c_uint16, 2),
        # this is width-1
        ('width', ctypes.c_uint8, 4),
        ('shift', ctypes.c_uint8, 4),
    ]
    _pack_ = True


@Typeface.loads('fzx', name='FZX', binary=True)
def load(instream):
    """Load font from FZX file."""
    data = instream.read()
    header = _FZX_HEADER.from_bytes(data)
    logging.info(header)
    n_chars = header.lastchar - 32 + 1
    char_table = (_CHAR_ENTRY * n_chars).from_buffer_copy(data, _FZX_HEADER.size)
    logging.info(list((x.kern, x.width, x.shift) for x in char_table))
    # offsets seem to be given relative to the entry in the char table; convert to absolute offsets
    offsets = [
        _FZX_HEADER.size + ctypes.sizeof(_CHAR_ENTRY) * _i + _entry.offset
        for _i, _entry in enumerate(char_table)
    ] + [None]
    logging.info(offsets)
    glyph_bytes = [data[_offs:_next] for _offs, _next in zip(offsets[:-1], offsets[1:])]
    glyphs = [
        Glyph.from_bytes(_glyph, _entry.width+1)
        for _glyph, _entry in zip(glyph_bytes, char_table)
    ]
    # resize glyphs
    max_kern = max(_entry.kern for _entry in char_table)
    glyphs = [
        _glyph.expand(
            top=_entry.shift,
            bottom=header.height-_glyph.height-_entry.shift,
            left=max_kern-_entry.kern,
            # only necessary to fix empty glyphs
            right=_entry.width+1-_glyph.width
        )
        for _glyph, _entry in zip(glyphs, char_table)
    ]
    properties = {
        # TODO: determine vertical offset from e.g. character 'x'
        'offset': (-max_kern, 0),
        'tracking': header.tracking,
        'encoding': 'zx-spectrum',
    }
    labels = {_i + 32: _i for _i, _ in enumerate(glyphs)}
    return Typeface([Font(glyphs, labels, (), properties)])
