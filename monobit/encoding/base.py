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
