"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from contextlib import contextmanager

DEFAULT_FORMAT = 'text'


@contextmanager
def ensure_stream(infile, mode):
    """If argument is a string, open as file."""
    if isinstance(infile, str) or isinstance(infile, bytes):
        instream = open(infile, mode)
    else:
        instream = infile
    with instream:
        yield instream

def ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)


class Font:
    """Glyphs and metadata."""

    _loaders = {}
    _savers = {}

    def __init__(self, glyphs, comments=(), properties=None):
        """Create new font."""
        self._glyphs = glyphs
        self._comments = comments
        self._properties = properties or {}

    @classmethod
    def load(cls, infile, format=None, **kwargs):
        """Load from file."""
        if isinstance(infile, bytes):
            infile = infile.decode('ascii')
        if not format and isinstance(infile, str):
            format = DEFAULT_FORMAT
            try:
                _, format = infile.rsplit('.', 1)
                if format not in cls._loaders:
                    format = DEFAULT_FORMAT
            except ValueError:
                pass
        try:
            loader = cls._loaders[format.lower()]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format))
        return loader(infile, **kwargs)

    def save(self, outfile, format=None, **kwargs):
        """Load from file."""
        if isinstance(outfile, bytes):
            outfile = outfile.decode('ascii')
        if not format and isinstance(outfile, str):
            format = DEFAULT_FORMAT
            try:
                _, format = outfile.rsplit('.', 1)
                if format not in self._savers:
                    format = DEFAULT_FORMAT
            except ValueError:
                pass
        try:
            saver = self._savers[format.lower()]
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))
        return saver(self, outfile, **kwargs)

    @classmethod
    def loads(cls, *formats):
        """Decorator to register font loader."""
        def _loadfunc(fn):
            for format in formats:
                cls._loaders[format.lower()] = fn
            return fn
        return _loadfunc

    @classmethod
    def saves(cls, *formats):
        """Decorator to register font saver."""
        def _savefunc(fn):
            for format in formats:
                cls._savers[format.lower()] = fn
            return fn
        return _savefunc
