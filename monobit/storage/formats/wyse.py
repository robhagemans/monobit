"""
monobit.storage.formats.wyse - Wyse-60 soft font

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# http://bitsavers.org/pdf/wyse/WY-60/880261-01A_WY-60_Programmers_Guide_Jan87.pdf
# pp 48--52

import logging

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Raster, Glyph
from monobit.base import Coord


@loaders.register(
    name='wyse',
    # maybe
    magic=(b'\x1bcA',)
)
def load_wyse(instream):
    """Load character-cell fonts from Wyse-60 soft font file."""
    glyphs = []
    while True:
        tri = instream.peek(3)
        if len(tri) < 3:
            break
        if tri[:3] == b'\x1bcA':
            glyphs.append(_read_wyse_glyph(instream))
        else:
            instream.read(1)
    if not glyphs:
        raise FileFormatError(
            'Not a Wyse-60 soft font: ESC c A sequence not found.'
        )
    return Font(glyphs)


def _read_wyse_glyph(instream):
    esc_seq = instream.read(3)
    try:
        bank = int(instream.read(1))
        codepoint = bytes.fromhex(instream.read(2).decode('ascii'))
        glyph = Glyph.from_hex(
            instream.read(32).decode('ascii'), width=8, codepoint=codepoint
        )
        # rightmost column should be repeated
        glyph = glyph.expand(right=2)
    except (ValueError, UnicodeError) as e:
        raise FileFormatError(
            'Not a Wyse-60 soft font: malformed character definition.'
        ) from e
    ctrl_y = instream.read(1)
    return glyph
