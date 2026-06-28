"""
monobit.storage.fontformats.oberon - ETH Oberon font files

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import chain

from monobit.storage import loaders, savers
from monobit.storage.utils.limitations import ensure_single, ensure_levels
from monobit.core import Font, Glyph, Raster
from monobit.encoding.indexers import find_ranges
from monobit.base import FileFormatError, UnsupportedError, struct
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv

_FONT_FILE_ID = 0xdb

# offset 0
_HEADER = le.Struct(
    ident='uint8',
    abstraction='uint8',
    family='uint8',
    variant='uint8',
    height='uint16',
    minX='int16',
    maxX='int16',
    minY='int16',
    maxY='int16',
    NofRuns='uint16',
)
_RUN = le.Struct(
    beg='uint16',
    end='uint16'
)
_BOX = le.Struct(
    dx='int16',
    x='int16',
    y='int16',
    w='int16',
    h='int16',
)

@loaders.register(
    name='oberon',
    magic=(b'\xdb\0',),
    patterns=('*.Scn.Fnt', '*.Pr?.Fnt'),
)
def load_oberon(instream):
    """
    Load an ETH Project Oberon font file.
    """
    header = _HEADER.read_from(instream)
    logging.debug(header)
    if header.ident != _FONT_FILE_ID:
        raise FileFormatError('Not an ETH Oberon font file.')
    if header.abstraction:
        raise UnsupportedError('Oberon "abstraction" font files not supported.')
    # read runs
    runs = (_RUN * header.NofRuns).read_from(instream)
    logging.debug(runs)
    n_boxes = sum(_run.end - _run.beg for _run in runs)
    cps = chain.from_iterable(range(_run.beg, _run.end) for _run in runs)
    boxes = (_BOX * n_boxes).read_from(instream)
    logging.debug(boxes)
    glyphs = tuple(
        Glyph(
            Raster.from_bytes(
                instream.read(ceildiv(_box.w, 8) * _box.h),
                width=_box.w,
                bit_order='little',
            ).flip(),
            left_bearing=_box.x,
            right_bearing=_box.dx-_box.w-_box.x,
            shift_up=_box.y,
            codepoint=_cp,
        )
        for _box, _cp in zip(boxes, cps)
    )
    return Font(
        glyphs,
        line_height=header.height,
        **{
            'oberon.family': header.family,
            'oberon.variant': header.variant,
        }
    )


@savers.register(linked=load_oberon)
def save_oberon(fonts, outstream):
    """
    Save font to ETH Project Oberon font file.
    """
    font = ensure_single(fonts)
    font = ensure_levels(font, 2)
    # restrict to ascii
    font = font.label()
    font = font.subset(codepoints=range(256))
    # get ascii runs
    codepoints = sorted(font.get_codepoints())
    ranges = find_ranges(codepoints)
    runs = _RUN.array(len(ranges))(
        *(_RUN(beg=_r.start, end=_r.stop) for _r in ranges)
    )
    # get glyphs in ascii order
    glyphs = tuple(font.get_glyph(_cp) for _cp in codepoints)
    glyph_bytes = [
        _g.flip(adjust_metrics=False).as_bytes(bit_order='little')
        for _g in glyphs
    ]
    boxes = _BOX.array(len(codepoints))(*(
        _BOX(
            dx=_g.advance_width,
            x=_g.left_bearing,
            y=_g.shift_up,
            w=_g.width,
            h=_g.height,
        )
        for _g in glyphs
    ))
    header = _HEADER(
        ident=_FONT_FILE_ID,
        abstraction=0,
        family=font.get_property('oberon.family') or 0,
        # 32, whatever it means, is almost always used
        variant=font.get_property('oberon.variant') or 32,
        height=font.line_height,
        minX=font.ink_bounds.left,
        maxX=font.ink_bounds.right,
        minY=font.ink_bounds.bottom,
        maxY=font.ink_bounds.top,
        NofRuns=len(ranges),
    )
    outstream.write(b''.join((
        bytes(header),
        bytes(runs),
        bytes(boxes),
        *glyph_bytes,
    )))
