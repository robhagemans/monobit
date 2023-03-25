"""
monobit.formats.dashen - Dashen font

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..binary import ceildiv
from ..struct import little_endian as le
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..properties import Props
from ..magic import Magic, FileFormatError

from .pcl import load_hppcl


@loaders.register(
    name='dashen',
    patterns=('*.pft',),
    # maybe-magic. first entry in offsets table, for NUL
    magic=(Magic.offset(14) + b'\xff\xff\xff\xff',),
)
def load_dashen(instream):
    """Load font from Dashen .pft file."""
    dashen_data = _read_dashen(instream)
    # screen font ?
    screen = _convert_dashen(*dashen_data)
    # PCL printer font
    if instream.peek(1):
        printer = load_hppcl(instream)
        printer = printer.modify(encoding='dashen').label()
        return screen, printer
    else:
        return screen


# 14 bytes. all guesses
_DASHEN_HEADER = le.Struct(
    # uint32 offset or size?
    unknown0=le.uint8*4,
    line_height='uint16',
    maybe_cell_width='uint16',
    # 4 (includes pcl font) 3 (no pcl) 1 (1-byte glyph header
    maybe_format_version='uint16',
    maybe_left='uint8',
    maybe_right='uint8',
    top='uint8',
    # descent plus leading?
    bottom='uint8',
)


_DASHEN_GLYPH_HEADER = le.Struct(
    width='uint8',
    shift='uint8',
    height='uint8',
)

def _read_dashen(instream):
    """Read Dashen screen font."""
    header = _DASHEN_HEADER.read_from(instream)
    logging.debug(header)
    # offsets from start of glyph table (i.e. from 1070)
    # 255 le.int32 values, -1 for unused
    offsets = (le.int32 * 256).read_from(instream)
    # perhaps a name string? would be in encoding
    unknown2 = instream.read(32)
    logging.debug(unknown2)
    glyphdata = []
    headers = []
    logging.debug(offsets)
    for offset in offsets:
        if offset == -1:
            glyphdata.append(None)
            headers.append(None)
            continue
        ghdr = _DASHEN_GLYPH_HEADER.read_from(instream)
        headers.append(ghdr)
        glyphdata.append(tuple(
            instream.read(ghdr.width)
            for _ in range(ceildiv(ghdr.height, 8))
        ))
    if instream.peek(1):
        codepoints = (le.uint8 * 256).read_from(instream)
    else:
        codepoints = range(256)
    props = Props(**vars(header), unknown2=unknown2)
    return props, glyphdata, headers, codepoints


def _convert_dashen(props, glyphdata, headers, codepoints):
    """Convert from Dashen font data to monobit."""
    glyphs = []
    for gdata, ghdr, codepoint in zip(glyphdata, headers, codepoints):
        if gdata is None:
            continue
        raster = Raster.concatenate(*(
            Raster.from_bytes(_bytes, width=8)
            for _bytes in gdata
        ))
        raster = raster.transpose()
        # clip off the alignment bits
        raster = raster.crop(bottom=raster.height-ghdr.height)
        glyphs.append(Glyph(
            raster, codepoint=codepoint,
            shift_up=props.top-raster.height-ghdr.shift+1
        ))
    font = Font(
        glyphs,
        line_height=props.line_height,
        encoding='dashen',
    )
    return font.label()
