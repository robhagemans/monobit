"""
monobit.label - yaff representation of labels

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string


def label(value=''):
    """Convert to codepoint/unicode/tag label as appropriate."""
    # check for codepoint (anything convertible to int)
    try:
        return CodepointLabel(value)
    except ValueError:
        pass
    # check for unicode identifier
    try:
        return UnicodeLabel(value)
    except ValueError:
        pass
    return TagLabel(value)


class TagLabel:
    """Tag label."""

    def __init__(self, value):
        """Construct tag object."""
        if isinstance(value, TagLabel):
            self._tag = value._tag
            return
        if not isinstance(value, str):
            raise ValueError(
                f'Cannot convert value {repr(value)} of type {type(value)} to tag.'
            )
        # remove leading and trailing whitespace
        value = value.strip()
        self._tag = value

    def __repr__(self):
        """Convert tag to str."""
        return self._tag

    def kwargs(self):
        """Keyword arguments for character-based functions."""
        return {'tag': self._tag}


class CodepointLabel:
    """Codepoint sequence label."""

    def __init__(self, value):
        """Convert to codepoint label if possible."""
        if isinstance(value, CodepointLabel):
            self._key = value._key
            return
        # handle composite labels
        # codepoint sequences (MBCS) "0xf5,0x02" etc.
        if isinstance(value, str):
            elements = value.split(',')
        elif isinstance(value, (tuple, list)):
            elements = value
        else:
            elements = [value]
        try:
            self._key = tuple(self._convert_element(_elem) for _elem in elements)
        except ValueError as e:
            raise self._value_error(value) from e

    @staticmethod
    def _value_error(value):
        """Create a ValueError."""
        return ValueError(
            f'Cannot convert value {repr(value)} of type {type(value)} to codepoint label.'
        )

    def _convert_element(self, value):
        """Convert codepoint label element to int if possible."""
        if isinstance(value, (int, float)) and value == int(value):
            return int(value)
        if not isinstance(value, str):
            raise self._value_error(value)
        # must start with a number to be a codepoint
        if not value or not value[0] in string.digits:
            raise self._value_error(value)
        try:
            # check for anything convertible to int in Python notation (12, 0xff, 0o777, etc.)
            return int(value, 0)
        except ValueError:
            pass
        # also accept decimals with leading zeros
        # raises ValueError if not possible
        return int(value.lstrip('0'))

    def __repr__(self):
        """Convert codepoint label to str."""
        return ','.join(
            f'0x{_elem:02x}'
            for _elem in self._key
        )

    def kwargs(self):
        """Keyword arguments for character-based functions."""
        return {'key': self._key}

    def to_codepoint(self):
        """Convert to codepoint sequence."""
        return self._key

    @classmethod
    def from_codepoint(cls, value):
        """Convert codepoint sequence str to label."""
        label = cls(())
        if not all(isinstance(_i, int) for _i in value):
            raise cls._value_error(value)
        label._key = tuple(value)
        return label


class UnicodeLabel:
    """Unicode label."""

    def __init__(self, value):
        """Convert u+XXXX string to unicode label. May be empty, representing no glyph."""
        if isinstance(value, UnicodeLabel):
            self._key = value._key
            return
        if not isinstance(value, str):
            raise self._value_error(value)
        if not value:
            self._key = ''
        # normalise
        elements = value.split(',')
        try:
            chars = [self._convert_element(_elem) for _elem in elements if _elem]
        except ValueError as e:
            raise self._value_error(value) from e
        # convert sequence of chars to str
        self._key = ''.join(chars)

    def _convert_element(self, element):
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

    def __repr__(self):
        """Convert to unicode label str."""
        return ','.join(
            f'u+{ord(_uc):04x}'
            for _uc in self._key
        )

    def kwargs(self):
        """Keyword arguments for character-based functions."""
        return {'key': self._key}

    def to_char(self):
        """Convert to character sequence str."""
        return self._key

    @classmethod
    def from_char(cls, value):
        """Convert character sequence str to unicode label."""
        label = cls('')
        if not isinstance(value, str):
            raise cls._value_error(value)
        label._key = value
        return label
