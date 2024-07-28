"""
monobit.storage.formats.vtfont - FreeBSD vt consolve font file

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import deque

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char, Raster
from monobit.base.struct import big_endian as be
from monobit.base.binary import ceildiv

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single, make_contiguous, ensure_charcell


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
    name='vtfont',
    magic=(_VFNT_MAGIC,),
    patterns=('*.fnt',),
)
def load_vfnt(instream):
    """Load a vtfont font."""
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
    rle_maps = (
        (_VFNT_MAP * header.fh_map_count[_i]).read_from(instream)
        for _i in range(4)
    )
    # label glyph halves
    expanded_maps = {}, {}, {}, {}
    for map, exp_map in zip(rle_maps, expanded_maps):
        for entry in map:
            for offset in range(entry.vfm_len+1):
                char = Char(chr(entry.vfm_src + offset))
                index = entry.vfm_dst + offset
                exp_map[char] = index
    # construct dict to hold original and merged rasters
    rasters = {
        _index: _glyph.pixels
        for _index, _glyph in enumerate(raw_glyphs)
    }
    for map_index in (0, 2):
        # merge left- and right-hand halves
        for char, rh_index in expanded_maps[map_index+1].items():
            # use index 0 as default (per comments in the source)
            lh_index = expanded_maps[map_index].get(char, 0)
            expanded_maps[map_index][char] = (lh_index, rh_index)
            if (lh_index, rh_index) not in rasters:
                rasters[(lh_index, rh_index)] = Raster.concatenate(
                    rasters[lh_index], rasters[rh_index]
                )
    # create index-to-label maps
    index_to_labels = {0: {}, 2: {}}
    for map_index in (0, 2):
        for char, indices in expanded_maps[map_index].items():
            if indices in index_to_labels[map_index]:
                index_to_labels[map_index][indices].append(char)
            else:
                index_to_labels[map_index][indices] = [char]
    # create labelled glyphs
    normal_glyphs = tuple(
        Glyph(rasters[_index], labels=_labels)
        for _index, _labels in index_to_labels[0].items()
    )
    bold_glyphs = tuple(
        Glyph(rasters[_index], labels=_labels)
        for _index, _labels in index_to_labels[2].items()
    )
    # create fonts for normal and bold, if present
    fonts = tuple(
        Font(_g, weight=_w)
        for _w, _g in {'regular': normal_glyphs, 'bold': bold_glyphs}.items()
        if _g
    )
    return fonts


@savers.register(linked=load_vfnt)
def save_vfnt(fonts, outstream):
    if len(fonts) > 2 or len(fonts) == 2 and (
            fonts[0].cell_size != fonts[1].cell_size
        ):
        raise ValueError(
            'This format can store only two fonts (regular and bold weight) '
            'of matching cell size.'
        )
    # don't enforce different weights, but if they do have them, put in order
    if fonts[0].weight == 'bold' and fonts[1].weight == 'regular':
        fonts = reversed(fonts)
    # select glyphs with char labels only
    fonts = tuple(_f.label().subset(chars=_f.get_chars()) for _f in fonts)
    # split double-width glyphs
    split_fonts = []
    for font in fonts:
        font = font.equalise_horizontal()
        if font.spacing == 'multi-cell':
            left = Font(
                _g if _g.width == font.cell_size.x
                else _g.crop(right=font.cell_size.x, adjust_metrics=False)
                for _g in font.glyphs
                if _g.width <= font.cell_size.x * 2
            )
            right = Font(
                _g.crop(left=font.cell_size.x, adjust_metrics=False)
                for _g in font.glyphs
                if _g.width == font.cell_size.x * 2
            )
            split_fonts.extend((left, right))
        elif font.spacing == 'character-cell':
            split_fonts.extend((font, Font()))
        else:
            raise ValueError(
                'This format only supports character-cell and multi-cell fonts.'
            )
    fonts = split_fonts
    maps = []
    base_index = 0
    for font in fonts:
        # generate char ranges
        # use first char label initially, assumption is that these are likely contiguous
        ucps = [
            # skip unicode sequences
            (_i, deque(ord(_c) for _c in _g.chars if len(_c) == 1))
            for _i, _g in enumerate(font.glyphs, base_index)
        ]
        map = []
        while any(_deq for _i, _deq in ucps):
            last_char = -2
            current_entry = None
            for index, chardeq in ucps:
                if not chardeq:
                    last_char = -2
                    continue
                char = chardeq.popleft()
                if char != last_char + 1 or current_entry is None:
                    if current_entry is not None:
                        map.append(current_entry)
                    current_entry = _VFNT_MAP(vfm_src=char, vfm_dst=index, vfm_len=0)
                else:
                    current_entry.vfm_len += 1
                last_char = char
            map.append(current_entry)
        maps.append(map)
        base_index += len(font.glyphs)
    # generate header
    header = _VFNT_HEADER(
        fh_magic=_VFNT_MAGIC,
        fh_width=fonts[0].cell_size.x,
        fh_height=fonts[0].cell_size.y,
        fh_pad=0,
        fh_glyph_count=sum(len(_f.glyphs) for _f in fonts),
        fh_map_count=tuple(len(_m) for _m in maps),
    )
    outstream.write(bytes(header))
    for font in fonts:
        save_bitmap(outstream, font)
    for map in maps:
        map = (_VFNT_MAP * len(map))(*map)
        outstream.write(bytes(map))
