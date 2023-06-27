"""
monobit.vector - stroke font support

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import deque
from functools import cached_property
from itertools import accumulate
from typing import NamedTuple

from .basetypes import Coord, Bounds
from .raster import Raster


class StrokeMove(NamedTuple):
    """Stroke path element."""
    command: str
    dx: int
    dy: int


class StrokePath:
    """Representation of a stroke path."""

    MOVE = 'm'
    LINE = 'l'

    def __init__(self, path=()):
        """
        Initialise with sequence of moves.
        m {x} {y}  move by x units horizontally (right +) and y vertically (up +)
        l {x} {y}  as `m`, with a line connecting the two points
        """
        if isinstance(path, type(self)):
            self._path = path._path
        elif isinstance(path, str):
            self._path = self.from_string(path)._path
        else:
            self._path = tuple(StrokeMove(*_m) for _m in path)

    def __str__(self):
        """String representation."""
        return '\n'.join(
            ' '.join(str(_i) for _i in _move) for _move in self._path
        )

    def __bool__(self):
        """Path is not empty."""
        return bool(self._path)

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
        #path = zip(*args, strict=True) # python3.10 and above
        path = zip(*args)
        path = (StrokeMove(_ink, int(_x), int(_y)) for _ink, _x, _y in path)
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
            path[0] = StrokeMove(self.MOVE, x + path[0][1], y + path[0][2])
        return type(self)(path)

    @cached_property
    def bounds(self):
        """Bounding box of path (not necessarily of ink)."""
        if not self._path:
            return Bounds(0, 0, 0, 0)
        xs = tuple(accumulate(_elem.dx for _elem in self._path))
        ys = tuple(accumulate(_elem.dy for _elem in self._path))
        return Bounds(
            left=min(xs), right=max(xs)+1,
            bottom=min(ys), top=max(ys)+1,
        )

    def draw(self):
        """Draw the path."""
        if not self._path:
            return Canvas.blank(0, 0)
        canvas = Canvas.blank(
            self.bounds.right - self.bounds.left,
            self.bounds.top - self.bounds.bottom,
        )
        x, y = -self.bounds.left, -self.bounds.bottom
        for ink, dx, dy in self._path:
            if ink == self.LINE:
                canvas.draw_line(x, y, x+dx, y+dy)
            x += dx
            y += dy
        return Raster(canvas)


class Canvas(Raster):
    """Mutable raster for line draw operations."""

    _inner = list
    _outer = list
    _0 = 0
    _1 = 1
    _itemtype = int

    @classmethod
    def blank(cls, width, height):
        """Create a canvas in background colour."""
        canvas = [[cls._0]*width for _ in range(height)]
        # setting 0 and 1 will make Raster init leave the input alone
        return cls(canvas, _0=cls._0, _1=cls._1)

    def draw_pixel(self, x, y):
        """Draw a pixel."""
        self._pixels[self.height - y - 1][x] = self._1

    def draw_line(self, x0, y0, x1, y1):
        """Draw a line between the given points."""
        # Bresenham algorithm
        dx, dy = abs(x1-x0), abs(y1-y0)
        steep = dy > dx
        if steep:
            x0, y0, x1, y1 = y0, x0, y1, x1
            dx, dy = dy, dx
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1
        line_error = dx // 2
        x, y = x0, y0
        for x in range(x0, x1+sx, sx):
            if steep:
                self.draw_pixel(y, x)
            else:
                self.draw_pixel(x, y)
            line_error -= dy
            if line_error < 0:
                y += sy
                line_error += dx
