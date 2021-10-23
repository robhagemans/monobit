"""
monobit.fzx - FZX format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import ctypes

from ..binary import ceildiv
from ..struct import bitfield, little_endian as le
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph


# https://faqwiki.zxnet.co.uk/wiki/FZX_format

_FZX_HEADER = le.Struct(
    height='uint8',
    tracking='int8', # 'should normally be a positive number' .. 'may be zero'
    lastchar='uint8',
)

_CHAR_ENTRY = le.Struct(
    # kern, shift are the high byte
    # but in ctypes, little endian ordering also seems to hold for bit fields
    offset=bitfield('uint16', 14),
    kern=bitfield('uint16', 2),
    # this is actually width-1
    width=bitfield('uint8', 4),
    shift=bitfield('uint8', 4),
)


@loaders.register('fzx', name='FZX')
def load_fzx(instream, where=None):
    """Load font from ZX Spectrum .FZX file."""
    data = instream.read()
    header = _FZX_HEADER.from_bytes(data)
    n_chars = header.lastchar - 32 + 1
    char_table = _CHAR_ENTRY.array(n_chars).from_bytes(data, _FZX_HEADER.size)
    # offsets seem to be given relative to the entry in the char table; convert to absolute offsets
    offsets = [
        _FZX_HEADER.size + _CHAR_ENTRY.size * _i + _entry.offset
        for _i, _entry in enumerate(char_table)
    ] + [None]
    glyph_bytes = [
        data[_offs:_next]
        for _offs, _next in zip(offsets[:-1], offsets[1:])
    ]
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
            # +1 because _entry.width is actually width-1
            right=(_entry.width+1)-_glyph.width
        )
        for _glyph, _entry in zip(glyphs, char_table)
    ]
    properties = {
        'offset': (-max_kern, 0),
        'tracking': header.tracking,
        'encoding': 'zx-spectrum',
    }
    glyphs = [
        _glyph.set_annotations(codepoint=(_index+32,))
        for _index, _glyph in enumerate(glyphs)
    ]
    return Font(glyphs, properties=properties)
