"""
monobit.storage.formats.softfont.wyse - Wyse-60 soft font

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# http://bitsavers.org/pdf/wyse/WY-60/880261-01A_WY-60_Programmers_Guide_Jan87.pdf
# pp 48--52

import logging

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Raster, Glyph
from monobit.base import Coord

from monobit.storage.utils.limitations import ensure_single, ensure_charcell


_WYSE_ESC_SEQ = b'\x1bcA'


@loaders.register(
    name='wyse',
    # maybe
    magic=(_WYSE_ESC_SEQ,)
)
def load_wyse(instream):
    """Load character-cell fonts from Wyse-60 soft font file."""
    glyphs = []
    while True:
        tri = instream.peek(3)
        if len(tri) < 3:
            break
        if tri[:3] == _WYSE_ESC_SEQ:
            glyphs.append(_read_wyse_glyph(instream))
        else:
            instream.read(1)
    if not glyphs:
        raise FileFormatError(
            'Not a Wyse-60 soft font: ESC c A sequence not found.'
        )
    return Font(glyphs)


def _read_wyse_glyph(instream):
    """Read a single-glyph escape sequence."""
    esc_seq = instream.read(3)
    try:
        bank = int(instream.read(1))
        codepoint, = bytes.fromhex(instream.read(2).decode('ascii'))
        glyph = Glyph.from_hex(
            instream.read(32).decode('ascii'), width=8,
            # interpret bank value (first char) as part of codepoint
            # alternatively, we could define 3 fonts, one per bank
            codepoint=bank * 0x100 + codepoint,
        )
        # rightmost column should be repeated
        glyph = glyph.expand(right=2)
    except (ValueError, UnicodeError) as e:
        raise FileFormatError(
            'Not a Wyse-60 soft font: malformed character definition.'
        ) from e
    ctrl_y = instream.read(1)
    return glyph


@savers.register(linked=load_wyse)
def save_wyse(fonts, outstream):
    """Save character-cell fonts to Wyse-60 soft font file."""
    font = ensure_single(fonts)
    font = ensure_charcell(font)
    if (font.cell_size.x > 8 or font.cell_size.y > 16):
        raise ValueError(
            'This format can only store character-cell fonts '
            'of cell-size 8x16 or smaller.'
        )
    font = font.label(codepoint_from=font.encoding)
    for glyph in font.glyphs:
        _write_wyse_glyph(glyph, outstream)


def _write_wyse_glyph(glyph, outstream):
    """Write a single-glyph escape sequence."""
    glyph = glyph.expand(right=8-glyph.width, bottom=16-glyph.height)
    if glyph.codepoint and int(glyph.codepoint) <= 0x3ff:
        outstream.write(_WYSE_ESC_SEQ)
        outstream.write(b'%03X' % int(glyph.codepoint))
        outstream.write(glyph.as_hex().upper().encode('ascii'))
        outstream.write(b'\x19')
    else:
        logging.warning(
            'Cannot encode codepoints > 0x3ff. '
            f'Skipping {glyph.codepoint}.'
        )
