"""
monobit.core.palette - RGB or greyscale palette

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

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

    def is_greyscale(self):
        """RGB/RGBA colourset is a grey scale."""
        # ignore transparency attribute if it exists
        return all(_c.r == _c.g == _c.b for _c in iter(self))


def create_gradient(paper, ink, levels):
    """Create equal-stepped RGB or intensity gradient from paper to ink."""
    maxlevel = levels - 1
    return RGBTable(
        tuple(
            (_value * _ink + (maxlevel - _value) * _paper) // maxlevel
            for _ink, _paper in zip(ink, paper)
        )
        for _value in range(levels)
    )
