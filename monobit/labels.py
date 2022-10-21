"""
monobit.label - yaff representation of labels

(c) 2020--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from string import ascii_letters, digits
from binascii import hexlify

from .binary import ceildiv, int_to_bytes
from .scripting import any_int


def is_enclosed(from_str, char):
    """Check if a char occurs on both sides of a string."""
    if not char:
        return True
    return len(from_str) >= 2*len(char) and from_str.startswith(char) and from_str.endswith(char)

def strip_matching(from_str, char, allow_no_match=True):
    """Strip a char from either side of the string if it occurs on both."""
    if not char:
        return from_str
    if is_enclosed(from_str, char):
        clen = len(char)
        return from_str[clen:-clen]
    elif not allow_no_match:
        raise ValueError(f'No matching delimiters `{char}` found in string `{from_str}`.')
    return from_str


##############################################################################
# label types

class Label:
    """Label."""


def to_label(value):
    """Convert to codepoint/unicode/tag label from yaff file."""
    if isinstance(value, Label):
        return value
    if not isinstance(value, str):
        # only Codepoint can have non-str argument
        return Codepoint(value)
    # remove leading and trailing whitespace
    value = value.strip()
    if not value:
        return Char()
    # protect commas, pluses etc. if enclosed
    if is_enclosed(value, '"'):
        # strip matching double quotes - this allows to set a label starting with a digit by quoting it
        value = strip_matching(value, '"')
        return Tag(value)
    if is_enclosed(value, "'"):
        value = strip_matching(value, "'")
        return Char(value)
    # codepoints start with an ascii digit
    try:
        return Codepoint(value)
    except ValueError:
        pass
    # length-one -> always a character
    if len(value) == 1:
        return Char(value)
    # unquoted non-ascii -> always a character
    # note that this includes non-printables such as controls but these should not be used.
    if any(ord(_c) > 0x7f for _c in value):
        return Char(value)
    # deal with other options such as single-quoted, u+codepoint and sequences
    try:
        elements = value.split(',')
        return Char(''.join(
            _convert_char_element(_elem)
            for _elem in elements if _elem
        ))
    except ValueError:
        pass
    return Tag(value)

def _convert_char_element(element):
    """Convert character label element to char if possible."""
    # string delimited by single quotes denotes a character or sequence
    try:
        element = strip_matching(element, "'", allow_no_match=False)
    except ValueError:
        pass
    else:
        return element
    # not a delimited char
    element = element.lower()
    if not element.startswith('u+'):
        raise ValueError(element)
    # convert to sequence of chars
    # this will raise ValueError if not possible
    cp_ord = int(element.strip()[2:], 16)
    return chr(cp_ord)


##############################################################################
# character labels

class Char(str, Label):
    """Character label."""

    def __new__(cls, value=''):
        """Convert char or char sequence to char label."""
        if isinstance(value, Char):
            # we don't want the redefined str() to be called on __new__ below
            value = super().__str__(value)
        elif value is None:
            value = ''
        elif not isinstance(value, str):
            raise ValueError(
                f'Can only convert `str` to character label, not `{type(value)}`.'
            )
        return super().__new__(cls, value)

    def __repr__(self):
        """Represent label."""
        return f"{type(self).__name__}({super().__repr__()})"

    def __str__(self):
        """Convert to unicode label str for yaff."""
        return ', '.join(
            f'u+{ord(_uc):04x}'
            for _uc in self
        )

    @property
    def value(self):
        """Get our str contents without calling __str__."""
        return ''.join(self)


##############################################################################
# codepoints

class Codepoint(bytes, Label):
    """Codepoint label."""

    def __new__(cls, value=b''):
        """Convert to codepoint label if possible."""
        if isinstance(value, Codepoint) or isinstance(value, bytes):
            pass
        elif value is None:
            value = b''
        elif isinstance(value, int):
            value = int_to_bytes(value)
        else:
            if isinstance(value, str):
                # handle composite labels
                # codepoint sequences (MBCS) "0xf5,0x02" etc.
                value = value.split(',')
            # deal with other iterables, e.g. bytes, tuple
            try:
                value = b''.join(int_to_bytes(any_int(_i)) for _i in value)
            except (TypeError, OverflowError):
                raise ValueError(
                    f'Cannot convert value {repr(value)} of type `{type(value)}` to codepoint label.'
                ) from None
        if len(value) > 1:
            value = value.lstrip(b'\0')
        return super().__new__(cls, value)

    def __repr__(self):
        """Represent label."""
        return f"{type(self).__name__}({super().__repr__()})"

    def __str__(self):
        """Convert codepoint label to str."""
        return '0x' + hexlify(self).decode('ascii')


##############################################################################
# tags

class Tag(Label):
    """Tag label."""

    def __init__(self, value=''):
        """Construct tag object."""
        if isinstance(value, Tag):
            self._value = value.value
            return
        if value is None:
            value = ''
        if not isinstance(value, str):
            raise ValueError(
                f'Cannot convert value {repr(value)} of type {type(value)} to tag.'
            )
        self._value = value


    def __repr__(self):
        """Represent label."""
        return f"{type(self).__name__}({repr(self._value)})"

    def __str__(self):
        """Convert tag to str."""
        # quote otherwise ambiguous/illegal tags
        # in particular, we need to quote 0x u+ ' ", non-ascii, and single chars
        if (
                len(self._value) < 2
                or not (self._value[0] in ascii_letters)
                or any(
                    _c not in ascii_letters + digits + '_-.'
                    for _c in self._value
                )
            ):
            return f'"{self._value}"'
        return self._value

    def __hash__(self):
        """Allow use as dictionary key."""
        # make sure tag and Char don't collide
        return hash((type(self), self._value))

    def __eq__(self, other):
        """Allow use as dictionary key."""
        return type(self) == type(other) and self._value == other.value

    def __bool__(self):
        """Check if tag is non-empty."""
        return bool(self._value)

    @property
    def value(self):
        """Tag contents as str."""
        # pylint: disable=no-member
        return self._value

