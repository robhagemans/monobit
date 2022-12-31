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
from ..basetypes import Coord


@loaders.register('bin', 'rom', 'raw', 'f08', 'f14', 'f16', name='binary')
def load_binary(
        instream, where=None, *,
        cell:Coord=(8, 8), count:int=-1, offset:int=0, padding:int=0,
        align:str='left', strike_count:int=1, strike_bytes:int=-1,
        first_codepoint:int=0
    ):
    """
    Load character-cell font from byte-aligned binary or bitmap strike.

    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyph rows (default: 0)
    count: number of glyphs to extract (<= 0 means all; default: all)
    align: alignment of glyph in byte (left for most-, right for least-significant; default: left; ignored if strike==True)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    first_codepoint: first code point in bitmap (default: 0)
    """
    width, height = cell
    # get through the offset
    # we don't assume instream is seekable - it may be sys.stdin
    instream.read(offset)
    return load_bitmap(
        instream, width, height, count, padding, align, strike_count, strike_bytes, first_codepoint
    )


@savers.register(linked=load_binary)
def save_binary(fonts, outstream, where=None):
    """
    Save character-cell font to byte-aligned binary.
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to raw binary file.')
    save_bitmap(outstream, fonts[0])


def save_bitmap(outstream, font):
    """Save fixed-width font to byte-aligned bitmap."""
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    for glyph in font.glyphs:
        outstream.write(glyph.as_bytes())


def load_bitmap(
        instream, width, height, count=-1, padding=0, align='left',
        strike_count=1, strike_bytes=-1, first_codepoint=0,
    ):
    """Load fixed-width font from bitmap."""
    rombytes = None
    if strike_bytes <= 0:
        if strike_count <= 0:
            rombytes = instream.read()
            strike_bytes = ceildiv(len(rombytes), height)
        else:
            strike_bytes = ceildiv(strike_count*width, 8)
    else:
        strike_count = -1
    if strike_count <= 0:
        strike_count = (strike_bytes * 8) // width
    row_bytes = strike_bytes*height + padding
    if count is None or count <= 0:
        if not rombytes:
            rombytes = instream.read()
        # get number of chars in extract
        nrows = ceildiv(len(rombytes), row_bytes)
        count = nrows * strike_count
    else:
        nrows = ceildiv(count, strike_count)
        if not rombytes:
            rombytes = instream.read(nrows * row_bytes)
    # we may exceed the length of the rom because we use ceildiv, pad with nulls
    rombytes = rombytes.ljust(nrows * row_bytes, b'\0')
    glyphrows = [
        [
            rombytes[
                _glyphrow*row_bytes+_pixelrow*strike_bytes
                : _glyphrow*row_bytes+(_pixelrow+1)*strike_bytes
            ]
            for _pixelrow in range(height)
        ]
        for _glyphrow in range(nrows)
    ]
    # convert to bits
    drawn_glyphrows = [
        [
            bytes_to_bits(_row)
            for _row in _glyphrow
        ]
        for _glyphrow in glyphrows
    ]
    if align.startswith('r') and drawn_glyphrows and drawn_glyphrows[0]:
        bitoffset = len(drawn_glyphrows[0][0]) - strike_count*width
    else:
        bitoffset = 0
    drawn_glyphrows = [
        [
            _row[bitoffset:]
            for _row in _glyphrow
        ]
        for _glyphrow in drawn_glyphrows
    ]
    # clip out glyphs
    cells = tuple(
        tuple(
            _row[_n*width:(_n+1)*width]
            for _row in _glyphrow
        )
        for _glyphrow in drawn_glyphrows
        for _n in range(strike_count)
    )
    # assign codepoints
    glyphs = tuple(
        Glyph(_cell, codepoint=_index)
        for _index, _cell in enumerate(cells, first_codepoint)
    )
    return Font(glyphs)


###############################################################################
# OPTIKS PCR - near-raw format
# http://fileformats.archiveteam.org/wiki/PCR_font
# http://cd.textfiles.com/simtel/simtel20/MSDOS/GRAPHICS/OKF220.ZIP
# OKF220.ZIP → OKFONTS.ZIP → FONTS.DOC - Has an overview of the format.

from ..struct import little_endian as le

_PCR_HEADER = le.Struct(
    magic='7s',
    # maybe it's a be uint16 of the file size, followed by the same size as le
    # anyway same difference
    height='uint8',
    zero='uint8',
    bytesize='uint16',
)

@loaders.register('pcr', name='pcr', magic=(b'KPG\1\2\x20\1', 'KPG\1\1\x20\1'))
def load_pcr(instream, where=None):
    """Load an OPTIKS .PCR font."""
    header = _PCR_HEADER.read_from(instream)
    return load_binary(instream, where, cell=(8, header.height), count=256)
