"""
monobit.core.palette - RGB or greyscale palette

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from operator import itemgetter

from monobit.base import RGB, RGBA


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


class Palette:

    def __init__(self, table=()):
        """Set up palette."""
        if isinstance(table, type(self)):
            self._rgb = table._rgb
            self._alpha = table._alpha
            self._levels = table._levels
            return
        table = tuple(table)
        self._levels = len(table)
        if not table:
            self._alpha = ()
            self._rgb = None
        elif isinstance(table[0], int):
            self._alpha = table
            self._rgb = None
        elif len(table[0]) == 3:
            self._alpha = None
            self._rgb = tuple(RGB.create(_v) for _v in table)
        elif len(table[0]) == 4:
            self._rgb = tuple(RGB.create(_v[:3]) for _v in table)
            self._alpha = tuple(_v[3] for _v in table)
            if len(set(self._rgb)) <= 1:
                # all the same colour -> intensity palette
                self._rgb = None
            elif len(set(self._alpha)) <= 1:
                # all alpha the same -> no alpha
                self._alpha = None
        else:
            raise ValueError('Palette must be intensity, rgb or rgba')
        if self._alpha is None and all(_c.r == _c.g == _c.b for _c in self._rgb):
            self._alpha = tuple(_c[0] for _c in table)
            self._rgb = None

    def __len__(self):
        """Number of levels."""
        return self._levels

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self._levels == other._levels
            and self._alpha == other._alpha
            and self._rgb == other._rgb
        )

    def __hash__(self):
        return hash((self._levels, self._rgb, self._alpha))

    def __repr__(self):
        if self._alpha is None:
            table = self._rgb
        elif self._rgb is None:
            table = self._alpha
        else:
            table = self.as_rgba()
        return f'{type(self).__name__}({list(table)})'

    def __str__(self):
        """Convert palette to multiline string."""
        if self._rgb is None:
            return '\n'.join(f'{_a:02X}' for _a in self._alpha)
        if self._alpha is None:
            table = self._rgb
        else:
            table = self.as_rgba()
        return '\n'.join(''.join(f'{_v:02X}' for _v in _c) for _c in table)

    def is_greyscale(self):
        """This palette is a grey scale."""
        return self._rgb is None

    def has_alpha(self):
        """This palette has an alpha channel."""
        return self._alpha is not None

    def is_default(self):
        """This palette is the default palette for this number of levels."""
        return self == self.default(self._levels)

    @classmethod
    def default(cls, levels):
        """Create equal-stepped intensity gradient."""
        maxlevel = levels - 1
        return cls(_value * 255 // maxlevel for _value in range(levels))

    def as_intensity(self):
        """Return iterable of intensity values for this palette."""
        if self._rgb is None:
            return self._alpha
        rgb_int = (sum(_tup) // len(_tup) for _tup in self._rgb)
        if self._alpha is None:
            return tuple(rgb_int)
        return tuple(_a * _i // 255 for _a, _i in zip(self._alpha, rgb_int))

    def as_rgb(self, paper:RGB=None, ink:RGB=None):
        """Return RGB palette with substituted ink and paper values."""
        if self._rgb is None:
            paper, ink = dark_defaults(paper, ink)
            return tuple(
                RGB(*(
                    (_i*_int + _p*(255-_int)) // 255
                    for _p, _i in zip(paper, ink)
                ))
                for _int in self._alpha
            )
        rgb = [*self._rgb]
        if self._alpha is not None:
            # premultiply alpha
            rgb = tuple(
                tuple(_i * _a // 255 for _i in _rgb)
                for _rgb, _a in zip(rgb, self._alpha)
            )
        if paper is not None:
            rgb[0] = paper
        if ink is not None:
            rgb[-1] = ink
        return tuple(RGB(*_v) for _v in rgb)

    def as_rgba(self, ink:RGB=None):
        """Return RGBA palette with substituted RGB ink value."""
        if self._rgb is None:
            ink = ink or WHITE
            return tuple(RGBA(*ink, _int) for _int in self._alpha)
        elif self._alpha is None:
            # set alpha to fully opaque, except background
            return (RGBA(*self._rgb[0], 0,),) + tuple(
                RGBA(*_c, 255) for _c in self._rgb[1:]
            )
        else:
            rgb = [*self._rgb]
            if ink is not None:
                rgb[-1] = ink
            return tuple(RGBA(*_v, _a) for _v, _a in zip(rgb, self._alpha))

    def as_mono(self, threshold=0.5):
        """Map to monochrome."""
        intensities = self.as_intensity()
        thresh = int(max(intensities) * threshold)
        return tuple(int(_int >= thresh) for _int in intensities)

    def map_to(self, other, approximate=False):
        """Return closest index in other palette for each entry."""
        other = type(self)(other)
        distances = tuple(
            tuple(
                sum(abs(_sv - _ov) for _sv, _ov in zip(_s, _o))
                for _o in other.as_rgb()
            )
            for _s in self.as_rgb()
        )
        if any(min(_d) for (_d) in distances):
            msg = 'Could not map palettes exactly.'
            if not approximate:
                raise ValueError(msg)
            else:
                logging.warning(msg)
        mapped_index = tuple(
            min(enumerate(_dist), key=itemgetter(1))[0]
            for _dist in distances
        )
        return mapped_index
