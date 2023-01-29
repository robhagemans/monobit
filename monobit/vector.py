"""
monobit.vector - stroke font support

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import deque
from functools import cached_property
from itertools import accumulate

from .renderer import Canvas
from .basetypes import Coord, Bounds
from .glyph import Glyph


class StrokePath:
    """Representation of a stroke path."""

    MOVE = 'm'
    LINE = 'l'

    def __init__(self, path):
        """
        Initialise with sequence of moves.
        m {x} {y}  move by x units horizontally (right +) and y vertically (up +)
        l {x} {y}  as `m`, with a line connecting the two points
        """
        if isinstance(path, type(self)):
            self._path = path._path
        else:
            self._path = tuple(path)

    def __str__(self):
        """String representation."""
        return '\n'.join(
            ' '.join(str(_i) for _i in _move) for _move in self._path
        )

    def as_svg(self):
        """SVG path 'd' value"""
        return ' '.join(
            ' '.join(str(_i) for _i in _move) for _move in self._path
        )

    def as_moves(self):
        """Tuple of moves."""
        return tuple(self._path)

    @classmethod
    def from_string(cls, pathstr):
        """Build from string representation."""
        elements = pathstr.split()
        # group in triplets
        args = [iter(elements)] * 3
        # raise an error if the path does not cleanly split
        path = zip(*args, strict=True)
        path = ((_ink, int(_x), int(_y)) for _ink, _x, _y in path)
        return cls(path)

    def flip(self):
        """Flip vertically about path origin."""
        return type(self)((_ink, _x, -_y) for _ink, _x, _y in self._path)

    def mirror(self):
        """Mirror horizontally about path origin."""
        return type(self)((_ink, -_x, _y) for _ink, _x, _y in self._path)

    def shift(self, x, y):
        """Shift path by (x, y)."""
        if not self._path:
            return self
        path = deque(self._path)
        if path[0][0] != self.MOVE:
            path.appendleft((self.MOVE, x, y))
        else:
            path[0] = (self.MOVE, x + path[0][1], y + path[0][2])
        return type(self)(path)

    @cached_property
    def bounds(self):
        """Bounding box of path (not necessarily of ink)."""
        if not self._path:
            return Bounds(0, 0, 0, 0)
        xs = tuple(accumulate(_elem[1] for _elem in self._path))
        ys = tuple(accumulate(_elem[2] for _elem in self._path))
        return Bounds(
            left=min(xs), right=max(xs)+1,
            bottom=min(ys), top=max(ys)+1,
        )

    def draw(self):
        """Draw the path."""
        if not self._path:
            return Canvas.blank(0, 0, 0)
        canvas = Canvas.blank(
            self.bounds.right - self.bounds.left,
            self.bounds.top - self.bounds.bottom,
            fill=0
        )
        x, y = -self.bounds.left, -self.bounds.bottom
        for ink, dx, dy in self._path:
            if ink == self.LINE:
                canvas.draw_line(x, y, x+dx, y+dy)
            x += dx
            y += dy
        return canvas

    def as_glyph(self, advance_width=None, **kwargs):
        """Draw the path and create a Glyph."""
        raster = self.draw()
        if advance_width is None:
            advance_width = self.bounds.right
        return Glyph(
            raster, path=self,
            right_bearing=advance_width-self.bounds.right,
            left_bearing=self.bounds.left,
            shift_up=self.bounds.bottom,
            **kwargs
        )
