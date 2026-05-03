"""
monobit.storage.fontformats.printer.polyprint - PolyPrint fonts

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# format described by John Elliott at https://www.seasip.info/ZX/polyprint.html

import logging

from monobit.storage import loaders, savers, Magic
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Raster, Glyph, Font, Char
from monobit.base.struct import little_endian as le

from .daisydot import convert_stacked_multipass_glyph


_POLYPRINT_HEADER = le.Struct(
    font_id='uint16',
    name_len='uint8',
    name='25s',
    # unknown flags
    flags0='uint8',
    # this appears to have a bit for double height
    flags1='uint8',
    zero='uint8',
    flags2='uint8',
    # these four bytes seem to be always identical, usually zero
    unknown='uint32',
    flags3='uint8',
    # this seems to hold random memory debris
    unused='91s',
)

_POLYPRINT_GLYPH = le.Struct(
    left='uint8',
    top0=le.uint8 * 20,
    width='uint8',
    top1=le.uint8 * 20,
    right='uint8',
    bot0=le.uint8 * 20,
    unknown='uint8',
    bot1=le.uint8 * 20,
)


@loaders.register(name='polyprint')
def load_polyprint(instream):
    """Load PolyPrint fonts."""
    # described at https://www.seasip.info/Unix/PSF/Amstrad/PolyPrint/index.html
    header = _POLYPRINT_HEADER.read_from(instream)
    glyphs = []
    for cp in range(32, 176):
        gdata = _POLYPRINT_GLYPH.read_from(instream)
        raster = convert_stacked_multipass_glyph(
            gdata.top0, gdata.top1, gdata.bot0, gdata.bot1
        )
        glyph = Glyph(
            raster, codepoint=cp,
            left_bearing=-gdata.left + 1,
            right_bearing=-20 + gdata.left + gdata.width + gdata.right,
        )
        glyphs.append(glyph)
    # this is a guess, flags1==47 in all "large" sample fonts i've seen
    large = header.flags1 & 32
    return Font(
        glyphs,
        name=header.name.strip().decode('ascii', 'replace'),
        # this is a guess; Epson LX-80s NLQ has 18 dots per line
        line_height=36 if large else 18,
        shift_up=0 if large else 18-32,
        **{"polyprint.font_id": header.font_id},
    )
