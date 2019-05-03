"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
from contextlib import contextmanager
from functools import partial

from . import glyph

DEFAULT_FORMAT = 'text'
VERSION = '0.2'


@contextmanager
def ensure_stream(infile, mode, encoding=None):
    """
    If argument is a string, open as file.
    Mode should be 'w' or 'r'. For binary, use encoding=None
    """
    if not infile:
        if mode.startswith('w'):
            instream = sys.stdout.buffer
        else:
            instream = sys.stdin.buffer
        # we take encoding == None to mean binary
        if encoding:
            instream = io.TextIOWrapper(instream, encoding=encoding)
    elif isinstance(infile, (str, bytes)):
        if encoding:
            instream = open(infile, mode, encoding=encoding)
        else:
            instream = open(infile, mode + 'b')
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
    _encodings = {}

    def __init__(self, glyphs, comments=(), properties=None):
        """Create new font."""
        self._glyphs = glyphs
        self._comments = comments
        self._properties = properties or {}


    ##########################################################################

    @classmethod
    def load(cls, infile:str, format:str='', **kwargs):
        """Load from file."""
        if isinstance(infile, bytes):
            infile = infile.decode('ascii')
        if not format:
            format = DEFAULT_FORMAT
            # if filename given, try to use it to infer format
            if isinstance(infile, str):
                try:
                    _, format = infile.rsplit('.', 1)
                except ValueError:
                    pass
        format = format.lower()
        try:
            loader = cls._loaders[format]
            encoding = cls._encodings[format]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format))
        with ensure_stream(infile, 'r', encoding=encoding) as instream:
            return loader(instream, **kwargs)

    def save(self, outfile:str, format:str='', **kwargs):
        """Load from file."""
        if isinstance(outfile, bytes):
            outfile = outfile.decode('ascii')
        if not format:
            format = DEFAULT_FORMAT
            # if filename given, try to use it to infer format
            if isinstance(outfile, str):
                try:
                    _, format = outfile.rsplit('.', 1)
                except ValueError:
                    pass
        format = format.lower()
        try:
            saver = self._savers[format]
            encoding = self._encodings[format]
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))
        with ensure_stream(outfile, 'w', encoding=encoding) as outstream:
            return saver(self, outstream, **kwargs)

    def renumber(self, add:int=0):
        """Return a font with renumbered keys."""
        glyphs = {
            (_k + add if isinstance(_k, int) else _k): _v
            for _k, _v in self._glyphs.items()
        }
        return Font(glyphs, self._comments, self._properties)

    def subrange(self, from_:int=0, to_:int=None):
        """Return a continuous subrange of the font."""
        return self.subset(range(from_, to_))

    def subset(self, keys:set=None):
        """Return a subset of the font."""
        if keys is None:
            keys = self._glyphs.keys()
        glyphs = {
            _k: _v
            for _k, _v in self._glyphs.items()
            if _k in keys
        }
        return Font(glyphs, self._comments, self._properties)

    ##########################################################################
    # apply per-glyph operations to whole font

    def modify(self, operation, *args, **kwargs):
        """Return a font with modified glyphs."""
        glyphs = {
            _key: operation(_glyph, *args, **kwargs)
            for _key, _glyph in self._glyphs.items()
        }
        return Font(glyphs, self._comments, self._properties)

    for _name, _func in glyph.__dict__.items():
        if not _name.startswith('_'):
            locals()[_name] = partial(modify, operation=_func)
            locals()[_name].__annotations__ = _func.__annotations__

    ##########################################################################

    def get_max_key(self):
        """Get maximum key in font."""
        return max(_k for _k in self._glyphs.keys() if isinstance(_k, int))

    @classmethod
    def loads(cls, *formats, encoding='utf-8-sig'):
        """Decorator to register font loader."""
        def _loadfunc(fn):
            for format in formats:
                cls._loaders[format.lower()] = fn
                cls._encodings[format.lower()] = encoding
            return fn
        return _loadfunc

    @classmethod
    def saves(cls, *formats, encoding='utf-8'):
        """Decorator to register font saver."""
        def _savefunc(fn):
            for format in formats:
                cls._savers[format.lower()] = fn
                cls._encodings[format.lower()] = encoding
            return fn
        return _savefunc
