"""
monobit.storage.formats.vfnt2 - FreeBSD vfnt2 file

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import big_endian as be
from monobit.base.binary import ceildiv

from .raw import load_bitmap, save_bitmap
from .limitations import ensure_single, make_contiguous, ensure_charcell


# https://codeberg.org/FreeBSD/freebsd-src/src/branch/main/sys/sys/font.h

# see also John Zaitseff's freebsdvfntio
# https://www.zap.org.au/projects/console-fonts-utils/src/freebsdvfntio.py


_VFNT_MAGIC = b'VFNT0002'

_VFNT_HEADER = be.Struct(
    fh_magic='8s',
    fh_width='uint8',
    fh_height='uint8',
    fh_pad='uint16',
    fh_glyph_count='uint32',
    fh_map_count=be.uint32 * 4,
)

# > Fonts support normal and bold weights, and single and double width glyphs.
# > Mapping tables are used to map Unicode points to glyphs.  They are sorted by
# > code point, and vtfont_lookup() uses this to perform a binary search.  Each
# > font has four mapping tables: two weights times two halves (left/single,
# > right).  When a character is not present in a bold map the glyph from the
# > normal map is used.  When no glyph is available, it uses glyph 0, which is
# > normally equal to U+FFFD.

_VFNT_MAP = be.Struct(
    # starting unicode code point
    vfm_src='uint32',
    # starting glyph index
    vfm_dst='uint16',
    # number of glyphs to apply to, less one
    vfm_len='uint16',
)


@loaders.register(
    name='vfnt2',
    magic=(_VFNT_MAGIC,),
    patterns=('*.fnt',),
)
def load_vfnt(instream):
    """Load a vfnt2 font."""
    header = _VFNT_HEADER.read_from(instream)
    glyphs = load_bitmap(
        instream,
        width=header.fh_width, height=header.fh_height,
        count=header.fh_glyph_count,
    ).glyphs
    # generated codepoint is not meaningful
    raw_glyphs = list(_g.modify(codepoint=None) for _g in glyphs)
    # > VFNT_MAP_NORMAL = 0,    /* Normal font. */
    # > VFNT_MAP_NORMAL_RIGHT,  /* Normal font right hand. */
    # > VFNT_MAP_BOLD,          /* Bold font. */
    # > VFNT_MAP_BOLD_RIGHT,    /* Bold font right hand. */
    mapses = (
        (_VFNT_MAP * header.fh_map_count[_i]).read_from(instream)
        for _i in range(4)
    )
    # label glyph halves
    glyphses = {}, {}, {}, {}
    for glyphs, map in zip(glyphses, mapses):
        for entry in map:
            for offset in range(entry.vfm_len+1):
                char = Char(chr(entry.vfm_src + offset))
                index = entry.vfm_dst + offset
                glyph = raw_glyphs[index]
                glyphs[index] = glyph.modify(
                    labels=list(glyph.get_labels()) + [char]
                )
    # merge left- and right-hand halves
    for map_index in (0, 2):
        try:
            default = glyphses[map_index][0]
        except KeyError:
            continue
        for index, rh_glyph in glyphses[map_index+1].items():
            lh_glyph = glyphses[map_index].get(index, default)
            glyphses[map_index][index] = Glyph(
                Raster.concatenate(lh_glyph.pixels, rh_glyph.pixels),
                labels=rh_glyph.get_labels()
            )
    # get sorted lists of glyphs
    normal_glyphs = tuple(glyphses[0][_i] for _i in sorted(glyphses[0].keys()))
    bold_glyphs = tuple(glyphses[2][_i] for _i in sorted(glyphses[2].keys()))
    # create fonts for normal and bold, if present
    fonts = tuple(
        Font(_g, weight=_w)
        for _w, _g in {'regular': normal_glyphs, 'bold': bold_glyphs}.items()
        if _g
    )
    return fonts
