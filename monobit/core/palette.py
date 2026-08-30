"""
monobit.core.palette - RGB or greyscale palette

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import RGB

BLACK = RGB(0, 0, 0)
WHITE = RGB(255, 255, 255)


def light_defaults(paper=None, ink=None):
    if paper is None:
        paper = WHITE
    if ink is None:
        ink = BLACK
    return paper, ink


def dark_defaults(paper=None, ink=None):
    if paper is None:
        paper = BLACK
    if ink is None:
        ink = WHITE
    return paper, ink


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

    def as_greyscale(self, paper:int=None, ink:int=None):
        """Return intensities between specified values."""
        intensities = self.as_intensity()
        max_int = 255 # max(intensities)
        if paper is None:
            paper = 0
        if ink is None:
            ink = 255
        return tuple(
            (ink*_int + paper*(max_int-_int)) // max_int
            for _int in intensities
        )

    def as_rgb(self, paper:RGB=None, ink:RGB=None, override_colours:bool=False):
        """Return RGB palette."""
        if self.is_greyscale():
            intensities = self.as_intensity()
            max_int = 255 # max(intensities)
            paper, ink = dark_defaults(paper, ink)
            return tuple(
                RGB(*(
                    (_i*_int + _p*(max_int-_int)) // max_int
                    for _p, _i in zip(paper, ink)
                ))
                for _int in intensities
            )
        else:
            inklevels = [*self]
            if paper is not None and override_colours:
                inklevels[0] = paper
            if ink is not None and override_colours:
                inklevels[-1] = ink
            return inklevels

    def as_mono(self, paper=None, ink=None, threshold=0.5):
        """Map to monochrome."""
        if paper is None:
            paper = 0
        if ink is None:
            ink = 1
        intensities = self.as_intensity()
        thresh = int(max(intensities) * threshold)
        is_above = (_int >= thresh for _int in intensities)
        return tuple(ink if _int else paper for _int in is_above)
