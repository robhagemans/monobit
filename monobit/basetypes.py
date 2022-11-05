"""
monobit.basetypes - base data types and converters

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import numbers
from collections import namedtuple


class IntTuple(tuple):
    """Tuple of ints with custom str conversion."""
    def __str__(self):
        return ','.join(str(_i) for _i in self)

def tuple_int(tup):
    """Convert NxNx... or N,N,... to tuple."""
    if isinstance(tup, str):
        return IntTuple(int(_s) for _s in tup.replace('x', ',').split(','))
    return IntTuple([*tup])

rgb = tuple_int
pair = tuple_int


def any_int(int_str):
    """Int-like or string in any representation."""
    try:
        # '0xFF' - hex
        # '0o77' - octal
        # '99' - decimal
        return int(int_str, 0)
    except (TypeError, ValueError):
        # '099' - ValueError above, OK as decimal
        # non-string inputs: TypeError, may be OK if int(x) works
        return int(int_str)


def Any(var):
    """Passthrough type."""
    return var



def number(value=0):
    """Convert to int or float."""
    if isinstance(value, str):
        value = float(value)
    if not isinstance(value, numbers.Real):
        raise ValueError("Can't convert `{}` to number.".format(value))
    if value == int(value):
        value = int(value)
    return value


class _VectorMixin:
    """Vector operations on tuple."""

    def __str__(self):
        return ' '.join(f'{_e}' for _e in self)

    def __add__(self, other):
        return type(self)(*(_l + _r for _l, _r in zip(self, other)))

    def __sub__(self, other):
        return type(self)(*(_l - _r for _l, _r in zip(self, other)))

    def __bool__(self):
        return any(self)



class Bounds(_VectorMixin, namedtuple('Bounds', 'left bottom right top')):
    """4-coordinate tuple."""

class Coord(_VectorMixin, namedtuple('Coord', 'x y')):
    """Coordinate tuple."""

    @classmethod
    def create(cls, coord=0):
        if isinstance(coord, Coord):
            return coord
        if isinstance(coord, numbers.Real):
            return cls(coord, coord)
        if isinstance(coord, str):
            splits = coord.split(' ')
            if len(splits) == 1:
                return cls(number(splits[0]), number(splits[0]))
            elif len(splits) == 2:
                return cls(number(splits[0]), number(splits[1]))
        if isinstance(coord, tuple):
            if len(coord) == 2:
                return cls(number(coord[0]), number(coord[1]))
        if not coord:
            return cls(0, 0)
        raise ValueError("Can't convert `{}` to coordinate pair.".format(coord))

