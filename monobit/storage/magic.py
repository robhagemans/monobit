"""
monobit.magic - file type recognition

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from fnmatch import fnmatch
import re

from .streams import get_name, DirectoryStream


# number of bytes to read to check if something looks like text
_TEXT_SAMPLE_SIZE = 256
# bytes not expected in (modern) text files
_NON_TEXT_BYTES = (
    # C0 controls except HT, LF, CR
    tuple(range(9)) + (11, 12,) + tuple(range(14, 32))
    # also check for F8-FF which shouldn't occur in utf-8 text
    + tuple(range(0xf8, 0x100))
    # we don't currently parse text formats that need the latin-1 range:
    # - yaff is utf-8 excluding controls
    # - bdf, bmfont are printable ascii [0x20--0x7e] plus 0x0a, 0x0d
    # - hex, draw have undefined range, but we can assume ascii or utf-8
)


class FileFormatError(Exception):
    """Incorrect file format."""


def maybe_text(instream):
    """
    Check if a binary input stream looks a bit like it might hold utf-8 text.
    Currently just checks for unexpected bytes in a short sample.
    """
    if instream.mode == 'w':
        # output binary streams *could* hold text
        # (this is not about the file type, but about the content)
        return True
    try:
        sample = instream.peek(_TEXT_SAMPLE_SIZE)
    except EnvironmentError:
        return None
    if set(sample) & set(_NON_TEXT_BYTES):
        logging.debug(
            'Found unexpected bytes: identifying unknown input stream as binary.'
        )
        return False
    try:
        sample.decode('utf-8')
    except UnicodeDecodeError as err:
        # need to ensure we ignore errors due to clipping inside a utf-8 sequence
        if err.reason != 'unexpected end of data':
            logging.debug(
                'Found non-UTF8: identifying unknown input stream as binary.'
            )
            return False
    logging.debug('Tentatively identifying unknown input stream as text.')
    return True


class MagicRegistry:
    """Retrieve file converters through magic sequences and name patterns."""

    def __init__(self, func_name, default_text='', default_binary=''):
        """Set up registry."""
        self._magic = []
        self._patterns = []
        self._names = {}
        self._func_name = func_name
        self._default_text = default_text
        self._default_binary = default_binary

    def get_formats(self):
        """Get tuple of all registered format names."""
        return tuple(self._names.keys())

    def get_for(self, file=None, format=''):
        """
        Get loader/saver function for this format.
        file must be a Stream or None
        """
        if isinstance(file, DirectoryStream):
            # directory 'stream'
            return (self._names['dir'],)
        if format:
            try:
                converter = (self._names[format],)
            except KeyError:
                raise ValueError(
                    f'Format specifier `{format}` not recognised'
                )
        else:
            converter = self.identify(file)
            if not converter:
                if not file or file.mode == 'w' or maybe_text(file):
                    format = self._default_text
                else:
                    format = self._default_binary
                if file and format:
                    if Path(file.name).suffix:
                        level = logging.WARNING
                    else:
                        level = logging.DEBUG
                    logging.log(
                        level,
                        f'Could not infer format from filename `{file.name}`. '
                        f'Falling back to default `{format}` format'
                    )
                try:
                    converter = (self._names[format],)
                except KeyError:
                    pass
        return converter

    def register(
            self, name='', magic=(), patterns=(),
            funcwrapper=lambda _:_
        ):
        """Decorator to register converter for file type."""

        def _decorator(converter):
            if not name:
                raise ValueError('No registration name given')
            if name in self._names:
                raise ValueError(f'Registration name `{name}` already in use for {self._names[name]}')
            if not isinstance(magic, (list, tuple)):
                raise TypeError('Registration parameter `magic` must be list or tuple')
            if not isinstance(patterns, (list, tuple)):
                raise TypeError('Registration parameter `patterns` must be list or tuple')
            converter.format = name
            self._names[name] = converter
            ## magic signatures
            for sequence in magic:
                self._magic.append((Magic(sequence), converter))
            # sort the magic registry long to short to manage conflicts
            self._magic = list(sorted(
                    self._magic,
                    key=lambda _i:len(_i[0]), reverse=True
                )
            )
            ## glob patterns
            for pattern in (*patterns, f'*.{name}'):
                self._patterns.append((to_pattern(pattern), converter))
            return funcwrapper(converter)

        return _decorator

    def identify(self, file):
        """Identify a type from magic sequence on input file."""
        if not file:
            return ()
        matches = []
        ## match magic on readable files
        if file.mode == 'r':
            for magic, converter in self._magic:
                if magic.fits(file):
                    logging.debug(
                        'Stream matches signature for format `%s`.',
                        converter.format
                    )
                    matches.append(converter)
        ## match glob patterns
        glob_matches = []
        for pattern, converter in self._patterns:
            if pattern.fits(file):
                logging.debug(
                    'Filename matches pattern for format `%s`.',
                    converter.format
                )
                glob_matches.append(converter)
        matches.extend(_c for _c in glob_matches if _c not in matches)
        return tuple(matches)

    def get_template(self, format):
        """Get output filename template for format."""
        for pattern, converter in self._patterns:
            if converter.format == format:
                template = pattern.generate('{name}')
                if template:
                    return template
        return '{name}' f'.{format}'


###############################################################################
# file format matchers

class Magic:
    """Match file contents against bytes mask."""

    def __init__(self, value, offset=0):
        """Initialise bytes mask from bytes or Magic object."""
        if isinstance(value, Magic):
            self._mask = tuple(
                (_item[0] + offset, _item[1])
                for _item in  value._mask
            )
        elif not isinstance(value, bytes):
            raise TypeError(
                'Initialiser must be bytes or Magic,'
                f' not {type(value).__name__}'
            )
        else:
            self._mask = ((offset, value),)

    def __len__(self):
        """Mask length."""
        return max(_item[0] + len(_item[1]) for _item in self._mask)

    def __add__(self, other):
        """Concatenate masks."""
        other = Magic(other, offset=len(self))
        new = Magic(self)
        new._mask += other._mask
        return new

    def __radd__(self, other):
        """Concatenate masks."""
        other = Magic(other)
        return other + self

    def matches(self, target):
        """Target bytes match the mask."""
        if len(target) < len(self):
            return False
        for offset, value in self._mask:
            if target[offset:offset+len(value)] != value:
                return False
        return True

    def fits(self, instream):
        """Binary stream matches the signature."""
        if instream.mode == 'w':
            return False
        return self.matches(instream.peek(len(self)))

    @classmethod
    def offset(cls, offset=0):
        """Represent offset in concatenated mask."""
        return cls(value=b'', offset=offset)


class Pattern:
    """Match filename against pattern."""

    def matches(self, target):
        """Target string matches the pattern."""
        raise NotImplementedError()

    def fits(self, instream):
        """Stream filename matches the pattern."""
        return self.matches(Path(instream.name).name)

    def generate(self, name):
        """Generate name that fits pattern. Failure -> empty"""
        raise NotImplementedError()


class Glob(Pattern):
    """Match filename against pattern using case-insensitive glob."""

    def __init__(self, pattern):
        """Set up pattern matcher."""
        self._pattern = pattern.lower()

    def matches(self, target):
        """Target string matches the pattern."""
        return fnmatch(str(target).lower(), self._pattern.lower())

    def generate(self, name):
        """Generate template that fits pattern. Failure -> empty"""
        if not '?' in self._pattern and not '[' in self._pattern:
            try:
                return self._pattern.replace('*', '{}').format(name)
            except IndexError:
                # multiple *
                pass
        return ''


class Regex(Pattern):
    """Match filename against pattern using regular expression."""

    def __init__(self, pattern):
        """Set up pattern matcher."""
        self._pattern = re.compile(pattern)

    def matches(self, target):
        """Target string matches the pattern."""
        return self._pattern.fullmatch(str(target).lower()) is not None

    def generate(self, name):
        """Generate name that fits pattern. Failure -> empty"""
        return ''


def to_pattern(obj):
    """Convert to Pattern object."""
    if isinstance(obj, Pattern):
        return obj
    return Glob(str(obj))
