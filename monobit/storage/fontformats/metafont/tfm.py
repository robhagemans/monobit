"""
monobit.storage.fontformats.metafont.tfm - TeX font metrics files

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be
from monobit.base import Props
from monobit.base.struct import bitfield
from monobit.core import Font


# https://web.archive.org/web/20120722013525/http://www-users.math.umd.edu/~asnowden/comp-cont/tfm.html
# https://www.tug.org/TUGboat/Articles/tb02-1/tb02fuchstfm.pdf
# https://en.wikipedia.org/wiki/TeX_font_metric


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


def apply_tfm(font, location, tfm_name, hppp, vppp=None):
    """Enrich font with metrics from TFM file, if found."""
    try:
        with location.open(tfm_name, 'r') as tfm_stream:
            tfm_data, glyph_tfm_data = read_tfm(tfm_stream)
    except EnvironmentError as err:
        logging.info(f'Could not open TFM file {location}/{tfm_name}')
        return font
    if vppp is None:
        vppp = hppp
    glyphs = []
    for glyph in font.glyphs:
        try:
            glyph_data = glyph_tfm_data[int(glyph.codepoint)]
        except KeyError:
            continue
        size_props = ('width', 'height', 'depth', 'kerns')
        glyph = glyph.modify(
            scalable_width=round(glyph_data.width * hppp, 2),
            # scalable_height=round((glyph_data.height+glyph_data.depth) * vppp),
            # **{'tfm.depth': glyph_tfm_data[cp].depth * hppp or None},
            right_kerning={_k: round(_v * hppp, 2) for _k, _v in glyph_data.kerns.items()},
            **{f'tfm.{_k}': _v for _k, _v in vars(glyph_data).items() if _v and _k not in size_props},
        )
        glyphs.append(glyph)
    return font.modify(
        glyphs,
        x_height=round(tfm_data.x_height * vppp) or None,
        word_space=round(tfm_data.space * hppp) or None,
        sentence_space=round((tfm_data.space + tfm_data.extra_space) * hppp) or None,
        # **{'tfm.slant': tfm_data.slant or None},
    )


def read_tfm(instream):
    """Read a TeX Font Metrics file."""
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
            # > 0   no_tag      means that remainder is unused.
            # > 1   lig_tag     means that this character has a ligature/kerning program starting
            # >                 at lig_kern[remainder].
            # > 2   list_tag    means that this character is part of a chain of characters of ascending
            # >                 sizes, and not the largest in the chain. The remainder field gives the
            # >                 character code of the next larger character.
            # > 3   ext_tag     means that this character code represents an extensible character, i.e.,
            # >                 a character that is built up of smaller pieces so that it can be made arbitrarily
            # >                 large. The pieces are specified in exten[remainder].
            lig_kern_index=_ci.remainder if _ci.tag == 1 else None,
            list_next=_ci.remainder if _ci.tag == 2 else None,
            extensible_recipe=extens[_ci.remainder] if _ci.tag == 3 else None,
        )
        for _cp, _ci in enumerate(char_info, tfmh.bc)
    }
    # parse lig_kern table
    for cp, props in tfm_glyph_data.items():
        kern_table = {}
        lig_table = Props()
        if props.lig_kern_index is not None:
            step = props.lig_kern_index
            while True:
                lig_kern = lig_kerns[step]
                # > op_byte indicates a ligature step if less than 128, a kern step otherwise.
                is_ligature = lig_kern.op_byte < 128
                # ligature step not implemented
                if is_ligature:
                    a = (lig_kern.op_byte >> 2) & 31
                    b = (lig_kern.op_byte >> 1) & 1
                    c = (lig_kern.op_byte >> 0) & 1
                    lig_table.insert = lig_kern.remainder
                    lig_table.next_char = lig_kern.next_char
                    lig_table.delete_current = b == 0
                    lig_table.delete_next = c == 0
                    lig_table.skip = a
                else:
                    kern_table[lig_kern.next_char] = (
                        kerns[256 * (lig_kern.op_byte-128) + lig_kern.remainder] / 2**20
                    )
                if lig_kern.skip_byte >= 128:
                    break
                step += (lig_kern.skip_byte & 0x7f) + 1
        tfm_glyph_data[cp].kerns = kern_table
        tfm_glyph_data[cp].ligatures = lig_table
        del tfm_glyph_data[cp].lig_kern_index
    tfm_data = Props(
        design_size=header.design_size / 2**20,
        slant=param.slant / 2**20,
        **param_dict
    )
    return tfm_data, tfm_glyph_data
