"""
monobit.basetypes - base data types and converters

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import numbers
from collections import namedtuple
from functools import partial


def to_int(int_str):
    """Convert from int-like or string in any representation."""
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

    @classmethod
    def create(cls, coord=0):
        coord = to_tuple(coord, length=4)
        return cls(*coord)


class Coord(_VectorMixin, namedtuple('Coord', 'x y')):
    """Coordinate tuple."""

    @classmethod
    def create(cls, coord=0):
        coord = to_tuple(coord, length=2)
        return cls(*coord)


def _str_to_tuple(value):
    """Convert various string representations to tuple."""
    value = value.strip().replace(',', ' ').replace('x', ' ')
    return tuple(number(_s) for _s in value.split())

def to_tuple(value=0, *, length=2):
    if isinstance(value, tuple):
        return value
    if isinstance(value, numbers.Real):
        return (value,) * length
    if isinstance(value, str):
        value = _str_to_tuple(value)
        if len(value) == 1:
            return value * length
        return value
    if not value:
        return (0,) * length
    try:
        return tuple(value)
    except ValueError:
        pass
    raise ValueError(f"Can't convert {value!r} to tuple.")

pair = partial(to_tuple, length=2)
rgb = partial(to_tuple, length=3)
