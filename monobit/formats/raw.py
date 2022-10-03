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
        cell:pair=(8, 8), count:int=-1, offset:int=0, padding:int=0,
        strike:bool=False, align:str='left',
        first_codepoint:int=0
    ):
    """
    Load character-cell font from byte-aligned binary or bitmap strike.

    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyphs (default: 0; ignored if strike==True)
    count: number of glyphs to extract (<= 0 means all; default: all)
    strike: bitmap is in strike format rather than byte-aligned (default: False)
    align: alignment of glyph in byte (left for most-, right for least-significant; default: left; ignored if strike==True)
    first_codepoint: first code point in bitmap (default: 0)
    """
    width, height = cell
    # get through the offset
    # we don't assume instream is seekable - it may be sys.stdin
    instream.read(offset)
    if strike:
        glyphs = load_strike(instream, width, height, count)
    else:
        glyphs = load_aligned(
            instream, width, height, count, padding, align
        )
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


def load_strike(instream, width, height, count):
    """Load fixed-width font from bitmap strike."""
    # count must be given for strikes
    # assume byte-aligned at end of strike only
    strike_bytes = ceildiv(count * width, 8)
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
        for _n in range(count)
    ]
    return cells

def load_aligned(
        instream, width, height, count=-1, padding=0, align='left'
    ):
    """Load fixed-width font from byte-aligned bitmap."""
    if count is None or count <= 0:
        rombytes = instream.read()
    else:
        rombytes = instream.read(count * (ceildiv(width, 8)*height + padding))
    return parse_aligned(rombytes, width, height, count, padding=padding, align=align)

def parse_aligned(
        rombytes, width, height, count=-1, offset=0, padding=0, align='left',
    ):
    """Load fixed-width font from byte-aligned bitmap."""
    if count is None or count <= 0:
        # get number of chars in extract
        count = ceildiv(len(rombytes), (ceildiv(width, 8)*height + padding))
    rowbytes = ceildiv(width, 8)
    bytesize = rowbytes*height + padding
    # get chunks
    glyphbytes = [
        rombytes[offset+_ord*bytesize : offset+(_ord+1)*bytesize-padding]
        for _ord in range(count)
    ]
    # concatenate rows
    cells = [
        Glyph.from_bytes(_bytes, width, align=align)
        for _bytes in glyphbytes
    ]
    return cells
