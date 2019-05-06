"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import struct
from contextlib import contextmanager
from functools import partial
from collections import namedtuple


DEFAULT_FORMAT = 'text'
VERSION = '0.3'


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
    try:
        with instream:
            yield instream
    except BrokenPipeError:
        # ignore broken pipes
        pass

def ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)

def bytes_to_bits(inbytes, width=None):
    """Convert bytes/bytearray/sequence of int to tuple of bits."""
    bitstr = ''.join('{:08b}'.format(_b) for _b in inbytes)
    bits = tuple(_c == '1' for _c in bitstr)
    return bits[:width]

def struct_to_dict(fmt, keys, buffer, offset=0):
    """Unpack from buffer into dict."""
    rec_tuple = struct.unpack_from(fmt, buffer, offset)
    record = namedtuple('Record', keys)._make(rec_tuple)
    return record._asdict()

def bytes_to_str(s, encoding='latin-1'):
    """Extract null-terminated string from bytes."""
    if b'\0' in s:
        s, _ = s.split(b'\0', 1)
    return s.decode(encoding, errors='replace')


def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn


##############################################################################

class Glyph:
    """Single glyph."""

    def __init__(self, pixels=((),)):
        """Create glyph from tuple of tuples."""
        self._rows = pixels

    @staticmethod
    def from_text(rows, background):
        """Create glyph from sequence of str."""
        return Glyph(tuple(
            tuple(_char not in background for _char in _row)
            for _row in rows
        ))

    def as_text(self, foreground, background):
        """Convert glyph to tuple of str."""
        return tuple(
            ''.join((foreground if _bit else background) for _bit in _row)
            for _row in self._rows
        )

    @staticmethod
    def from_bytes(byteseq, width=None):
        """Create glyph from bytes/bytearray/int sequence."""
        bytewidth = ceildiv(width, 8)
        byteseq = list(byteseq)
        rows = [byteseq[_offs:_offs+bytewidth] for _offs in range(0, len(byteseq), bytewidth]
        return Glyph(tuple(bytes_to_bits(_row)[:width] for _row in rows))

    ##########################################################################

    @scriptable
    def mirror(self):
        """Reverse pixels horizontally."""
        return Glyph(tuple(_row[::-1] for _row in self._rows))

    @scriptable
    def flip(self):
        """Reverse pixels vertically."""
        return Glyph(self._rows[::-1])

    @scriptable
    def transpose(self):
        """Transpose glyph."""
        return Glyph(tuple(tuple(_x) for _x in zip(*self._rows)))

    @scriptable
    def rotate(self, turns:int=1):
        """Rotate by 90-degree turns; positive is clockwise."""
        turns %= 4
        if turns == 3:
            return self.transpose().flip()
        elif turns == 2:
            return self.mirror().flip()
        elif turns == 1:
            return self.transpose().mirror()
        return self

    @scriptable
    def invert(self):
        """Reverse video."""
        return Glyph(tuple(tuple((not _col) for _col in _row) for _row in self._rows))

    @scriptable
    def crop(self, left:int=0, top:int=0, right:int=0, bottom:int=0):
        """Crop glyph, inclusive bounds."""
        return Glyph(tuple(
            _row[left : (-right if right else None)]
            for _row in self._rows[top : (-bottom if bottom else None)]
        ))

    @scriptable
    def expand(self, left:int=0, top:int=0, right:int=0, bottom:int=0):
        """Add empty space."""
        if self._rows:
            old_width = len(self._rows[0])
        else:
            old_width = 0
        new_width = left + old_width + right
        return Glyph(
            ((False,)*new_width, ) * top
            + tuple((False,)*left + _row + (False,)*right for _row in self._rows)
            + ((False,)*new_width, ) * bottom
        )

    @scriptable
    def stretch(self, factor_x:int=1, factor_y:int=1):
        """Repeat rows and/or columns."""
        # vertical stretch
        glyph = tuple(_row for _row in self._rows for _ in range(factor_y))
        # horizontal stretch
        glyph = tuple(
            tuple(_col for _col in _row for _ in range(factor_x))
            for _row in glyph
        )
        return Glyph(glyph)

    @scriptable
    def shrink(self, factor_x:int=1, factor_y:int=1, force:bool=False):
        """Remove rows and/or columns."""
        # vertical shrink
        shrunk_glyph = self._rows[::factor_y]
        if not force:
            # check we're not throwing away stuff
            for offs in range(1, factor_y):
                alt = self._rows[offs::factor_y]
                if shrunk_glyph != alt:
                    raise ValueError("can't shrink glyph without loss")
        # horizontal stretch
        glyph = tuple(_row[::factor_x] for _row in self._rows)
        return Glyph(glyph)


##############################################################################

class Font:
    """Glyphs and metadata."""

    def __init__(self, glyphs, comments=(), properties=None):
        """Create new font."""
        self._glyphs = glyphs
        if isinstance(comments, dict):
            # per-key comments
            self._comments = comments
        else:
            # global comments only
            self._comments = {None: comments}
        self._properties = properties or {}

    def get_max_key(self):
        """Get maximum key in font."""
        return max(_k for _k in self._glyphs.keys() if isinstance(_k, int))

    @scriptable
    def renumber(self, add:int=0):
        """Return a font with renumbered keys."""
        glyphs = {
            (_k + add if isinstance(_k, int) else _k): _v
            for _k, _v in self._glyphs.items()
        }
        return Font(glyphs, self._comments, self._properties)

    @scriptable
    def subrange(self, from_:int=0, to_:int=None):
        """Return a continuous subrange of the font."""
        return self.subset(range(from_, to_))

    @scriptable
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

    def _modify(self, operation, *args, **kwargs):
        """Return a font with modified glyphs."""
        glyphs = {
            _key: operation(_glyph, *args, **kwargs)
            for _key, _glyph in self._glyphs.items()
        }
        return Font(glyphs, self._comments, self._properties)

    for _name, _func in Glyph.__dict__.items():
        if hasattr(_func, 'scriptable'):
            operation = partial(_modify, operation=_func)
            operation.scriptable = True
            operation.script_args = _func.script_args
            locals()[_name] = operation


##############################################################################

class Typeface:
    """One or more fonts."""

    _loaders = {}
    _savers = {}
    _encodings = {}

    def __init__(self, fonts=()):
        """Create typeface from sequence of fonts."""
        self._fonts = tuple(fonts)

    @classmethod
    def load(cls, infile:str, format:str='', **kwargs):
        """Read new font from file."""
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

    @scriptable
    def save(self, outfile:str, format:str='', **kwargs):
        """Write to file, return unchanged."""
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
            saver(self, outstream, **kwargs)
            return self

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

    def _modify(self, operation, *args, **kwargs):
        """Return a typeface with modified fonts."""
        fonts = [
            operation(_font, *args, **kwargs)
            for _font in self._fonts
        ]
        return Typeface(fonts)

    for _name, _func in Font.__dict__.items():
        if hasattr(_func, 'scriptable'):
            operation = partial(_modify, operation=_func)
            operation.scriptable = True
            operation.script_args = _func.script_args
            locals()[_name] = operation
