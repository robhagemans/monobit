"""
monobit.storage.fontformats.raw.hrcg - AppleSoft Toolkit Hi-Res Character Generator

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers
from monobit.base import FileFormatError
from monobit.core import Font, Glyph, Raster
from monobit.storage.utils.limitations import (
    ensure_single, ensure_charcell, make_contiguous
)

from .raw import load_bitmap, save_bitmap


@loaders.register(
    name='hrcg',
    patterns=('*.set',),
)
def load_hrcg(instream):
    """Load a Hi-Res Character Generator font."""
    font = load_bitmap(instream, width=8, height=8, count=96, msb='r', first_codepoint=0x20)
    more_data = instream.read()
    if more_data:
        raise FileFormatError(f'Not a HRCG font: size {768+len(more_data)} != 768')
    font = font.interlace(factor=(2, 1), shift_mask_column=-1, adjust_metrics=False)
    font = font.modify(source_format='hrcg')
    return font


@savers.register(linked=load_hrcg)
def save_hrcg(fonts, outstream):
    """Save a Hi-Res Character Generator font."""
    font = ensure_single(fonts)
    font = ensure_charcell(font, cell_size=(14, 8))
    font = make_contiguous(font, full_range=range(0x20, 0x80), missing='space')
    # split even, odd columns
    even = font.shrink(factor=(2, 1), modulo=(0, 0)).glyphs
    odd = font.shrink(factor=(2, 1), modulo=(1, 0)).glyphs
    # combine to deinterlaced raster
    rasters = tuple(_e.overlay(_o).pixels for _e, _o in zip(even, odd))
    # print(rasters)
    # determine shifts
    matrices = (_g.as_matrix(inklevels=(0, 1)) for _g in odd)
    odd_has_ink = (tuple(sum(_row) > 0 for _row in _mx) for _mx in matrices)
    masks = (Raster.from_vector(_ohi, stride=1, inklevels=(False, True)) for _ohi in odd_has_ink)
    # combine glyphs and masks
    glyphs = tuple(Glyph(Raster.concatenate(_g, _mask)) for _g, _mask in zip(rasters, masks))
    # print(glyphs)
    font = Font(glyphs)
    save_bitmap(outstream, font, msb='right')
