"""
monobit.formats.printshop - Broderbund's The Print Shop font files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import count

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from .. import struct
from ..struct import little_endian as le
from ..binary import ceildiv

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
# offset 384, another 95 words, zeroed
# offset 574, bitmap header
_BITMAP_HEADER = le.Struct(
    unknown0='uint8',
    # maybe, but only sometimes fits
    maybe_baseline='uint8',
    unknown1='uint16',
    unknown2='uint16',
    # zero
    unused='uint8',
    name='9s',
    logo_bytewidth='uint8',
    logo_height='uint8',
    height='uint8',
    shortname='4s',
    unknown4='uint16',
    # unknown5==unknown2
    unknown5='uint16',
)
# logo bitmap starts at offset 601, followed by glyph


# not clear how baseline and interglyph spacing are determined
# the Print Shop uses negative bearings/kerning, but there clearly is
# no bearings or kerning table present in the font file
# so the hypothesis is that TPS does this algorithmically,
# moving the next glyph as far left as possible so that a certain amount
# of space remains between inked pixels

@loaders.register(
    name='printshop',
    patterns=('*.pnf', '*.psf'),
)
def load_printshop(instream):
    """
    Load a Broderbund The Print Shop font.
    """
    header = _HEADER.read_from(instream)
    logging.debug(header)
    widths = _WIDTHS.read_from(instream)
    heights = _HEIGHTS.read_from(instream)
    offsets = _OFFSETS.read_from(instream)
    # another block in the same format, usually (always?) zeroed out
    unknown = _OFFSETS.read_from(instream)
    logging.debug(unknown)
    bmp_header = _BITMAP_HEADER.read_from(instream)
    logging.debug(bmp_header)
    logobytes = instream.read(bmp_header.logo_bytewidth * bmp_header.logo_height)
    width = bmp_header.logo_bytewidth * 8
    logo = Glyph.from_bytes(
        logobytes, width=width, height=bmp_header.logo_height,
        tag='sample',
    )
    # ignoring the offsets table, assuming the glyphs are stored contiguously
    glyphs = tuple(
        Glyph.from_bytes(
            instream.read(ceildiv(_w, 8) * _h),
            width=_w, codepoint=_cp,
            shift_up=bmp_header.height-_h
        )
        for _w, _h, _cp in zip(widths, heights, count(0x20))
    )
    return Font(
        glyphs, source_format='The Print Shop',
        family=bmp_header.name.decode('latin-1'),
        # preserve the logo bitmap as a comment
        # storing it as a glyph would mess up the bounding box
        comment=logo.as_text()
    )
