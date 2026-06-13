"""
monobit.renderer.rgb - generate rgb shades

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base import RGB, RGBTable


def create_gradient(paper:RGB, ink:RGB, levels:int):
    """Create equal-stepped RGB gradient from paper to ink."""
    maxlevel = levels - 1
    return RGBTable(
        tuple(
            (_value * _ink + (maxlevel - _value) * _paper) // maxlevel
            for _ink, _paper in zip(ink, paper)
        )
        for _value in range(levels)
    )


def create_image_colours(*, image_mode, rgb_table, levels, paper, ink):
    """Create colour table for given image format."""
    image_mode = image_mode[:4].lower()
    if rgb_table is not None and image_mode in ('mono', 'grey', 'gray'):
        logging.warning('RGB colour table will be ignored.')
    if image_mode == 'mono':
        if levels > 2:
            logging.warning('Ink levels will be downsampled from %d to 2', levels)
        inklevels = [0] * (levels//2) + [1] * (levels-levels//2)
        border = 0
    elif image_mode in ('grey', 'gray'):
        inklevels = tuple(
            _v * 255 // (levels-1)
            for _v in range(levels)
        )
        border = 0
    elif rgb_table is not None:
        inklevels = RGBTable(rgb_table)
        if paper is not None:
            inklevels[0] = RGB(*paper)
        if ink is not None:
            inklevels[-1] = RGB(*ink)
    else:
        if paper is None:
            paper = (0, 0, 0)
        if ink is None:
            ink = (255, 255, 255)
        inklevels = create_gradient(paper=paper, ink=ink, levels=levels)
    return inklevels


def default_colours(
        font,
        paper, ink, border,
        default_paper, default_ink,
        border_match_paper=False, default_border=None
    ):
    """Apply default colours based on input and colour table."""
    if font.rgb_table:
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
