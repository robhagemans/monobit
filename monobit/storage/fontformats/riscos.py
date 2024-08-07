"""
monobit.storage.formats.riscos - Acorn RiscOS fonts

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.binary import ceildiv
from monobit.base.properties import Props
from monobit.base.struct import little_endian as le, bitfield, flag
from monobit.storage import loaders, Magic
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Font, Glyph, Raster

# https://web.archive.org/web/20210610120924/https://hwiegman.home.xs4all.nl/fileformats/acorn_font/font.htm
# > (The original information can be found on page 1801 of Volume IV of
# > the RISC OS 3.1 PROGRAMMER'S REFERENCE MANUAL)

# extended format versions exist, not yet supported


# x90y45 old-style bitmap file

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
    x0='int8',
    # > 1       y0     |  bottom-left is inclusive
    y0='int8',
    # > 1       x1     |  top-rightis exclusive
    x1='int8',
    # > 1       y1     |  all coordinates are in pixels
    y1='int8',
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
    # load metrics, if available
    location = instream.where
    try:
        metrics_file = location.open('IntMetrics', mode='r')
    except FileNotFoundError:
        header = None
        metrics = None
    else:
        with metrics_file:
            header, metrics = _read_int_metrics(metrics_file)
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
            if metrics:
                metrics_index = header.mapping[cp]
                char_metrics = metrics[metrics_index]
            else:
                char_metrics = None
            instream.seek(anchor + offset)
            char_entry = _CHAR_HEADER.read_from(instream)
            logging.debug('char entry: %s', char_entry)
            char_data = instream.read(ceildiv(char_entry.width * char_entry.height, 2))
            char_table.append((cp, char_entry, char_data, char_metrics))
        char_tables.append(char_table)
    # convert
    fonts = []
    for index_entry, font_entry, char_table in zip(index, font_data, char_tables):
        # entries are in 1/1000 of an em (1em == point-size)
        # point = 1/72 in, 90dpi -> 90 pixels per inch -> 90/72 pixels per point
        scale_x = index_entry.point_size * font_entry.dpi_x / 72 / 1000
        scale_y = index_entry.point_size * font_entry.dpi_y / 72 / 1000
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
                # x0, y0 in the x90y45 file seem to make more sense than in IntMetrics
                # or I am not understanding the units correctly
                shift_up=char_entry.y0,
                left_bearing=char_entry.x0,
                # y1 seems to be more consistent than y0
                # shift_up=round(char_metrics.y1*scale_y) - char_entry.height + 1,
                # left_bearing=round(char_metrics.x0*scale_x),
                # right bearing such that advance width is consistent
                right_bearing=(
                    round(char_metrics.x_offset*scale_x)
                    - char_entry.x0
                    - char_entry.width
                ),
                scalable_width=char_metrics.x_offset * scale_x,
                codepoint=cp,
            )
            for cp, char_entry, char_data, char_metrics in char_table
        )
        name = header.name.rstrip(b'\r').decode('latin-1')
        family, _, subfamily = name.partition('.')
        fonts.append(Font(
            glyphs,
            family=family,
            subfamily=subfamily or None,
            point_size=index_entry.point_size,
            dpi=(font_entry.dpi_x, font_entry.dpi_y),
            encoding='latin-1',
        ).label())
    return fonts


# IntMetrics file

_INT_METRICS_HEADER = le.Struct(
    # > 40      Name of font, padded with Return (&0D) characters
    name='40s',
    # > 4       16
    # > 4       16
    four_0='uint32',
    four_1='uint32',
    # > 1       n=number of defined characters
    n='uint8',
    # > 3       reserved - currently 0
    reserved=le.uint8 * 3,
    # > 256     character mapping (ie indices into following arrays). For
    # >         example, if the 40th byte in this block is 4, then the fourth
    # >         entry in each of the following arrays refers to that character.
    # >         A zero entry means that character is not defined in this font.
    mapping=le.uint8 * 256,
    # 2n      x0     |
    # 2n      y0     |  bounding cox of character (in 1/1000th em)
    # 2n      x1     |  coordinates are relative to the 'origin point'
    # 2n      y1     |
    # 2n      x-offset after printing this character
    # 2n      y-offset after printing this character
    #
    # The bounding boxes and offsets are given as 16-bit signed numbers, with the low byte first.
)


def _read_int_metrics(instream):
    """Read IntMetrics file."""
    header = _INT_METRICS_HEADER.read_from(instream)
    x0 = (le.int16 * header.n).read_from(instream)
    y0 = (le.int16 * header.n).read_from(instream)
    x1 = (le.int16 * header.n).read_from(instream)
    y1 = (le.int16 * header.n).read_from(instream)
    x_offset = (le.int16 * header.n).read_from(instream)
    y_offset = (le.int16 * header.n).read_from(instream)
    logging.debug('header: %s', header)
    metrics = tuple(
        Props(x0=_x0, y0=_y0, x1=_x1, y1=_y1, x_offset=_xoffs, y_offset=_yoffs)
        for _x0, _y0, _x1, _y1, _xoffs, _yoffs
        in zip(x0, y0, x1, y1, x_offset, y_offset)
    )
    return header, metrics



# new font file format

_NEW_HEADER = le.Struct(
    # > 4 "FONT" -identification word
    identification_word='4s',
    # > 1 Bits per pixel:
    # >   0 = outlines
    # >   1 = 1 bpp
    # >   4 = 4 bpp
    bits_per_pixel='uint8',
    # > 1 Version number of file format
    # >   4: no "don't draw skeleton lines unless smaller than this" byte present
    # >   5: byte at [table+512] =max pixel size for skeleton lines
    # >      (0 => always do it)
    # >   6: byte at [chunk+indexsize] = dependency mask (see below)
    version='uint8',
    # > 2 if bpp = 0: design size of font
    # >   if bpp > 0: flags:
    # >     bit 0 set - horizontal subpixel placement
    # >     bit 1 set - vertical subpixel placement
    flags='uint16',
    # > 2 xO - font bounding box (16- bit signed)
    # > 2 yO - units are pixels or design units
    # > 2 x1-xO : xO, yO inclusive, x1, y1 exclusive
    # > 2 y1-y0
    x0='int16',
    y0='int16',
    x1='int16',
    y1='int16',
    # > 4 file offset of 0...31 chunk (word-aligned)
    # > 4 file offset of 32...63 chunk
    # > ...
    # > 4 file offset of 224...255 chunk
    # > 4 file offset of end (ie. size of file)
    # > if offset(n+1) = offset(n), then chunk n is null.
    offsets=le.uint32*9,
)

_TABLE = le.Struct(
    # > 2 n = size of table/scaffold data
    n='uint16',
    # > Bitmaps: (n=10 normally - other values are reserved)
    # > 2 x-size (1/16th point)
    x_size='uint16',
    # 2 x-res (dpi)
    x_res='uint16',
    # 2 y-size (1/16th point)
    y_size='uint16',
    # 2 y-res (dpi)
    y_res='uint16',
)

_CHAR_FLAGS = le.Struct(
    # > 1   flags:
    # >     bit 0 set => coords are 12-bit, else 8-bit
    # >     bit 1 set => data is 1-bpp, else 4-bpp
    # >     bit 2 set => initial pixel is black, else white
    # >     bit 3 set => data is outline, else bitmap
    # >     bits 4-7 = 'f' value for char (0 ==> not encoded)
    coords_12bit=flag,
    data_1bpp=flag,
    initial_black=flag,
    outline=flag,
    f_value=bitfield('uint8', 4),
)
_CHAR_DATA_8BIT = le.Struct(
    # > 2/3 xO, yO sign-extended 8· or 12- bit coordinates
    x0='int8',
    y0='int8',
    # > 2/3 xs, ys width, height (bbox = xO,yO,xO+xs,yO+ys)
    xs='int8',
    ys='int8',
    # > n   data: (depends on type of file)
    #           1-bpp uncrunched: rows from bottom to top
    #           4-bpp uncrunchcd: rows from bottom to top
    #           1-bpp crunched: list of (packed) run-lengths
    #           outlines: list of move/line/curve segments
    # word-aligned at the end of the character data
)
_CHAR_DATA_12BIT = le.Struct(
    x0_y0=le.uint8 * 3,
    xs_ys=le.uint8 * 3,
)

_RISCOS_MAGIC = b'FONT'

@loaders.register(
    name='riscos',
    # maybe, assumes 4bpp, xdpi 90, ydpi 45 in first entry
    # followed by four nulls in newer but not older files
    magic=(_RISCOS_MAGIC,),
    patterns=('f*x*','b*x*'),
)
def load_riscos(instream):
    """Load font from acorn RiscOS new-style font files."""
    header = _NEW_HEADER.read_from(instream)
    logging.debug('header: %s', header)
    if header.identification_word != _RISCOS_MAGIC:
        raise FileFormatError(
            'Not a RiscOS new font format file: magic bytes '
            f'{header.identification_word} != {_RISCOS_MAGIC}'
        )
    if not header.bits_per_pixel:
        raise UnsuppportedError('RiscOS Outline fonts not supported')
    table = _TABLE.read_from(instream)
    logging.debug('table: %s', table)
    # NULL-separated description
    desc = instream.read(header.offsets[0] - instream.tell())
    logging.debug('%s', desc)
    for chunk_start, chunk_end in zip(header.offsets[:-1], header.offsets[1:]):
        logging.debug('%d %d', chunk_start, chunk_end)
        if chunk_end == chunk_start:
            continue
        instream.seek(chunk_start)
        # > 4 x 32 offset within chunk to character
        # >        0 => character is not defined
        # >        x 4 for vertical placement
        # >        x 4 for horizontal placement
        # Character index is more tightly bound than vertical
        # placement which is more tightly bound than
        # horizontal placement.
        offsets = (le.uint32 * 32).read_from(instream)
        offsets = (*offsets, chunk_end - chunk_start)
        logging.debug('%s', offsets)
        # ignoring tables for horizontal/vertical subpixel placement
        for offs, next in zip(offsets[:-1], offsets[1:]):
            instream.seek(chunk_start+offs)
            char_flags = _CHAR_FLAGS.read_from(instream)
            logging.debug('%s', char_flags)
            if char_flags.coords_12bit:
                char_data = _CHAR_DATA_12BIT.read_from(instream)
            else:
                char_data = _CHAR_DATA_8BIT.read_from(instream)
            logging.debug('%s', char_data)
            char_bytes = instream.read(chunk_start+next-instream.tell())
            logging.debug('%s', char_bytes)
