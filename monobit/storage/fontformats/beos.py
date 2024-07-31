"""
monobit.storage.formats.beos - BeOS Bitmap Font

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from monobit.base.binary import ceildiv
from monobit.base.struct import big_endian as be
from monobit.base import Props
from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph

from monobit.storage.utils.limitations import ensure_single


# http://www.eonet.ne.jp/~hirotsu/bin/bmf_format.txt

_HEADER = be.Struct(
    mark='4s',
    size='uint32',
    ffnSize='uint16',
    fsnSize='uint16',
    padding_0='10s',
    ltMax='uint16',
    point='uint16',
    unknown_768='uint16',
    padding_1='8s',
)

_LOCATION_TABLE = be.Struct(
    pointer='uint32',
    code='uint16',
    reserved='uint16',
)

_GLYPH_DATA = be.Struct(
    unknown_0x4996b438 = 'uint32',
    unknown_0x4996b440 = 'uint32',
    left='int16',
    top='int16',
    right='int16',
    bottom='int16',
    width='float',
    maybe_height='float',
)

@loaders.register(
    name='beos',
    magic=(b'|Be;',)
)
def load_beos(instream):
    """Load font from Be Bitmap Font file."""
    header = _HEADER.read_from(instream)
    familyName = instream.read(header.ffnSize+1)
    styleName = instream.read(header.fsnSize+1)
    logging.debug('header: %s', header)
    logging.debug('family: %s', familyName)
    logging.debug('style: %s', styleName)
    # hash table of pointers to glyphs, hashed by unicode codepoint
    location_table = (_LOCATION_TABLE * (header.ltMax+1)).read_from(instream)
    location_dict = {_e.pointer: _e.code for _e in location_table}
    # for entry in location_table:
    glyphs = []
    while instream.tell() < header.size:
        pointer = instream.tell()
        code = location_dict.get(pointer, None)
        glyph_data = _GLYPH_DATA.read_from(instream)
        # 4 bits per pixel
        width = glyph_data.right - glyph_data.left + 1
        bytewidth = ceildiv(width * 4, 8)
        height = glyph_data.bottom - glyph_data.top + 1
        glyph_bytes = instream.read(height*bytewidth)
        glyphs.append(
            Glyph.from_bytes(
                glyph_bytes, width=width, height=height, bits_per_pixel=4,
                codepoint=code,
            )
        )
    return Font(glyphs, encoding='unicode').label()
