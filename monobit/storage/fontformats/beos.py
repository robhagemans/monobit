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
    # > total size
    size='uint32',
    # > font-family-name size (not including the trailing null)
    ffnSize='uint16',
    # > font-style-name size (not including the trailing null)
    fsnSize='uint16',
    padding_0='10s',
    # > The number of characters that can be stored in the location-table -1
    ltMax='uint16',
    # > font-point (Bitmap fonts are enabled at this point number)
    point='uint16',
    unknown_768='uint16',
    unknown='8s',
)

_LOCATION_ENTRY = be.Struct(
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

_BEOS_MAGIC = b'|Be;'


@loaders.register(
    name='beos',
    magic=(_BEOS_MAGIC,)
)
def load_beos(instream):
    """Load font from Be Bitmap Font file."""
    header = _HEADER.read_from(instream)
    familyName = instream.read(header.ffnSize+1)[:-1].decode('latin-1')
    styleName = instream.read(header.fsnSize+1)[:-1].decode('latin-1')
    logging.debug('header: %s', header)
    logging.debug('family: %s', familyName)
    logging.debug('style: %s', styleName)
    # hash table of pointers to glyphs, hashed by unicode codepoint
    location_table = (_LOCATION_ENTRY * (header.ltMax+1)).read_from(instream)
    location_dict = {_e.pointer: _e.code for _e in location_table}
    glyphs = []
    while instream.tell() < header.size:
        pointer = instream.tell()
        code = location_dict.get(pointer, None)
        glyph_data = _GLYPH_DATA.read_from(instream)
        # bitmap dimensions
        width = glyph_data.right - glyph_data.left + 1
        height = glyph_data.bottom - glyph_data.top + 1
        # 4 bits per pixel
        bytewidth = ceildiv(width * 4, 8)
        glyph_bytes = instream.read(height*bytewidth)
        glyphs.append(
            Glyph.from_bytes(
                glyph_bytes, width=width, height=height, bits_per_pixel=4,
                codepoint=code,
                right_bearing=glyph_data.width-width,
                left_bearing=glyph_data.left,
                shift_up=-1-glyph_data.bottom,
            )
        )
    return Font(
        glyphs,
        encoding='unicode',
        family=familyName,
        name=(familyName + ' ' + styleName),
        point_size=header.point,
    ).label()
