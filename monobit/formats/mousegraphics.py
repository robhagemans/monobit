"""
monobit.formats.mousegraphics - Apple II MouseGraphics ToolKit Font Format

(c) 2023 Kelvin Sherlock
licence: https://opensource.org/licenses/MIT

See: https://github.com/a2stuff/a2d/blob/main/mgtk/MGTK.md#font
"""

import logging

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..labels import Char
from ..struct import little_endian as le


_HEADER = le.Struct(
    type='uint8', # $00 = single byte, $80 = double-byte
    lastChar='uint8',
    height='uint8'
)
# header is followed by:
# width_table[lastChar+1]
# row0left[lastChar+1]
# row0right[lastChar+1] if double-byte
# ...
# rowNleft[lastChar+1]
# rowNright[lastChar+1] if double-byte
#
# Pixel data is 7-bits (MSB ignored) and stored in reverse order.


@loaders.register(
    name='mgtk'
)
def load_mgtk_fnt(instream):
    """Load font from a MouseGraphics ToolKit font file"""
    font = _parse_mgtk(instream.read())
    return font

def _byte_to_bits(inbyte):
    return tuple(_c == '1' for _c in '{:08b}'.format(inbyte))


def _split_byte(inbyte):
    return _byte_to_bits(inbyte)[:0:-1]


def _parse_mgtk(data):

    header = _HEADER.from_bytes(data)
    offset = _HEADER.size

    logging.debug(header)

    double_width = bool(header.type)
    n_chars = header.lastChar + 1

    widths = le.uint8.array(n_chars).from_bytes(data, offset)
    offset += n_chars

    strike_width = n_chars
    if double_width: strike_width *= 2

    strike = data[offset:offset+strike_width*header.height]

    rows = [
        strike[_r * strike_width : _r * strike_width + strike_width]
        for _r in range(0, header.height)
    ]

    rows = [ tuple(_split_byte(_b) for _b in _r) for _r in rows]

    if double_width:
        # re-assemble the left/right halves
        rows = [
            tuple(_r[_ix] + _r[_ix + n_chars] for _ix in range(n_chars))
            for _r in rows
        ]

    glyphs = [
        Glyph( _row[_offset][0:_width] for _row in rows )
        for _offset, _width in enumerate(widths)
    ]

    glyphs = [
        _g.modify(codepoint=_codepoint)
        for _codepoint, _g in enumerate(glyphs)
    ]

    return Font(glyphs)
