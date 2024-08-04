"""
monobit.storage.formats.riscos - Acorn RiscOS fonts

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.binary import ceildiv
from monobit.base.struct import little_endian as le
from monobit.storage import loaders, FileFormatError, Magic
from monobit.core import Font, Glyph, Raster

# https://web.archive.org/web/20210610120924/https://hwiegman.home.xs4all.nl/fileformats/acorn_font/font.htm
# > (The original information can be found on page 1801 of Volume IV of
# > the RISC OS 3.1 PROGRAMMER'S REFERENCE MANUAL)

# extended format versions exist, not yet supported


_INDEX_ENTRY = le.Struct(
    # > 1       point size (not multiplied by 16)
    point_size='uint8',
    # > 1       bits per pixel (4)
    bpp='uint8',
    # > 1       pixels per inch (x-direction)
    dpi_x='uint8',
    # > 1       pixels per inch (y-direction)
    dpi_y='uint8',
    # > 4       reserved - currently 0
    reserved='uint32',
    # > 4       offset of font data in file
    offset='uint32',
    # > 4       size of font data
    size='uint32',
)

_FONT_DATA = le.Struct(
    # > 4       x-size in 1/16ths point * x pixels per inch
    x_size='uint32',
    # > 4       y-size in 1/16ths point * y pixels per inch
    y_size='uint32',
    # > 4       pixels per inch in the x-direction
    dpi_x='uint32',
    # > 4       pixels per inch in the y-direction
    dpi_y='uint32',
    # > 1       x0     |  maximum bounding box for any character
    max_x0='int8',
    # > 1       y0     |  bottom-left is inclusive
    max_y0='int8',
    # > 1       x1     |  top-rightis exclusive
    max_x1='int8',
    # > 1       y1     |  all coordinates are in pixels
    max_y1='int8',
    # > 512     2 byte offsets from table start of character data. A zero value
    # >         means the character is not defined. These are low/high byte
    # >         pairs (ie little-endian)
    offsets=le.uint16 * 256,
)

_CHAR_HEADER = le.Struct(
    # > 1       x0     |  bounding box
    x0='int8',
    # > 1       y0     |
    y0='int8',
    # > 1       x1 - x0 = X
    width='int8',
    # > 1       y1 - y0 = Y
    height='int8',
    # > X*Y/2   4-bits per pixel (bpp), consectutive rows bottom to top.
    # >         Not aligned until at the end.
    # > 0 - 3.5 Alignment
)

@loaders.register(
    name='x90y45',
    # maybe, assumes 4bpp, xdpi 90, ydpi 45 in first entry
    # followed by four nulls in newer but not older files
    magic=(Magic.offset(1) + b'\x04\x5a\x2d',),
    patterns=('x90y45',),
)
def load_x90y45(instream):
    """Load font from acorn RiscOS x90y45 font files."""
    index = []
    while True:
        entry = _INDEX_ENTRY.read_from(instream)
        # list terminated by a single null
        # so we've read too far, but will seek to the offset anyway
        if not entry.point_size:
            break
        index.append(entry)
        logging.debug('index entry: %s', entry)
    font_data = []
    char_tables = []
    for entry in index:
        instream.seek(entry.offset)
        font_entry = _FONT_DATA.read_from(instream)
        font_data.append(font_entry)
        logging.debug('font data: %s', font_entry)
        # actually offsets are from start of offset table
        anchor = instream.tell() - 512
        char_table = []
        for cp, offset in enumerate(font_entry.offsets):
            if offset == 0:
                continue
            instream.seek(anchor + offset)
            char_entry = _CHAR_HEADER.read_from(instream)
            logging.debug('char entry: %s', char_entry)
            char_data = instream.read(ceildiv(char_entry.width * char_entry.height, 2))
            char_table.append((cp, char_entry, char_data))
        char_tables.append(char_table)
    # convert
    fonts = []
    for index_entry, font_entry, char_table in zip(index, font_data, char_tables):
        glyphs = tuple(
            Glyph(
                Raster.from_bytes(
                    char_data,
                    width=char_entry.width,
                    height=char_entry.height,
                    # bpp must be 4
                    bits_per_pixel=index_entry.bpp,
                    align='bit',
                    bit_order='little',
                    bytes=len(char_data),
                ).flip(),
                left_bearing=char_entry.x0,
                shift_up=char_entry.y0,
                codepoint=cp,
            )
            for cp, char_entry, char_data in char_table
        )
        fonts.append(Font(
            glyphs,
            point_size=index_entry.point_size,
            dpi=(font_entry.dpi_x, font_entry.dpi_y),
            encoding='latin-1',
        ).label())
    return fonts
