"""
monobit.base.basetypes - base data types and converters

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from collections import namedtuple
from functools import partial
from typing import Any
from numbers import Real


# sentinel object
NOT_SET = ...


class FileFormatError(Exception):
    """Incorrect file format."""

class UnsupportedError(Exception):
    """Unsupported file format variant."""



class blockstr(str):
    """str that is shown as block text in interactive session."""
    def __repr__(self):
        return f'"""\\\n{self}"""'


def passthrough(var):
    """Passthrough type."""
    return var

def to_int(int_str):
    """Convert from int-like or string in any representation."""
    if isinstance(int_str, int):
        return int_str
    if isinstance(int_str, str) and any(ord(_c)>127 for _c in int_str):
        # avoid unintentiaonally decoding non-ascii numerals (Python does this)
        raise ValueError(
            f"Non-ASCII '{int_str}' "
            "is not a valid string representation for a codepoint."
        )
    try:
        # '0xFF' - hex
        # '0o77' - octal
        # '99' - decimal
        return int(int_str, 0)
    except (TypeError, ValueError):
        # '099' - ValueError above, OK as decimal
        # non-string inputs: TypeError, may be OK if int(x) works
        # int() will raise TypeError or ValueError as needed
        return int(int_str)

def to_number(value=0):
    """Convert to int or float."""
    if isinstance(value, str):
        value = float(value)
    if not isinstance(value, Real):
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

    def __str__(self):
        return 'x'.join(str(_x) for _x in self)

    @classmethod
    def create(cls, coord=0):
        coord = to_tuple(coord, length=2)
        return cls(*coord)


class RGB(_VectorMixin, namedtuple('RGB', 'r g b')):
    """Coordinate tuple."""

    @classmethod
    def create(cls, coord=0):
        coord = to_tuple(coord, length=3)
        return cls(*coord)


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




def _str_to_tuple(value):
    """Convert various string representations to tuple."""
    value = value.strip().replace(',', ' ').replace('x', ' ')
    return tuple(to_number(_s) for _s in value.split())

def to_tuple(value=0, *, length=2):
    if isinstance(value, tuple):
        return tuple(to_int(_i) for _i in value)
    if isinstance(value, Real):
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


# type converters
CONVERTERS = {
    int: to_int,
    float: to_number,
    Real: to_number,
    Any: passthrough,
    Coord: Coord.create,
    Bounds: Bounds.create,
    RGB: RGB.create,
}
