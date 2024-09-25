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


class TableShader:

    def __init__(self, rgb_table:RGBTable):
        self._rgb_table = rgb_table
        self._levels = len(rgb_table)

    def get_shade(self, value:int, paper:RGB, ink:RGB):
        """Get RGB for given index level."""
        if value == 0 and paper is not None:
            return paper
        if value == self._levels - 1 and ink is not None:
            return ink
        return self._rgb_table[value]


class GradientShader:

    def __init__(self, levels:int):
        self._levels = levels

    def get_shade(self, value:int, paper:RGB, ink:RGB):
        """Get RGB for given grey level."""
        maxlevel = self._levels - 1
        shade = tuple(
            (value * _ink + (maxlevel - value) * _paper) // maxlevel
            for _ink, _paper in zip(ink, paper)
        )
        return shade
