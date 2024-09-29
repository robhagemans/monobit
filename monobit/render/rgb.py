"""
monobit.render.rgb - generate rgb shades

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base import RGB


class RGBTable(list):

    def __init__(self, table=()):
        """Set up RGB table."""
        if isinstance(table, str):
            table = table.splitlines()
        super().__init__(RGB.create(_v) for _v in table)

    def __str__(self):
        """Convert RGB table to multiline string."""
        return '\n'.join(str(_v) for _v in iter(self))


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
    if rgb_table is not None and image_mode in ('1', 'L'):
        logging.warning('RGB colour table will be ignored.')
    if image_mode == '1':
        if levels > 2:
            logging.warning('Ink levels will be downsampled from %d to 2', levels)
        inklevels = [0] * (levels//2) + [1] * (levels-levels//2)
        border = 0
    elif image_mode == 'L':
        inklevels = tuple(
            _v * 255 // (levels-1)
            for _v in range(levels)
        )
        border = 0
    elif rgb_table is not None:
        inklevels = rgb_table
    else:
        inklevels = create_gradient(paper=paper, ink=ink, levels=levels)
    return inklevels
