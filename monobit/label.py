"""
monobit.label - glyph labels

(c) 2020 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata

class Label:
    """Glyph label."""

    def __init__(self, value=''):
        """Convert to int/unicode label as appropriate."""
        if isinstance(value, Label):
            self._value = value._value
            return
        if isinstance(value, (int, float)):
            self._value = int(value)
            return
        try:
            # check for ordinal (anything convertible to int)
            self._value = int(value, 0)
            return
        except ValueError:
            pass
        try:
            # accept decimals with leading zeros
            self._value = int(value.lstrip('0'))
            return
        except ValueError:
            pass
        value = value.strip()
        # see if it counts as unicode label
        if value.lower().startswith('u+'):
            try:
                [int(_elem.strip()[2:], 16) for _elem in value.split(',')]
            except ValueError as e:
                raise ValueError("'{}' is not a valid unicode label.".format(value)) from e
        # 'namespace' labels with a dot are not converted to lowercase
        if '.' in value:
            self._value = value
        else:
            self._value = value.lower()

    @classmethod
    def from_unicode(cls, unicode):
        """Convert ordinal to unicode label."""
        return ','.join(
            'u+{:04x}'.format(ord(_uc))
            for _uc in unicode
        )

    def __int__(self):
        """Convert to int if ordinal."""
        if self.is_ordinal:
            return self._value
        raise TypeError("Label is not an ordinal.")

    def __repr__(self):
        """Convert label to str."""
        if self.is_ordinal:
            return '0x{:02x}'.format(self._value)
        return self._value

    def __eq__(self, other):
        try:
            return self._value == other._value
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self._value)

    @property
    def is_unicode(self):
        return isinstance(self._value, str) and self._value.startswith('u+')

    @property
    def is_ordinal(self):
        return isinstance(self._value, int)

    @property
    def unicode(self):
        if self.is_unicode:
            return ''.join(chr(int(_cp.strip()[2:], 16)) for _cp in self._value.split(',') if _cp)
        return ''

    @property
    def unicode_name(self):
        if self.is_unicode:
            try:
                return ', '.join(unicodedata.name(_cp) for _cp in self.unicode)
            except ValueError:
                pass
        return ''
