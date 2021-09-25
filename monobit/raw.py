"""
monobit.raw - raw binary font files

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .binary import ceildiv, bytes_to_bits
from .formats import Loaders, Savers
from .font import Font
from .glyph import Glyph
from .streams import FileFormatError
from .base import boolean, pair


@Loaders.register('dos', 'bin', 'rom', 'raw', name='raw binary')
def load(instream, where=None, cell:pair=(8, 8), n_chars:int=None, offset:int=0, strike:boolean=False):
    """Load font from raw binary."""
    # get through the offset
    # we don't assume instream is seekable - it may be sys.stdin
    instream.read(offset)
    if strike:
        cells = load_strike(instream, cell, n_chars)
    else:
        cells = load_aligned(instream, cell, n_chars)
    return Font(cells)


@Savers.register(loader=load)
def save(fonts, outstream, where=None):
    """Save font to raw byte-aligned binary (DOS font)."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to BDF file.')
    save_aligned(outstream, fonts[0])


def save_aligned(outstream, font, encoding=None):
    """Save fixed-width font to byte-aligned bitmap."""
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    for glyph in font.glyphs:
        outstream.write(glyph.as_bytes())


def load_strike(instream, cell, n_chars):
    """Load fixed-width font from bitmap strike."""
    width, height = cell
    # n_chars must be given for strikes
    # assume byte-aligned at end of strike only
    strike_bytes = ceildiv(n_chars * width, 8)
    rombytes = instream.read(strike_bytes * height)
    # flatten strikes
    rows = [
        rombytes[_strike*strike_bytes : (_strike+1)*strike_bytes]
        for _strike in range(height)
    ]
    # convert to bits
    drawn = [bytes_to_bits(_row) for _row in rows]
    # clip out glyphs
    cells = [
        [_strike[_n*width:(_n+1)*width] for _strike in drawn]
        for _n in range(n_chars)
    ]
    return cells

def load_aligned(instream, cell, n_chars):
    """Load fixed-width font from byte-aligned bitmap."""
    width, height = cell
    width_bytes = ceildiv(width, 8)
    if n_chars is None:
        rombytes = instream.read()
        # get number of chars in extract
        n_chars = ceildiv(len(rombytes), width_bytes * height)
    else:
        rombytes = instream.read(n_chars * width_bytes * height)
    return parse_aligned(rombytes, width, height, n_chars)

def parse_aligned(rombytes, width, height, n_chars, offset=0):
    """Load fixed-width font from byte-aligned bitmap."""
    bytesize = ceildiv(width, 8) * height
    # get chunks
    glyphbytes = [
        rombytes[offset+_ord*bytesize : offset+(_ord+1)*bytesize]
        for _ord in range(n_chars)
    ]
    # concatenate rows
    cells = [
        Glyph.from_bytes(_bytes, width)
        for _bytes in glyphbytes
    ]
    return cells
