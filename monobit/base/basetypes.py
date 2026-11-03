"""
monobit.base.basetypes - base data types and converters

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from collections import namedtuple
from functools import partial
from typing import Any
from numbers import Real


# sentinel object
# used by scriptable functions to indicate that a parameter was not specified
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
    """Vector operations on namedtuple."""

    def __add__(self, other):
        return type(self)(*(_l + _r for _l, _r in zip(self, other)))

    def __sub__(self, other):
        return type(self)(*(_l - _r for _l, _r in zip(self, other)))

    def __bool__(self):
        return any(self)


class _CoordMixin:
    """Coordinate creation/string representation."""

    _default_separator = ' '

    @classmethod
    def create(cls, coord=0):
        coord = to_tuple(coord, length=len(cls._fields))
        return cls(*coord)

    def __str__(self):
        return self._default_separator.join(f'{_e}' for _e in self)


class Bounds(
        _VectorMixin, _CoordMixin,
        namedtuple('Bounds', 'left bottom right top')
    ):
    _default_separator = ' '


class Coord(
        _VectorMixin, _CoordMixin,
        namedtuple('Coord', 'x y')
    ):
    _default_separator = 'x'





class Colour(_VectorMixin):
    """Base class for RGB or RGBA tuples; mixin alongside namedtuple."""

    def __bool__(self):
        return True

    def __str__(self):
        return ''.join(f'{_elem:02X}' for _elem in self)


class RGB(Colour, namedtuple('RGB', 'r g b')):
    """Red-green-blue tuple."""


class RGBA(Colour, namedtuple('RGBA', 'r g b a')):
    """Red-green-blue-alpha tuple."""


def grouper(value, grouplength):
    """Split into groups of given length. Recipe from itertools docs."""
    return zip(*([iter(value)] * grouplength))


def to_colour(value):
    """Convert scalar, tuple or string to RGB or RGBA value."""
    if isinstance(value, tuple):
        valuetuple = tuple
    elif isinstance(value, str):
        groups = tuple(''.join(_g) for _g in grouper(value, 2))
        valuetuple = tuple(int(_g, 16) for _g in groups)
    else:
        valuetuple = value,
    if len(valuetuple) == 4:
        return RGBA(*valuetuple)
    elif len(valuetuple) == 3:
        return RGB(*valuetuple)
    elif len(valuetuple) == 1:
        return RGB(*(valuetuple*3))
    raise ValueError(f'Unknown colour specification {value}')



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
    Colour: to_colour,
}
