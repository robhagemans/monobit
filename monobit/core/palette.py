"""
monobit.core.palette - RGB or greyscale palette

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import RGB

BLACK = RGB(0, 0, 0)
WHITE = RGB(255, 255, 255)


class Palette(list):

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

    def is_default(self):
        """Palette is the default palette for this number of levels."""
        return self == self.default(len(self))

    @classmethod
    def default(cls, levels):
        """Create equal-stepped RGB gradient from black to white."""
        return cls.gradient(BLACK, WHITE, levels)

    @classmethod
    def gradient(cls, paper, ink, levels):
        """Create equal-stepped RGB or intensity gradient from paper to ink."""
        maxlevel = levels - 1
        return cls(
            tuple(
                (_value * _ink + (maxlevel - _value) * _paper) // maxlevel
                for _ink, _paper in zip(ink, paper)
            )
            for _value in range(levels)
        )

    def as_intensity(self):
        """Return iterable of intensity values for this palette."""
        return tuple(sum(_tup) // len(_tup) for _tup in iter(self))
