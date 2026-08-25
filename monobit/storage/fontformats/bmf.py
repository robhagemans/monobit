"""
monobit.storage.fontformats.bmf - ByteMap Font format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate
from collections import defaultdict

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


###############################################################################
# ByteMap Font format
# http://bmf.wz.cz:8080/index.php?page=format
# https://zdoom.org/w/index.php?title=Byte_Map_Font

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

_KERNING_ENTRY = le.Struct(
    first='uint32',
    second='uint32',
    correction='int16',
)


###############################################################################
# BMF reader

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
        which = int(le.uint8.read_from(instream))
        bmf.glyphs.append(read_bmf_glyph(instream, which))
    # treat 1.2 tables as optional
    if bmf.header.version >= 0x12 and len(instream.peek(4)) >= 4:
        bmf.unicodeChars = int(le.uint32.read_from(instream))
        for cp in range(bmf.unicodeChars):
            which = int(le.uint32.read_from(instream))
            bmf.glyphs.append(read_bmf_glyph(instream, which))
    else:
        bmf.unicodeChars = 0
    if bmf.header.version >= 0x12 and len(instream.peek(4)) >= 4:
        bmf.kerningPairs = int(le.uint32.read_from(instream))
        bmf.kerningTable = (_KERNING_ENTRY * bmf.kerningPairs).read_from(instream)
    else:
        bmf.kerningTable = ()
    # some bmf files appear to have byte values outside the palette range
    # potential conflict higestAttribute vs. numColorsEx0 vs. numColors
    for gp in bmf.glyphs:
        gp.bitmap = bytes(min(_b, bmf.header.highestAttribute) for _b in gp.bitmap)
    logging.debug(bmf)
    return bmf


def read_bmf_glyph(instream, which):
    """Read tablo and bitmap for one glyph."""
    gp = Props()
    gp.which = which
    gp.tablo = _TABLO_ENTRY.read_from(instream)
    gp.bitmap = instream.read(gp.tablo.width*gp.tablo.height)
    return gp


def _convert_bmf(bmf):
    """Convert BMF font."""
    kerning_map = defaultdict(list)
    if bmf.header.version >= 0x12:
        for kern in bmf.kerningTable:
            kerning_map[kern.first][kern.second] = kern.correction
    kerning_map = dict(kerning_map)
    # convert glyphs
    glyphs = tuple(
        Glyph.from_bytes(
            _gp.bitmap,
            bits_per_pixel=8,
            levels=len(bmf.palette) + 1,
            width=_gp.tablo.width,
            # ""its ASCII code 0..255"". No codepage defined
            codepoint=_gp.which,
            left_bearing=_gp.tablo.relX,
            right_bearing=(
                _gp.tablo.shift - _gp.tablo.width - _gp.tablo.relX
                + bmf.header.addSpace
            ),
            shift_up=(
                bmf.header.lineHeight - bmf.header.sizeUnder
                - _gp.tablo.relY - _gp.tablo.height
            ),
            right_kerning=kerning_map.get(_gp.which, None),
        )
        for _gp in bmf.glyphs
    )
    # convert palette
    # NOTE: color 0 is defined as transparent, not black
    # TODO: update when we support alpha in palettes
    rgb_table = ((0, 0, 0),) + tuple(
        (_p.r*255//63, _p.g*255//63, _p.b*255//63) for _p in bmf.palette
    )
    # -- convert font metrics and metadata
    # encoding of the title is not defined in the spec.
    # https://github.com/JoeStrout/minimicro-fonts/blob/main/bmfFonts.ms uses UTF-8
    if bmf.header.version >= 0x12:
        title = bmf.title.decode('utf-8', errors='replace')
    else:
        # assumption, consistent with the font's encoding
        title = bmf.title.decode('cp437')
    font = Font(
        glyphs, x_height=-bmf.header.sizeInner,
        ascent=-bmf.header.sizeOver, descent=bmf.header.sizeUnder,
        line_height=bmf.header.lineHeight,
        rgb_table=rgb_table,
        name=title,
        source_format=f'bmf 1.{bmf.header.version-0x10}',
    )
    if bmf.header.version >= 0x12:
        # as defined in the spec
        font = font.label(char_from='unicode')
    else:
        # not defined in the spec. CP 437 is consistent with BMF gallery web site
        font = font.label(char_from='cp437')
    return font
