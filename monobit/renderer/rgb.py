"""
monobit.renderer.rgb - generate rgb shades

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base import RGB
from monobit.core.palette import Palette, BLACK, WHITE


def create_image_colours(*, image_mode, rgb_table, levels, paper, ink):
    """Create colour table for given image format."""
    if rgb_table is not None:
        inklevels = [*rgb_table]
        if paper is not None:
            inklevels[0] = RGB(*paper)
        if ink is not None:
            inklevels[-1] = RGB(*ink)
    else:
        if paper is None:
            paper = BLACK
        if ink is None:
            ink = WHITE
        inklevels = Palette.gradient(paper=paper, ink=ink, levels=levels)
    image_mode = image_mode[:4].lower()
    if image_mode in ('grey', 'gray', 'mono'):
        inklevels = inklevels.as_intensity()
        border = 0
    if image_mode == 'mono':
        thresh = max(inklevels) // 2
        inklevels = tuple(int(_int >= thresh) for _int in inklevels)
        border = 0
    return inklevels


def default_colours(
        font,
        paper, ink, border,
        default_paper, default_ink,
        border_match_paper=False, default_border=None
    ):
    """Apply default colours based on input and colour table."""
    # FIXME this logic doesn't make much sense. does this function make sense at all?
    if not font.rgb_table.is_default():
        if ink is None:
            ink = font.rgb_table[-1]
        if paper is None:
            paper = font.rgb_table[0]
    else:
        if ink is None:
            ink = default_ink
        if paper is None:
            paper = default_paper
    if border is None:
        if default_border is None and border_match_paper:
            border = paper
        else:
            border = default_border
    return paper, ink, border
