"""
monobit.formats.geos - C64 GEOS font files

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
from .raw import load_binary

# https://www.lyonlabs.org/commodore/onrequest/geos/geos-fonts.html
_HEADER = le.Struct(
    baseline='uint8',
    stride='uint16',
    height='uint8',
    index_offset='uint16',
    bitstream_offset='uint16',
)

# characters 0x20 - 0x7f
# do we get plus one for the offset to the end?
_OFFSETS = le.uint16.array(96)


@loaders.register('vlir', name='geos')
def load_geos(instream, where=None):
    """Load a bare GEOS font VLIR."""
    header = _HEADER.read_from(instream)
    logging.debug(header)
    instream.seek(header.index_offset)
    offsets = _OFFSETS.read_from(instream)
    instream.seek(header.bitstream_offset)
    strike = Raster.from_bytes(
        instream.read(header.height * header.stride),
        header.stride * 8, header.height,
    )
    # clip out glyphs
    glyphs = tuple(
        Glyph(
            strike.crop(left=_offset, right=header.stride*8 - _next),
            codepoint=_cp,
            shift_up=-(header.height-header.baseline-1)
        )
        for _offset, _next, _cp in zip(offsets, offsets[1:], count(0x20))
    )
    return Font(glyphs)
