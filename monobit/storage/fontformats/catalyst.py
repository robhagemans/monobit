"""
monobit.storage.fontformats.catalyst - Quark Catalyst font file

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import count

from monobit.storage import loaders, savers
from monobit.core import Font, Glyph, Raster
from monobit.base import struct
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv

# this was reverse engineered based on a single file
# so it may not work on other files, should they exist


@loaders.register(name='catalyst')
def load_catalyst(instream):
    """Load Quark Catalyst fonts."""
    n_resources = int(le.uint8.read_from(instream))
    fonts = tuple(_load_catalyst_resource(instream) for _ in range(n_resources))
    return fonts

def _load_catalyst_resource(instream):
    """Load single Quark Catalyst resource."""
    size = int(le.uint16.read_from(instream))
    anchor = instream.tell()
    count = 128
    offsets = (le.uint16 * count).read_from(instream)
    logging.debug('offsets table: %s', offsets)
    metrics = (le.uint8 * count).read_from(instream)
    logging.debug('metrics table: %s', metrics)
    widths = tuple(_m & 0x7f for _m in metrics)
    # shifted glyphs have the high width bit set
    shift_downs = tuple(_m // 0x80 for _m in metrics)
    height = int(le.uint8.read_from(instream))
    logging.debug('glyph height: %s', height)
    leading = int(le.uint8.read_from(instream))
    logging.debug('leading: %s', leading)
    sidebearing = int(le.uint8.read_from(instream))
    logging.debug('sidebearing: %s', sidebearing)
    # ignoring the offsets table, assuming the glyphs are stored contiguously
    glyphs = tuple(
        Glyph(
            Raster.from_bytes(
                instream.read(ceildiv(_w, 8) * height),
                width=_w, bit_order='little',
            ).stretch((7, 1)).shrink((8, 1)),
            shift_up=-_sh, right_bearing=sidebearing,
            codepoint=_cp,
        )
        for _cp, (_w, _sh) in enumerate(zip(widths, shift_downs))
    )
    remainder = size - (instream.tell() - anchor)
    logging.debug(remainder)
    return Font(glyphs, source_format='catalyst', line_height=height+leading)
