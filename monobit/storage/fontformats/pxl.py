"""
monobit.storage.fontformats.pxl - METAFONT PXL font files

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Glob
from monobit.base.struct import big_endian as be
from monobit.base.binary import align
from monobit.base import FileFormatError, UnsupportedError, Props
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
    for cp, glyph_dict in glyph_tfm_data.items():
        size_props = ('width', 'height', 'depth')
        glyphs[cp] = glyphs.get(cp, empty).modify(
            scalable_width=round(glyph_tfm_data[cp].width * pixels_per_point, 2),
            # scalable_height=round((glyph_tfm_data[cp].height+glyph_tfm_data[cp].depth) * pixels_per_point),
            # **{'tfm.depth': glyph_tfm_data[cp].depth * pixels_per_point or None},
            **{f'tfm.{_k}': _v for _k, _v in vars(glyph_tfm_data[cp]).items() if _v and _k not in size_props},
        )
        # glyphs[cp] = glyphs[cp].modify(pixel_width=glyphs[cp].width, pixel_height=glyphs[cp].height)
    return Font(
        glyphs.values(),
        point_size=point_size,
        dpi=dpi,
        x_height=round(tfm_data.x_height * pixels_per_point) or None,
        word_space=round(tfm_data.space * pixels_per_point) or None,
        sentence_space=round((tfm_data.space + tfm_data.extra_space) * pixels_per_point) or None,
        # **{'tfm.slant': tfm_data.slant or None},
    )


# https://web.archive.org/web/20120722013525/http://www-users.math.umd.edu/~asnowden/comp-cont/tfm.html

from monobit.base.struct import bitfield

_TFM_HEADER = be.Struct(
    # > length of the entire file, in words
    lf='uint16',
    # > length of the header data, in words
    lh='uint16',
    # > smallest character code in the font
    bc='uint16',
    # > largest character code in the font
    ec='uint16',
    # > number of words in the width table
    nw='uint16',
    # > number of words in the height table
    nh='uint16',
    # > number of words in the depth table
    nd='uint16',
    # > number of words in the italic correction table
    ni='uint16',
    # > number of words in the lig/kern table
    nl='uint16',
    # > number of words in the kern table
    nk='uint16',
    # > number of words in the extensible character table
    ne='uint16',
    # > number of font parameter words
    np='uint16',
)

_HEADER = be.Struct(
    # > a 32-bit check sum that TeX will copy into the DVI output file whenever it uses the font
    checksum='uint32',
    # > a fix_word containing the design size of the font, in units of TeX points (7227 TeX points = 254 cm)
    design_size='uint32',
    coding_scheme_len='uint8',
    coding_scheme='39s',
    family_len='uint8',
    family='19s',
    seven_bit_safe_flag='uint8',
    ignored='uint16',
    face='uint8',
)

_CHAR_INFO = be.Struct(
    width_index=bitfield('uint32', 8),
    height_index=bitfield('uint32', 4),
    depth_index=bitfield('uint32', 4),
    italic_index=bitfield('uint32', 6),
    tag=bitfield('uint32', 2),
    remainder=bitfield('uint32', 8),
)

_LIG_KERN = be.Struct(
    skip_byte='uint8',
    next_char='uint8',
    op_byte='uint8',
    remainder='uint8',
)

_EXTENSIBLE_RECIPE = be.Struct(
    top='uint8',
    mid='uint8',
    bot='uint8',
    rep='uint8',
)

_PARAM = be.Struct(
    slant='int32',
    space='uint32',
    space_stretch='int32',
    space_shrink='int32',
    x_height='uint32',
    quad='uint32',
    extra_space='uint32',
)

def read_tfm(instream):
    """Read a Tex Font Metrics file."""
    tfmh = _TFM_HEADER.read_from(instream)
    headerbytes = (be.uint32 * tfmh.lh).read_from(instream)
    headerbytes = bytes(headerbytes).ljust(_HEADER.size, b'\0')
    header = _HEADER.from_bytes(headerbytes[:_HEADER.size])
    n_chars = tfmh.ec - tfmh.bc + 1
    char_info = (_CHAR_INFO * n_chars).read_from(instream)
    widths = (be.uint32 * tfmh.nw).read_from(instream)
    heights = (be.uint32 * tfmh.nh).read_from(instream)
    depths = (be.int32 * tfmh.nd).read_from(instream)
    italics = (be.int32 * tfmh.ni).read_from(instream)
    lig_kerns = (_LIG_KERN * tfmh.nl).read_from(instream)
    kerns = (be.int32 * tfmh.nk).read_from(instream)
    extens = (_EXTENSIBLE_RECIPE * tfmh.ne).read_from(instream)
    parambytes = (be.uint32 * tfmh.np).read_from(instream)
    parambytes = bytes(parambytes).ljust(_PARAM.size, b'\0')
    param = _PARAM.from_bytes(parambytes[:_PARAM.size])
    param_dict = vars(param)
    size_factor = header.design_size / 2**20 / 2**20
    param_dict = {
        _k: _v * size_factor
        for _k, _v in param_dict.items()
        if _k != 'slant'
    }
    tfm_glyph_data = {
        _cp: Props(
            # codepoint=_cp,
            width=widths[_ci.width_index] * size_factor,
            height=heights[_ci.height_index] * size_factor,
            depth=depths[_ci.depth_index] * size_factor,
            italic_adj=italics[_ci.italic_index] * size_factor,
            tag=_ci.tag,
            remainder=_ci.remainder,
            lig_kern=lig_kerns[_ci.remainder] if _ci.tag == 1 else None,
            ext=extens[_ci.remainder] if _ci.tag == 3 else None,
        )
        for _cp, _ci in enumerate(char_info, tfmh.bc)
    }
    tfm_data = Props(
        design_size=header.design_size / 2**20,
        slant=param.slant / 2**20,
        **param_dict
    )
    return tfm_data, tfm_glyph_data
