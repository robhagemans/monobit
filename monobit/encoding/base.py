"""
monobit.encoding.base - base classes and functions for encoding

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""



class NotFoundError(KeyError):
    """Encoding not found."""


class EncodingName(str):

    def __new__(cls, value=''):
        """Convert value to encoding name."""
        value = normalise_name(str(value))
        return super().__new__(cls, value)


def normalise_name(name=''):
    """Replace encoding name with normalised variant for display."""
    return name.lower().replace('_', '-').replace(' ', '-')



class Encoder:
    """
    Convert between unicode, ordinals and tags.
    Encoder objects act on single-glyph codes only, which may be single- or multi-codepoint.
    They need not encode/decode between full strings and bytes.
    """

    def __init__(self, name):
        """Set encoder name."""
        self.name = name

    def char(self, *labels):
        """Convert codepoint to character, return empty string if missing."""
        raise NotImplementedError

    def codepoint(self, *labels):
        """Convert character to codepoint, return None if missing."""
        raise NotImplementedError

    def __repr__(self):
        """Representation."""
        return f"{type(self).__name__}(name='{self.name}')"
