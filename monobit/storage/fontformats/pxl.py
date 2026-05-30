"""
monobit.storage.fontformats.metafont.pxl - METAFONT PXL font files

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Glob
from monobit.base.struct import big_endian as be
from monobit.base.binary import align
from monobit.base import FileFormatError, UnsupportedError, Props
from monobit.core import Font, Glyph
from .tfm import read_tfm


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
    ### convert properties
    point_size = postamble.designsize / 2**20
    # magnification is scaled by 1000 in PXL file. magnification 1.0 means 200dpi, it seems.
    dpi = 200 * postamble.magnification / 1000
    pixels_per_point = dpi / 72.27
    ### convert glyphs
    glyphs = {}
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
                scalable_width=round(
                    entry.tfm_width/2**20 * point_size * pixels_per_point, 2
                ),
            )
        glyphs[cp] = glyph
    tfm_name = instream.name.replace('.PXL', '.TFM')
    try:
        with instream.where.open(tfm_name, 'r') as tfm_stream:
            tfm_data, glyph_tfm_data = read_tfm(tfm_stream)
    except EnvironmentError as err:
        logging.info(f'Could not open TFM file {instream.where}/{tfm_name}')
        tfm_data = Props(
            x_height=0,
            space=0,
            extra_space=0,
        )
        glyph_tfm_data = {}
    empty = Glyph()
    for cp, glyph_data in glyph_tfm_data.items():
        size_props = ('width', 'height', 'depth', 'kerns')
        try:
            glyphs[cp] = glyphs[cp].modify(
                scalable_width=round(glyph_data.width * pixels_per_point, 2),
                # scalable_height=round((glyph_tfm_data[cp].height+glyph_tfm_data[cp].depth) * pixels_per_point),
                # **{'tfm.depth': glyph_tfm_data[cp].depth * pixels_per_point or None},
                right_kerning={_k: round(_v * pixels_per_point, 2) for _k, _v in glyph_data.kerns.items()},
                **{f'tfm.{_k}': _v for _k, _v in vars(glyph_data).items() if _v and _k not in size_props},
            )
            # glyphs[cp] = glyphs[cp].modify(pixel_width=glyphs[cp].width, pixel_height=glyphs[cp].height)
        except KeyError:
            pass
    return Font(
        glyphs.values(),
        point_size=point_size,
        dpi=dpi,
        x_height=round(tfm_data.x_height * pixels_per_point) or None,
        word_space=round(tfm_data.space * pixels_per_point) or None,
        sentence_space=round((tfm_data.space + tfm_data.extra_space) * pixels_per_point) or None,
        # **{'tfm.slant': tfm_data.slant or None},
    )
