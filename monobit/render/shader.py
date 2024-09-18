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


class RGBShader:

    def __init__(self, rgb_table:RGBTable):
        self.rgb_table = rgb_table

    def get_shade(self, value:int):
        """Get RGB for given index level."""
        return self.rgb_table[value]


class GreyscaleShader:

    def __init__(self, levels:int, paper:RGB, ink:RGB):
        self.levels = levels
        self.paper = paper
        self.ink = ink

    def get_shade(self, value:int):
        """Get RGB for given grey level."""
        maxlevel = self.levels - 1
        shade = tuple(
            (value * _ink + (maxlevel - value) * _paper) // maxlevel
            for _ink, _paper in zip(self.ink, self.paper)
        )
        return shade
