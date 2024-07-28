"""
monobit.storage.formats.raw.raw - raw binary font files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import zip_longest
from pathlib import PurePath

from monobit.base.binary import ceildiv, bytes_to_bits
from monobit.storage import loaders, savers
from monobit.storage import FileFormatError, Regex, Glob
from monobit.core import Font, Glyph, Raster
from monobit.base import Coord, NOT_SET
from monobit.storage.utils.limitations import ensure_charcell

# patterns

# CHET .814 .88 .914 - http://fileformats.archiveteam.org/wiki/CHET_font

# .udg: 8x8 raw https://www.seasip.info/Unix/PSF/Amstrad/UDG/index.html

# https://www.seasip.info/Unix/PSF/Amstrad/Genecar/index.html
# GENECAR included three fonts in a format it calls .CAR. This is basically a
# raw dump of the font, but using a 16×16 character cell rather than the usual 16×8.

# height in suffix, one or two digits after f or 8 or 9
_FXX = Regex(r'.+\.[f89]\d\d?')

# raw formats we can't easily recognise from suffix or magic

# PRINTIT .fnt -> 8x16x192, 3072 bytes https://www.seasip.info/Unix/PSF/Amstrad/Printit/index.html
# degas elite .fnt, 8x16x128, + flags, 2050 bytes https://temlib.org/AtariForumWiki/index.php/DEGAS_Elite_Font_file_format
# warp 9 .fnt, 8x16x256 + flags, 4098 bytes https://temlib.org/AtariForumWiki/index.php/Warp9_Font_file_format
# however not all have the extra word

# Harlekin III .fnt - "Raw font data line by line, 8x8 (2048 bytes) or 8x16 (4096 bytes) only."
# https://temlib.org/AtariForumWiki/index.php/Fonts
# i.e. this is a wide-strike format, load width -strike-count=-1


@loaders.register(
    name='raw',
    patterns=('*.raw', '*.car', '*.udg', '*.ch8', _FXX),
    template='{name}.f{cell_size.y:02}',
)
def load_binary(
        instream, *,
        cell:Coord=NOT_SET, count:int=-1, offset:int=0, padding:int=0,
        align:str='left', byte_order:str='row-major',
        strike_count:int=1, strike_bytes:int=-1,
        first_codepoint:int=0, ink:int=1, msb:str='left', byte_swap:int=0,
    ):
    """
    Load character-cell font from binary bitmap.

    cell: size X,Y of character cell (default: 8x8 or determine from filename)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyph rows (default: 0)
    count: number of glyphs to extract (<= 0 means all; default: all)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    align: alignment of strike row ('left' for most-, 'right' for least-significant; 'bit' for bit-aligned; default: 'left')
    byte_order: 'row-major' (default) or 'column-major' byte order (affect cell sizes wider than 8 pixels)
    first_codepoint: first code point in bitmap (default: 0)
    ink: bit-value to interpret as ink (0 or 1; default: 1)
    msb: position of most-significant bit ('left' or 'right', default: 'left')
    byte_swap: reverse byte order in units of n bytes (default: no swap)
    """
    # determine cell size from filename, if not given
    encoding = None
    if cell is NOT_SET:
        if Glob('*.car').fits(instream):
            width, height = 16, 16
            encoding = 'amstread-cpm-plus'
        if Glob('*.udg').fits(instream):
            width, height = 8, 8
            encoding = 'amstread-cpm-plus'
        elif _FXX.fits(instream):
            # raw 8xN or 9xN (encoded as 8xN) format with height in suffix
            width = 8
            suffix = PurePath(instream.name).suffix
            try:
                height = int(suffix[2:])
            except ValueError:
                height = 8
        else:
            # e.g. *.ch8
            width, height = 8, 8
    else:
        width, height = cell
    # get through the offset
    instream.read(offset)
    font = load_bitmap(
        instream, width, height, count, padding, align,
        strike_count, strike_bytes, first_codepoint,
        byte_order=byte_order, ink=ink, msb=msb, byte_swap=byte_swap,
    )
    if encoding:
        font = font.label(char_from=encoding)
    return font

@savers.register(linked=load_binary)
def save_binary(
        fonts, outstream, *,
        strike_count:int=1, align:str='left', padding:int=0,
        ink:int=1, msb:str='left', byte_swap:int=0,
    ):
    """
    Save character-cell fonts to binary bitmap. Multiple fonts will be saved consecutively.

    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    align: alignment of strike row ('left' for most-, 'right' for least-significant; 'bit' for bit-aligned; default: 'left')
    padding: number of bytes between encoded glyph rows (default: 0)
    ink: bit-value to interpret as ink (0 or 1; default: 1)
    msb: position of most-significant bit ('left' or 'right', default: 'left')
    byte_swap: reverse byte order in units of n bytes (default: no swap)
    """
    for font in fonts:
        save_bitmap(
            outstream, font,
            strike_count=strike_count, align=align, padding=padding,
            ink=ink, msb=msb,
        )


###############################################################################
# bitmap reader

def load_bitmap(
        instream, width, height, count=-1, padding=0, align='left',
        strike_count=1, strike_bytes=-1, first_codepoint=0, *,
        byte_order='row-major', ink=1, msb='left',
        byte_swap:int=0,
    ):
    """Load fixed-width font from bitmap."""
    if align == 'bit':
        data, count = _extract_data_and_geometry_bit_aligned(
            instream, width, height, count, padding, strike_count, strike_bytes,
        )
        cells = _extract_cells_bit_aligned(data, width, height, count, byte_swap)
    else:
        data, count, cells_per_row, bytes_per_row, nrows = _extract_data_and_geometry(
            instream, width, height, count, padding, strike_count, strike_bytes,
        )
        cells = _extract_cells(
            data, width, height, align, cells_per_row, bytes_per_row, nrows,
            byte_order=byte_order, byte_swap=byte_swap,
        )
    # reduce to given count, if exceeded
    cells = cells[:count]
    # assign codepoints
    glyphs = (
        Glyph(_cell, codepoint=_index)
        for _index, _cell in enumerate(cells, first_codepoint)
    )
    if ink == 0:
        glyphs = (_g.invert() for _g in glyphs)
    if msb.lower().startswith('r'):
        glyphs = (_g.mirror() for _g in glyphs)
    return Font(glyphs)


def _extract_data_and_geometry(
        instream, width, height, count=-1, padding=0,
        strike_count=1, strike_bytes=-1,
    ):
    """Determine geometry from defaults and data size."""
    data = None
    # determine byte-width of the bitmap strike rows
    if strike_bytes <= 0:
        if strike_count <= 0:
            data = instream.read()
            strike_bytes = len(data) // height
        else:
            strike_bytes = ceildiv(strike_count*width, 8)
    # we should not force recalculation of strike count
    # as that stops us from having a too-wide strike.
    # E.g. 4-pixel wide glyph, one per 1-byte row
    # else:
    #     strike_count = -1
    # determine number of cells per strike row
    if strike_count <= 0:
        strike_count = (strike_bytes * 8) // width
    if not strike_count:
        raise FileFormatError('Bad file geometry')
    # determine bytes per strike row
    row_bytes = strike_bytes*height + padding
    # determine number of strike rows
    if count is None or count <= 0:
        if not data:
            data = instream.read()
        # get number of chars in extract
        nrows = ceildiv(len(data), row_bytes)
        count = nrows * strike_count
    else:
        nrows = ceildiv(count, strike_count)
        if not data:
            data = instream.read(nrows * row_bytes)
    # we may exceed the length of the rom because we use ceildiv, pad with nulls
    data = data.ljust(nrows * row_bytes, b'\0')
    if nrows == 0 or row_bytes == 0:
        return b'', 0, 0, 0, 0
    return data, count, strike_count, row_bytes, nrows


def _extract_cells(
        data, width, height, align, cells_per_row, bytes_per_row, nrows, *,
        byte_order='row-major', byte_swap=0,
    ):
    """Extract glyphs from bitmap strike with given geometry."""
    # extract one strike row at a time
    # note that the strikes may not be immediately contiguous if there's padding
    glyphrows = (
        Raster.from_bytes(
            data[_i*bytes_per_row : (_i+1)*bytes_per_row],
            width*cells_per_row, height,
            align=align, byte_order=byte_order,
            byte_swap=byte_swap,
        )
        for _i in range(nrows)
    )
    # clip out glyphs
    cells = tuple(
        _glyphrow.crop(
            left=_i*width,
            right=_glyphrow.width - (_i+1)*width
        )
        for _glyphrow in glyphrows
        for _i in range(cells_per_row)
    )
    return cells


def _extract_data_and_geometry_bit_aligned(
        instream, width, height, count, padding, strike_count, strike_bytes,
    ):
    if padding != 0:
        raise ValueError(
            'Nonzero padding not supported for bit-aligned binaries.'
        )
    if strike_count != 1:
        raise ValueError(
            'Strike count other than 1 not supported for bit-aligned binaries.'
        )
    if strike_bytes != -1:
        raise ValueError(
            'Strike bytes argument not supported for bit-aligned binaries.'
        )
    if count <= 0:
        data = instream.read()
        count = (8 * len(data)) // (width * height)
    else:
        data = instream.read(ceildiv(count*width*height, 8))
    return data, count


def _extract_cells_bit_aligned(data, width, height, count, byte_swap):
    """Extract glyphs from bit-aligned bitmap strike."""
    bitmap = Raster.from_bytes(data, width, align='bit', byte_swap=byte_swap)
    # clip out glyphs
    cells = tuple(
        bitmap.crop(
            top=_r*height,
            bottom=bitmap.height - (_r+1)*height,
        )
        for _r in range(count)
    )
    return cells


###############################################################################
# bitmap writer

def save_bitmap(
        outstream, font, *,
        strike_count:int=1, align:str='left', padding:int=0,
        ink:int=1, msb:str='left', byte_swap:int=0,
    ):
    """
    Save character-cell font to binary bitmap.
    """
    font = ensure_charcell(font)
    # get pixel rasters
    rasters = (_g.pixels for _g in font.glyphs)
    if align == 'bit':
        if padding != 0:
            raise ValueError(
                'Nonzero padding not supported for bit-aligned binaries.'
            )
        if strike_count != 1:
            raise ValueError(
                'Strike count other than 1 not supported for bit-aligned binaries.'
            )
        # stack all vertically as if it were one row
        # in case glyphs do not end on a byte boundary
        bitmap = Raster.stack(*rasters)
        glyphrows = (bitmap,)
    else:
        # contruct rows (itertools.grouper recipe)
        args = [iter(rasters)] * strike_count
        grouped = zip_longest(*args, fillvalue=Glyph())
        glyphrows = (
            Raster.concatenate(*_row)
            for _row in grouped
        )
    for glyphrow in glyphrows:
        if ink == 0:
            glyphrow = glyphrow.invert()
        if msb.lower().startswith('r'):
            glyphrow = glyphrow.mirror()
        outstream.write(glyphrow.as_bytes(align=align, byte_swap=byte_swap))
        outstream.write(b'\0' * padding)
