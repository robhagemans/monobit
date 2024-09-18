"""
monobit.render.shader - generate rgb shades

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base import RGB


###################################################################################################

class RGBTable(list):

    def __init__(self, table=()):
        """Set up RGB table."""
        if isinstance(table, str):
            table = (
                _row
                for _row in table.splitlines()
            )
        table = tuple(RGB.create(_v) for _v in table)
        super().__init__(table)

    def __str__(self):
        """Convert RGB table to multiline string."""
        return '\n'.join(str(_v) for _v in iter(self))


###################################################################################################

def get_greyscale_shade(value, levels, paper, ink):
    """Get block at given grey level."""
    maxlevel = levels - 1
    shade = tuple(
        (value * _ink + (maxlevel - value) * _paper) // maxlevel
        for _ink, _paper in zip(ink, paper)
    )
    return shade
