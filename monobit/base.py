"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import struct
import binascii
import string
from contextlib import contextmanager
from collections import namedtuple, OrderedDict
from types import SimpleNamespace


DEFAULT_FORMAT = 'text'
VERSION = '0.4'


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

def pad(num, exp):
    """Round up to multiple of 2**exp."""
    mask = 2**exp - 1
    return (num + mask) & ~mask

def bytes_to_bits(inbytes, width=None):
    """Convert bytes/bytearray/sequence of int to tuple of bits."""
    bitstr = ''.join('{:08b}'.format(_b) for _b in inbytes)
    bits = tuple(_c == '1' for _c in bitstr)
    return bits[:width]

def bytes_to_str(s, encoding='latin-1'):
    """Extract null-terminated string from bytes."""
    if b'\0' in s:
        s, _ = s.split(b'\0', 1)
    return s.decode(encoding, errors='replace')

##############################################################################
# binary structs

class Bag(SimpleNamespace):
    """Namespace."""

    def __add__(self, bag):
        """Merge two bags."""
        return Bag(**self.__dict__, **bag.__dict__)

    def __iadd__(self, bag):
        """Marge another bag into this one."""
        self.__dict__.update(bag._dict__)
        return self


def friendlystruct(_endian, **description):
    """A slightly less clunky interface to struct."""


    class Struct:
        """Struct with binary representation."""

        # this requires Python 3.6+ - assumes preservation of dict and kwarg order
        _description = OrderedDict(**description)
        _keys = _description.keys()
        _format = _endian + ''.join(_description.values())
        _namedtuple = namedtuple('Record', _description.keys())
        size = struct.calcsize(_format)

        def __init__(self, *args, **kwargs):
            """Create struct."""
            if args:
                self._data = self._namedtuple(*args)._asdict()
            else:
                self._data = {}
            self._data.update(**kwargs)

        def __repr__(self):
            """String representation."""
            return 'Struct({})'.format(', '.join(
                '{}={}'.format(*_item)
                for _item in self._iteritems()
            ))

        @property
        def __dict__(self):
            """Dict representation."""
            return self._data

        def __bytes__(self):
            """Bytes representation of core struct - missing or extra values not allowed."""
            return struct.pack(self._format, *self._namedtuple(**self._data))

        def __len__(self):
            """Number of elements."""
            return len(self._data)

        def __iter__(self):
            """Iterate over all values, starting with core tuple"""
            for key in self._keys:
                yield self._data[key]
            for key in self._data:
                if key not in self._keys:
                    yield self._data[key]

        def _iteritems(self):
            """Iterate over all key-value pairs, starting with core tuple"""
            for key in self._keys:
                yield key, self._data[key]
            for key in self._data:
                if key not in self._keys:
                    yield key, self._data[key]

        def __getattribute__(self, attr):
            """Retrive a value from the struct."""
            if not attr.startswith('_'):
                return object.__getattribute__(self, '_data')[attr]
            return object.__getattribute__(self, attr)

        def __setattr__(self, attr, value):
            """Set a value in the struct."""
            if not attr.startswith('_'):
                #FIXME: enforce struct order
                object.__getattribute__(self, '_data')[attr] = value
            else:
                object.__setattr__(self, attr, value)

        def __delattr__(self, attr):
            """Deleyte an entry in the struct."""
            if not attr.startswith('_'):
                del object.__getattribute__(self, '_data')[attr]
            else:
                object.__delattr__(self, attr)

        def __getitem__(self, key):
            """Retrieve item by key or tuple index."""
            try:
                return list(self._data.values())[key]
            except TypeError:
                return self._data[key]

        def __setitem__(self, key, value):
            """Set item by key or tuple index. Only the core struct items have tuple indices."""
            try:
                key = list(self._data.keys())[key]
            except TypeError:
                pass
            self._data[key] = value

        def __delitem__(self, key):
            """Delete item by key or tuple index. Only the core struct items have tuple indices."""
            try:
                key = list(self._data.keys())[key]
            except TypeError:
                pass
            del self._data[key]

        def __add__(self, other):
            """Concatenate with another struct."""
            # FIXME - this doesn't actually work the way I need it, can't concat types themselves
            if other._format[0] != self._format[0]:
                raise TypeError("Can't concatenate structs with different byte order.")
            added_type = friendlystruct(self._format[0], **self._description, **other._description)
            return added_type(**self.__dict__, **other.__dict__)

        # note that we override getattribute/setattr for this to work like a namespace
        # - it is not possible to call static/class methods on instances
        # unless they start with _
        # this also means we can't use ** as this requires a .keys function on the instance
        # which collides with our bag namespace

        @classmethod
        def from_bytes(cls, blob, offset=0):
            """Unpack binary blob."""
            return cls(*cls._namedtuple(*struct.unpack_from(cls._format, blob, offset)))

        @classmethod
        def read_from(cls, stream):
            """Read blob from stream and unpack."""
            blob = stream.read(cls.size)
            return cls.from_bytes(blob)

    return Struct



##############################################################################
# text-file comments

def clean_comment(comment):
    """Remove leading characters from comment."""
    while comment and not comment[-1]:
        comment = comment[:-1]
    if not comment:
        return []
    comment = [(_line if _line else '') for _line in comment]
    # remove "comment char" - non-alphanumeric shared first character
    firsts = [_line[0:1] for _line in comment if _line]
    if len(set(firsts)) == 1 and firsts[0] not in string.ascii_letters + string.digits:
        comment = [_line[1:] for _line in comment]
    # normalise leading whitespace
    if all(_line.startswith(' ') for _line in comment if _line):
        comment = [_line[1:] for _line in comment]
    return comment

def split_global_comment(comment):
    while comment and not comment[-1]:
        comment = comment[:-1]
    try:
        splitter = comment[::-1].index('')
    except ValueError:
        global_comment = comment
        comment = []
    else:
        global_comment = comment[:-splitter-1]
        comment = comment[-splitter:]
    return global_comment, comment

def write_comments(outstream, comments, comm_char, is_global=False):
    """Write out the comments attached to a given font item."""
    if comments:
        if not is_global:
            outstream.write('\n')
        for line in comments:
            outstream.write('{} {}\n'.format(comm_char, line))
        if is_global:
            outstream.write('\n')


##############################################################################

def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn


##############################################################################

class Glyph:
    """Single glyph."""

    def __init__(self, pixels=((),), comments=()):
        """Create glyph from tuple of tuples."""
        self._rows = tuple(tuple(_row) for _row in pixels)
        self._comments = comments

    def __repr__(self):
        """Text representation."""
        return "Glyph(\n  '{}'\n)".format(
            "'\n  '".join(self.as_text(foreground='@', background='.'))
        )

    def add_comments(self, comments):
        """Return a copy of the glyph with added comments."""
        return Glyph(self._rows, self._comments + tuple(comments))

    @property
    def comments(self):
        """Extract comments."""
        return self._comments

    @staticmethod
    def empty(width=0, height=0):
        """Create whitespace glyph."""
        return Glyph(((0,) * width,) * height)

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
    def from_bytes(byteseq, width):
        """Create glyph from bytes/bytearray/int sequence."""
        bytewidth = ceildiv(width, 8)
        byteseq = list(byteseq)
        rows = [byteseq[_offs:_offs+bytewidth] for _offs in range(0, len(byteseq), bytewidth)]
        return Glyph(tuple(bytes_to_bits(_row, width) for _row in rows))

    def as_bytes(self):
        """Convert glyph to flat bytes."""
        if not self._rows:
            return b''
        width = len(self._rows[0])
        bytewidth = ceildiv(width, 8)
        # byte-align rows
        rows = [
            _row + (False,) * (bytewidth*8 - width)
            for _row in self._rows
        ]
        # chunk by byte and flatten
        glyph_bytes = [
            _row[_offs:_offs+8]
            for _row in rows
            for _offs in range(0, len(_row), 8)
        ]
        # convert to binary strings
        glyph_bytes = [
            ''.join(str(int(_bit)) for _bit in _byte)
            for _byte in glyph_bytes
        ]
        return bytes(int(_bitstr, 2) for _bitstr in glyph_bytes)

    @staticmethod
    def from_hex(hexstr, width):
        """Create glyph from hex string."""
        return Glyph.from_bytes(binascii.unhexlify(hexstr.encode('ascii')), width)

    def as_hex(self):
        """Convert glyph to hex string."""
        return binascii.hexlify(self.as_bytes()).decode('ascii')

    @property
    def width(self):
        """Pixel width of glyph."""
        if not self._rows:
            return 0
        return len(self._rows[0])

    @property
    def height(self):
        """Pixel height of glyph."""
        return len(self._rows)

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
        # FIXME: adjust offsets?
        return Glyph(tuple(
            _row[left : (-right if right else None)]
            for _row in self._rows[top : (-bottom if bottom else None)]
        ))

    @scriptable
    def expand(self, left:int=0, top:int=0, right:int=0, bottom:int=0):
        """Add empty space."""
        # FIXME: adjust offsets?
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
        # FIXME: adjust offsets?
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

    def __init__(self, glyphs, labels=None, comments=(), properties=None):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        if not labels:
            labels = {_i: _i for _i in range(len(glyphs))}
        self._labels = labels
        if isinstance(comments, dict):
            # per-property comments
            self._comments = comments
        else:
            # global comments only
            self._comments = {None: comments}
        self._properties = properties or {}

    def __iter__(self):
        """Iterate over labels, glyph pairs."""
        for index, glyph in enumerate(self._glyphs):
            labels = tuple(_label for _label, _index in self._labels.items() if _index == index)
            yield labels, glyph

    @property
    def max_ordinal(self):
        """Get maximum ordinal in font."""
        ordinals = self.ordinals
        if ordinals:
            return max(ordinals)
        return -1

    @property
    def ordinal_range(self):
        """Get range of ordinals."""
        return range(0, self.max_ordinal + 1)

    @property
    def ordinals(self):
        """Get tuple of defined ordinals."""
        default_key = self._labels.get(None, None)
        return tuple(_k for _k in self._labels if isinstance(_k, int) and _k != default_key)

    @property
    def all_ordinal(self):
        """All glyphs except the default have ordinals."""
        default_key = self._labels.get(None, None)
        return set(self._labels) - set(self.ordinals) <= set([default_key])

    @property
    def number_glyphs(self):
        """Get number of glyphs in font."""
        return len(self._glyphs)

    @property
    def fixed(self):
        """Font is fixed width."""
        sizes = set((_glyph.width, _glyph.height) for _glyph in self._glyphs)
        return len(sizes) <= 1

    @property
    def max_width(self):
        """Get maximum width."""
        return max(_glyph.width for _glyph in self._glyphs)

    @property
    def max_height(self):
        """Get maximum height."""
        return max(_glyph.height for _glyph in self._glyphs)

    def get_glyph(self, key):
        """Get glyph by key, default if not present."""
        try:
            index = self._labels[key]
        except KeyError:
            return self.get_default_glyph()
        return self._glyphs[index]

    def get_default_glyph(self):
        """Get default glyph."""
        try:
            default_key = self._labels[None]
            return self._glyphs[default_key]
        except KeyError:
            return Glyph.empty(self.max_width, self.max_height)


    ##########################################################################
    @scriptable
    def renumber(self, add:int=0):
        """Return a font with renumbered keys."""
        labels = {
            (_k + add if isinstance(_k, int) else _k): _v
            for _k, _v in self._labels.items()
        }
        return Font(self._glyphs, labels, self._comments, self._properties)

    @scriptable
    def subrange(self, from_:int=0, to_:int=None):
        """Return a continuous subrange of the font."""
        return self.subset(range(from_, to_))

    @scriptable
    def subset(self, keys:set=None):
        """Return a subset of the font."""
        if keys is None:
            keys = self._labels.keys()
        labels = {_k: _v for _k, _v in self._labels.items() if _k in keys}
        indexes = sorted(set(_v for _k, _v in self._labels.items()))
        glyphs = [self._glyphs[_i] for _i in indexes]
        return Font(glyphs, labels, self._comments, self._properties)

    # inject Glyph operations into Font

    for _name, _func in Glyph.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a font with modified glyphs."""
                glyphs = [
                    operation(_glyph, *args, **kwargs)
                    for _glyph in self._glyphs
                ]
                return Font(glyphs, self._comments, self._properties)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify


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
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format))
        return loader(infile, **kwargs)

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
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))
        return saver(self, outfile, **kwargs)

    @classmethod
    def loads(cls, *formats, encoding='utf-8-sig'):
        """Decorator to register font loader."""
        def _load_decorator(load):

            # stream input wrapper
            def _load_func(infile, **kwargs):
                with ensure_stream(infile, 'r', encoding=encoding) as instream:
                    return load(instream, **kwargs)
            _load_func.__doc__ = load.__doc__
            _load_func.__name__ = load.__name__

            # register loader
            for format in formats:
                cls._loaders[format.lower()] = _load_func

            return _load_func
        return _load_decorator

    @classmethod
    def saves(cls, *formats, encoding='utf-8'):
        """Decorator to register font saver."""
        def _save_decorator(save):

            # stream output wrapper
            def _save_func(typeface, outfile, **kwargs):
                with ensure_stream(outfile, 'w', encoding=encoding) as outstream:
                    save(typeface, outstream, **kwargs)
                return typeface
            _save_func.__doc__ = save.__doc__
            _save_func.__name__ = save.__name__

            # register saver
            for format in formats:
                cls._savers[format.lower()] = _save_func

            return _save_func
        return _save_decorator

    # inject Font operations into Typeface

    for _name, _func in Font.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a typeface with modified fonts."""
                fonts = [
                    operation(_font, *args, **kwargs)
                    for _font in self._fonts
                ]
                return Typeface(fonts)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
