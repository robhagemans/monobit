"""
monobit.label - yaff representation of labels

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string
from typing import NamedTuple


def strip_matching(from_str, char):
    """Strip a char from either side of the string if it occurs on both."""
    if not char:
        return from_str
    clen = len(char)
    if from_str.startswith(char) and from_str.endswith(char):
        return from_str[clen:-clen]
    return from_str


def label(value=''):
    """Convert to codepoint/unicode/tag label as appropriate."""
    if isinstance(value, Label):
        return value
    if not isinstance(value, str):
        # only Codepoint can have non-str argument
        return Codepoint(value)
    try:
        return Codepoint.from_str(value)
    except ValueError:
        pass
    # check for unicode identifier
    try:
        return Char.from_str(value)
    except ValueError:
        pass
    return Tag.from_str(value)


# pylint: disable=no-member
class Label:
    """Label base class."""


    def __init__(self, value=None):
        """Label base class should not be instantiated."""
        raise ValueError('Cannot create untyped label.')

    @classmethod
    def from_str(cls, value):
        """Create label from string representation."""
        return cls(value)

    def indexer(self):
        """Keyword arguments for character-based functions."""
        return {}


    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return self.value == other.value

    def __bool__(self):
        return bool(self.value)

    def __len__(self):
        return len(self.value)

    def __iter__(self):
        return iter(self.value)


class Tag(Label):
    """Tag label."""

    value: str

    def __init__(self, value):
        """Construct tag object."""
        if isinstance(value, Tag):
            self.value = value.value
            return
        if Tag is None:
            tag = ''
        if not isinstance(value, str):
            raise ValueError(
                f'Cannot convert value {repr(value)} of type {type(value)} to tag.'
            )
        # remove leading and trailing whitespace
        value = value.strip()
        # strip matching double quotes - this allows to set a label starting with a digit by quoting it
        value = strip_matching(value, '"')
        self.value = value

    def __repr__(self):
        """Represent tag."""
        return f"{type(self).__name__}('{self.value}')"

    def __str__(self):
        """Convert tag to str."""
        # quote otherwise ambiguous/illegal tags
        if (
                self.value.lower().startswith('u+')
                or not (self.value[:1].isalpha() or self.value[:1] in '_-."')
                or (self.value.startswith('"') and self.value.endswith('"'))
                or (self.value.startswith("'") and self.value.endswith("'"))
                # one-character tags - we want to consider representing ascii chars this way
                # longer chars get single quotes
                or len(self.value) == 1
            ):
            return f'"{self.value}"'
        return self.value

    def indexer(self):
        """Keyword arguments for get_index."""
        return {'tag': self.value}

    def __hash__(self):
        # make sure tag and Char don't collide
        return hash((type(self), self.value))

    def __eq__(self, other):
        return type(self) == type(other) and self.value == other.value


class Codepoint(Label):
    """Codepoint sequence label."""

    value: tuple

    def __init__(self, value):
        """Convert to codepoint label if possible."""
        if isinstance(value, Codepoint):
            self.value = value.value
            return
        if isinstance(value, int):
            value = (value,)
        if value is None:
            value = ()
        # int.from_bytes? need byte width e.g. utf-32
        self.value = tuple(value)
        if not all(isinstance(_elem, int) for _elem in self.value):
            raise self._value_error(value)

    def __repr__(self):
        """Represent codepoint."""
        cpstr = str(self)
        if len(self.value) != 1:
            cpstr = f'({cpstr})'
        return f"{type(self).__name__}({cpstr})"

    def __str__(self):
        """Convert codepoint label to str."""
        return ', '.join(
            f'0x{_elem:02x}'
            for _elem in self.value
        )

    def indexer(self):
        """Keyword arguments for get_index."""
        return {'codepoint': self.value}

    @classmethod
    def from_str(cls, value):
        """Convert str to codepoint label if possible."""
        if not isinstance(value, str):
            raise cls._value_error(value)
        # handle composite labels
        # codepoint sequences (MBCS) "0xf5,0x02" etc.
        elements = value.split(',')
        try:
            key = [cls._convert_element(_elem) for _elem in elements]
        except ValueError:
            raise cls._value_error(value) from None
        return cls(key)

    @staticmethod
    def _convert_element(value):
        """Convert codepoint label element to int if possible."""
        try:
            # check for anything convertible to int in Python notation (12, 0xff, 0o777, etc.)
            return int(value, 0)
        except ValueError:
            # also accept decimals with leading zeros
            # raises ValueError if not possible
            return int(value.lstrip('0'))

    @staticmethod
    def _value_error(value):
        """Create a ValueError."""
        return ValueError(
            f'Cannot convert value {repr(value)} of type {type(value)} to codepoint label.'
        )


class Char(Label):
    """Unicode label."""

    value: str

    def __init__(self, value):
        """Convert char or char sequence to unicode label."""
        if isinstance(value, Char):
            self.value = value.value
            return
        if value is None:
            value = ''
        try:
            value = ''.join(value)
        except TypeError:
            raise self._value_error(value) from None
        # Char('x') just holds 'x'
        self.value = value

    def __repr__(self):
        """Represent character label."""
        return f"{type(self).__name__}({ascii(self.value)})"

    def __str__(self):
        """Convert to unicode label str."""
        return ', '.join(
            f'u+{ord(_uc):04x}'
            for _uc in self.value
        )

    def indexer(self):
        """Keyword arguments for get_index."""
        return {'char': self.value}

    @classmethod
    def from_str(cls, value):
        """Convert u+XXXX string to unicode label. May be empty, representing no glyph."""
        if not isinstance(value, str):
            raise cls._value_error(value)
        # codepoint sequences
        elements = value.split(',')
        try:
            chars = [cls._convert_element(_elem) for _elem in elements if _elem]
        except ValueError:
            raise cls._value_error(value) from None
        # convert sequence of chars to str
        return cls(chars)

    @staticmethod
    def _convert_element(element):
        """Convert unicode label element to char if possible."""
        element = element.lower()
        if not element.startswith('u+'):
            raise ValueError(element)
        # convert to sequence of chars
        # this will raise ValueError if not possible
        cp_ord = int(element.strip()[2:], 16)
        return chr(cp_ord)

    @staticmethod
    def _value_error(value):
        """Create a ValueError."""
        return ValueError(
            f'Cannot convert value {repr(value)} of type {type(value)} to unicode label.'
        )
