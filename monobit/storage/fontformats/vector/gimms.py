"""
monobit.storage.formats.vector.gimms - GIMMS.BIN

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# GIMMS vector fonts, as decoded by EDWIN
# see https://gtoal.com/vectrex/vector_fonts/gimms/
#     https://gtoal.com/vectrex/vector_fonts/gimms/GIMMS.imp.html

import logging

from monobit.storage import loaders, savers, Magic
from monobit.storage import FileFormatError
from monobit.base.struct import StructError, big_endian as be
from monobit.core import Font, Glyph, StrokePath, StrokeMove


_GIMMS_MAGIC = Magic.offset(4) + b'GIMM'

@loaders.register(
    name='gimms',
    magic=(_GIMMS_MAGIC,),
)
def load_gimms(instream):
    """Read GIMMS.BIN font file."""
    fonts = []
    while True:
        font = _read_gimms_resource(instream)
        if not font:
            break
        fonts.append(font)
    return fonts


_HEADER = be.Struct(
    fontlength='uint32',
    gimm='4s',
    number='4s',
    padding='16s',
    scale='uint16',
    xx='uint8',
    yy='uint8',
    start=be.uint16 * 128,
)

_PENUP = 1 << 15
_LASTVECTOR = 1 << 7

_CHARHEADER = be.Struct(
    xbias='uint8',
    xmax='uint8',
    ybias='uint8',
    ymax='uint8',
    # data='uint16',
)


def _read_gimms_resource(instream):
    """Read font resource from GIMMS.BIN file."""
    try:
        gimms_header = _HEADER.read_from(instream)
    except StructError:
        return None
    if gimms_header.gimm != b'GIMM':
        raise FileFormatError(
            f'Not a GIMMS font: `GIMM` signature not found'
        )
    chdata = instream.read(gimms_header.fontlength - _HEADER.size)
    glyphs = []
    for cp, start in enumerate(gimms_header.start):
        if not start:
            continue
        offset = start - 256
        charheader = _CHARHEADER.from_bytes(chdata[offset:])
        offset += _CHARHEADER.size
        # biases will define left_bearing and shift_up
        lastx, lasty = charheader.xbias, charheader.ybias
        path = []
        while True:
            codeword = int(be.uint16.from_bytes(chdata[offset:offset+2]))
            offset += 2
            x = (codeword>>8) & 127
            y = codeword & 127
            if codeword & _PENUP:
                path.append((StrokePath.MOVE, x-lastx, y-lasty))
            else:
                path.append((StrokePath.LINE, x-lastx, y-lasty))
            lastx, lasty = x, y
            if codeword & _LASTVECTOR:
                break
        glyphs.append(
            Glyph.from_path(path, codepoint=cp)
        )
    return Font(glyphs, name=f"GIMMS-{gimms_header.number.decode('latin-1')}")
