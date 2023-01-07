"""
monobit.formats.printshop - Broderrbund's The Print Shop font files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from .. import struct
from ..struct import little_endian as le
from ..binary import ceildiv
from .raw import load_binary

# offset 0
_HEADER = le.Struct(
    bbx_width='uint8',
    bbx_height='uint8',
    unused='uint16',
)
# offset 4
_WIDTHS = le.uint8.array(95)
# offset 99
_HEIGHTS = le.uint8.array(95)
# offset 194
_OFFSETS = le.uint16.array(95)
# offset 384

# offs 574, 7 bytes unknown

# offs 581, name, max 9 chars inc null terminator
# offs 590 name bitmap byte width?
# offs 591 name bitmap height/
# offs 592 glyph height?
# offs 593 short name, 4 bytes?
# offs 597, 4 bytes unknown
# offs 601, name bitmap
# followed by glyph bitmaps

_BITMAP_HEADER = le.Struct(
    unknown0=le.uint8 * 7,
    name='9s',
    logo_bytewidth='uint8',
    logo_height='uint8',
    height='uint8',
    shortname='4s',
    unknown1=le.uint8 * 4,
)

@loaders.register(
    name='printshop'
)
def load_printshop(instream, where=None):
    """
    Load a Broderbund The Print Shop font.
    """
    header = _HEADER.read_from(instream)
    logging.debug(header)
    widths = _WIDTHS.read_from(instream)
    heights = _HEIGHTS.read_from(instream)
    offsets = _OFFSETS.read_from(instream)
    instream.seek(574)
    bmp_header = _BITMAP_HEADER.read_from(instream)
    logging.debug(bmp_header)
    logobytes = instream.read(bmp_header.logo_bytewidth * bmp_header.logo_height)
    width = bmp_header.logo_bytewidth * 8
    logo = Glyph.from_bytes(
            logobytes, width=width, height=bmp_header.logo_height,
            tag='sample',
        )
    glyphs = []
    codepoint = 0x20
    for start, width, height in zip(offsets, widths, heights):
        glyphs.append(Glyph.from_bytes(
            instream.read(ceildiv(width, 8) * height),
            width=width, codepoint=codepoint, shift_up=bmp_header.height-height
        ))
        codepoint += 1
    return Font(
        glyphs, source_format='The Print Shop',
        family=bmp_header.name.decode('latin-1'),
        comment=logo.as_text()
    )
