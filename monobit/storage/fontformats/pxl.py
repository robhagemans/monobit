"""
monobit.storage.fontformats.pxl - METAFONT PXL font files

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Glob
from monobit.base.struct import big_endian as be
from monobit.base.binary import align
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Font, Glyph


# https://tug.org/TUGboat/tb02-3/tb04fuchspxl.pdf

_PXL_IDS = (b'\0\0\3\xe9', b'\0\0\3\xea',)

_PXL_PRE = be.Struct(
    pxl_id='uint32',
)

_PXL_POST = be.Struct(
    checksum='uint32',
    magnification='uint32',
    designsize='uint32',
    directory_pointer='uint32',
    pxl_id='uint32',
)

_DIR_ENTRY = be.Struct(
    pixel_width='uint16',
    pixel_height='uint16',
    x_offset='int16',
    y_offset='int16',
    raster_pointer='uint32',
    tfm_width='uint32',
)

@loaders.register(
    name='pxl',
    magic=_PXL_IDS,
    patterns=(Glob('*.PXL'),),
)
def load_pxl(instream):
    """Load fonts from a METAFONT PXL file."""
    preamble = _PXL_PRE.read_from(instream)
    if bytes(preamble) not in _PXL_IDS:
        raise FileFormatError(
            f'Not a METAFONT PXL file: incorrect PXL ID {preamble.pxl_id}'
        )
    byte_align = preamble.pxl_id == 1002
    if byte_align:
        align_exp = 3
    else:
        align_exp = 5
    data = instream.read()
    font_directory = (_DIR_ENTRY * 128).from_bytes(data[-2048-20:-20])
    postamble = _PXL_POST.from_bytes(data[-20:])
    glyphs = []
    for cp, entry in enumerate(font_directory):
        if entry.raster_pointer == 0:
            glyph = Glyph(codepoint=cp, **vars(entry))
        else:
            if byte_align:
                raster_offset = entry.raster_pointer-4
            else:
                raster_offset = (entry.raster_pointer-1)*4
            glyph = Glyph.from_bytes(
                data[raster_offset:],
                width=entry.pixel_width,
                height=entry.pixel_height,
                stride=align(entry.pixel_width, align_exp),
                codepoint=cp,
                shift_up=-entry.pixel_height+entry.y_offset+1,
                left_bearing=-entry.x_offset,
                **{'metafont.tfm_width': entry.tfm_width/2**20},
            )
        glyphs.append(glyph)
    return Font(
        glyphs, point_size=postamble.designsize/2**20,
        **{'metafont.magnification': postamble.magnification / 1000},
    )
