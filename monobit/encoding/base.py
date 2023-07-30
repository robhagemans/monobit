"""
monobit.encoding.base - base classes and functions for encoding

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""



class NotFoundError(KeyError):
    """Encoding not found."""


class EncodingName(str):

    # replacement patterns for normalisation
    # longest first to avoid partial match
    _patterns = {
        'microsoftcp': 'windows',
        'microsoft': 'windows',
        'msdoscp': 'oem',
        'oemcp': 'oem',
        'msdos': 'oem',
        'ibmcp': 'ibm',
        'apple': 'mac',
        'macos': 'mac',
        'doscp': 'oem',
        'mscp': 'windows',
        'dos': 'oem',
        'pc': 'oem',
        'ms': 'windows',
        # mac-roman also known as x-mac-roman etc.
        'x': '',
    }

    def __new__(cls, value=''):
        """Convert value to encoding name."""
        value = cls._normalise_name(str(value))
        return super().__new__(cls, value)

    def __eq__(self, other):
        """Check if two names match."""
        return self._normalise_for_match() == EncodingName(other)._normalise_for_match()

    def __hash__(self):
        return str.__hash__(self._normalise_for_match())

    @staticmethod
    def _normalise_name(name=''):
        """Replace encoding name with normalised variant for display."""
        return name.lower().replace('_', '-').replace(' ', '-')

    def _normalise_for_match(self):
        """Further normalise names to base form."""
        name = str(self)
        # remove underscores, spaces, dashes and dots
        for char in '-.':
            name = name.replace(char, '')
        # try replacements
        for start, replacement in self._patterns.items():
            if name.startswith(start):
                name = replacement + name[len(start):]
                break
        return name



class Encoder:
    """
    Convert between unicode, ordinals and tags.
    Encoder objects act on single-glyph codes only, which may be single- or multi-codepoint.
    They need not encode/decode between full strings and bytes.
    """

    def __init__(self, name):
        """Set encoder name."""
        self.name = EncodingName(name)

    def char(self, *labels):
        """Convert labels to character, return empty string if missing."""
        raise NotImplementedError

    def codepoint(self, *labels):
        """Convert labels to codepoint, return None if missing."""
        raise NotImplementedError

    def tag(self, *labels):
        """Convert labels to tag, return None if missing."""
        raise NotImplementedError

    def __repr__(self):
        """Representation."""
        return f"{type(self).__name__}(name='{self.name}')"


class EncoderBuilder:
    """Callable returning an Encoder and allowing for lazy composition."""

    def __init__(self, callable):
        self._callable = callable

    def __call__(self):
        return self._callable()

    # delayed operations

    def __or__(self, other):
        """Return encoding overlaid with all characters defined in right-hand side."""
        if isinstance(other, Encoder):
            def delayed_or():
                return self() | other
        else:
            def delayed_or():
                return self() | other()
        return EncoderBuilder(delayed_or)

    def subset(self, codepoint_range):
        """Return encoding only for given range of codepoints."""
        def delayed_subset():
            return self().subset(codepoint_range)
        return EncoderBuilder(delayed_subset)


# registry of charmap/tagmap file format readers
encoding_readers = {}

def register_reader(format, **default_kwargs):
    """Decorator to register charmap reader."""
    def decorator(reader):
        encoding_readers[format] = (reader, default_kwargs)
        return reader
    return decorator
