"""
monobit.formats.raw - raw binary font files

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..binary import ceildiv, bytes_to_bits
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError
from ..scripting import pair, any_int


@loaders.register('dos', 'bin', 'rom', 'raw', name='raw binary')
def load_binary(
        instream, where=None, *,
        cell:pair=(8, 8), numchars:int=None, offset:int=0, padding:int=0, strike:bool=False,
        first_codepoint:int=0
    ):
    """
    Load character-cell font from byte-aligned binary or bitmap strike.

    cell: size X,Y of character cell
    offset: number of bytes in file before bitmap starts
    padding: number of bytes between encoded glyphs (not used for strike fonts)
    numchars: number of glyphs to extract
    strike: bitmap is in strike format rather than byte-aligned
    first_codepoint: first code point in bitmap
    """
    width, height = cell
    # get through the offset
    # we don't assume instream is seekable - it may be sys.stdin
    instream.read(offset)
    if strike:
        glyphs = load_strike(instream, width, height, numchars)
    else:
        glyphs = load_aligned(instream, width, height, numchars, padding)
    glyphs = (
        _glyph.modify(codepoint=_index)
        for _index, _glyph in enumerate(glyphs, first_codepoint)
    )
    return Font(glyphs)


@savers.register(linked=load_binary)
def save_binary(fonts, outstream, where=None):
    """
    Save character-cell font to byte-aligned binary.
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to raw binary file.')
    save_aligned(outstream, fonts[0])


def save_aligned(outstream, font):
    """Save fixed-width font to byte-aligned bitmap."""
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    for glyph in font.glyphs:
        outstream.write(glyph.as_bytes())


def load_strike(instream, width, height, numchars):
    """Load fixed-width font from bitmap strike."""
    # numchars must be given for strikes
    # assume byte-aligned at end of strike only
    strike_bytes = ceildiv(numchars * width, 8)
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
        for _n in range(numchars)
    ]
    return cells

def load_aligned(instream, width, height, numchars=None, padding=0):
    """Load fixed-width font from byte-aligned bitmap."""
    if numchars is None:
        rombytes = instream.read()
    else:
        rombytes = instream.read(numchars * (ceildiv(width, 8)*height + padding))
    return parse_aligned(rombytes, width, height, numchars, padding=padding)

def parse_aligned(rombytes, width, height, numchars=None, offset=0, padding=0):
    """Load fixed-width font from byte-aligned bitmap."""
    if numchars is None:
        # get number of chars in extract
        numchars = ceildiv(len(rombytes), (ceildiv(width, 8)*height + padding))
    rowbytes = ceildiv(width, 8)
    bytesize = rowbytes*height + padding
    # get chunks
    glyphbytes = [
        rombytes[offset+_ord*bytesize : offset+(_ord+1)*bytesize-padding]
        for _ord in range(numchars)
    ]
    # concatenate rows
    cells = [
        Glyph.from_bytes(_bytes, width)
        for _bytes in glyphbytes
    ]
    return cells
