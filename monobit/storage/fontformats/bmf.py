"""
monobit.storage.fontformats.bmf - ByteMap format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from monobit.base.binary import ceildiv
from monobit.base.struct import bitfield, little_endian as le
from monobit.base import Props, UnsupportedError
from monobit.storage import loaders, savers
from monobit.core import Font, Glyph

from monobit.storage.utils.limitations import ensure_single, ensure_levels



@loaders.register(
    name='bmf',
    magic=(b'\xe1\xe6\xd5\x1a',),
    patterns=('*.bmf',),
)
def load_bmf(instream):
    """Load font from bytemap format file."""
    bmf = _read_bmf(instream)
    font = _convert_bmf(bmf)
    return font


_BMF_HEADER = le.Struct(
    magic='4s',
    version='uint8',
    lineHeight='uint8',
    sizeOver='int8',
    sizeUnder='int8',
    addSpace='int8',
    sizeInner='int8',
    usedColors='uint8',
    highestAttribute='uint8',
    # 1.2 only, reserved in 1.1
    alphaBits='uint8',
    # 1.2 only, reserved in 1.1
    extraPalettes='uint8',
    reserved0='uint16',
    numColorsEx0='uint8',
)

_RGB_ENTRY = le.Struct(
    r='uint8',
    g='uint8',
    b='uint8',
)

_TABLO_ENTRY = le.Struct(
    width='uint8',
    height='uint8',
    relX='int8',
    relY='int8',
    shift='uint8'
)

def _read_bmf(instream):
    """Read a ByteMap Format font."""
    bmf = Props()
    bmf.header = _BMF_HEADER.read_from(instream)
    bmf.palette = (_RGB_ENTRY * bmf.header.numColorsEx0).read_from(instream)
    title_length = int(le.uint8.read_from(instream))
    bmf.title = instream.read(title_length)
    bmf.asciiChars = int(le.uint16.read_from(instream))
    bmf.glyphs = []
    for cp in range(bmf.asciiChars):
        gp = Props()
        gp.which = instream.read(1)
        gp.tablo = _TABLO_ENTRY.read_from(instream)
        gp.bitmap = instream.read(gp.tablo.width*gp.tablo.height)
        # - some bmf files appear to have byte values outside the palette range
        # - potential conflict higestAttribute vs. numColorsEx0 vs. numColors
        gp.bitmap = bytes(min(_b, bmf.header.highestAttribute) for _b in gp.bitmap)
        bmf.glyphs.append(gp)
    logging.debug(bmf)
    # TODO v1.2 extensions
    return bmf

def _convert_bmf(bmf):
    """Convert BMF font."""
    # convert glyphs
    glyphs = tuple(
        Glyph.from_bytes(
            _gp.bitmap,
            bits_per_pixel=8,
            levels=len(bmf.palette) + 1,
            width=_gp.tablo.width,
            # ""its ASCII code 0..255"". Assume they mean latin-1
            codepoint=_gp.which,
            char=_gp.which.decode('latin-1'),
            left_bearing=_gp.tablo.relX,
            right_bearing=(
                _gp.tablo.shift - _gp.tablo.width - _gp.tablo.relX
                + bmf.header.addSpace
            ),
            shift_up=(
                bmf.header.lineHeight - bmf.header.sizeUnder
                - _gp.tablo.relY - _gp.tablo.height
            ),
            tablo=_gp.tablo
        )
        for _gp in bmf.glyphs
    )
    # convert palette
    rgb_table = ((0, 0, 0),) + tuple(
        (_p.r*255//63, _p.g*255//63, _p.b*255//63) for _p in bmf.palette
    )
    # convert font metrics
    return Font(
        glyphs, x_height=-bmf.header.sizeInner,
        ascent=-bmf.header.sizeOver, descent=bmf.header.sizeUnder,
        line_height=bmf.header.lineHeight,
        # assumed latin-1 for 1.1; 1.2 is unicode
        encoding='latin-1',
        rgb_table=rgb_table,
        bmf=bmf.header,
        bmfpalette=bmf.palette,
    )
