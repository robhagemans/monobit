"""
monobit.vector - stroke font support

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from collections import deque


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
