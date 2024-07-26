"""
monobit.storage.magic - file type recognition

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from fnmatch import fnmatch
import re

from .streams import get_name
from ..base import FileFormatError


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


def looks_like_text(instream):
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
            'Found non-text-like bytes: '
            f"input stream '{instream.name}' is likely binary."
        )
        return False
    try:
        sample.decode('utf-8')
    except UnicodeDecodeError as err:
        # need to ensure we ignore errors due to clipping inside a utf-8 sequence
        if err.reason != 'unexpected end of data':
            logging.debug(
                'Found non-UTF8 sequences:'
                f"input stream '{instream.name}' is likely binary."
            )
            return False
    logging.debug(
        f"input stream '{instream.name}' is likely text."
    )
    return True


class MagicRegistry:
    """Retrieve file converters through magic sequences and name patterns."""

    def __init__(self, default_text='', default_binary=''):
        """Set up registry."""
        self._magic = []
        self._patterns = []
        self._templates = []
        self._names = {}
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
        if format:
            try:
                converter = (self._names[format],)
            except KeyError:
                return ()
        else:
            converter = self.identify(file)
            if not converter:
                if not file or file.mode == 'w' or looks_like_text(file):
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
                        f"Could not infer format from file '{file.name}'. "
                        f'Falling back to default `{format}` format'
                    )
                try:
                    converter = (self._names[format],)
                except KeyError:
                    pass
        return converter

    def register(
            self, name='',
            magic=(), patterns=(), template=(),
            text=False,
            linked=None,
        ):
        """
        Decorator to register converter for file type.

        name: unique name of the format
        magic: magic sequences for this format (no effect for savers)
        patterns: filename patterns for this format
        template: template to generate filenames
        text: text-based format
        linked: earlier registration to take information from
        """

        def _decorator(converter):

            converter.format = name
            converter.magic = magic
            converter.patterns = patterns
            converter.template = template
            converter.text = text
            if linked:
                # take from linked registration
                converter.format = converter.format or linked.format
                converter.magic = converter.magic or linked.magic
                converter.patterns = converter.patterns or linked.patterns
                converter.template = converter.template or linked.template
                converter.text = converter.text or linked.text

            if not converter.format:
                raise ValueError('No registration name given')
            if converter.format in self._names:
                raise ValueError(
                    f'Registration name `{converter.format}` '
                    f'already in use for {self._names[converter.format]}'
                )
            if not isinstance(magic, (list, tuple)):
                raise TypeError(
                    'Registration parameter `magic` must be list or tuple'
                )
            if not isinstance(patterns, (list, tuple)):
                raise TypeError(
                    'Registration parameter `patterns` must be list or tuple'
                )
            self._names[converter.format] = converter
            ## magic signatures
            for sequence in converter.magic:
                if isinstance(sequence, bytes):
                    sequence = Magic(sequence)
                self._magic.append((sequence, converter))
            # sort the magic registry long to short to manage conflicts
            self._magic = list(sorted(
                    self._magic,
                    key=lambda _i:len(_i[0]), reverse=True
                )
            )
            ## glob patterns
            # glob_patterns = tuple(set(
            #     (*converter.patterns, f'*.{converter.format}')
            # ))
            for pattern in converter.patterns:
                self._patterns.append((to_pattern(pattern), converter))
            self._templates.append((converter.template, converter))
            return converter

        return _decorator

    def identify(self, file):
        """Identify a type from magic sequence on input file."""
        if not file:
            return ()
        matches = []
        maybe_text = looks_like_text(file)
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
                if converter.text and not maybe_text:
                    logging.debug(
                        'but format `%s` requires text.',
                        converter.format
                    )
                else:
                    glob_matches.append(converter)
        matches.extend(_c for _c in glob_matches if _c not in matches)
        return tuple(matches)

    def get_template(self, format):
        """Get output filename template for format."""
        for template, converter in self._templates:
            if template and converter.format == format:
                return template
        for pattern, converter in self._patterns:
            if converter.format == format:
                template = pattern.generate('{name}')
                if template:
                    return template
        return '{name}' f'.{format}'


###############################################################################
# file signature matchers

class Magic:
    """Match file contents against bytes mask."""

    def __init__(self, value, offset=0):
        """Initialise bytes mask from bytes or Magic object."""
        if isinstance(value, Magic):
            self._mask = tuple(
                (_item[0] + offset, _item[1])
                for _item in value._mask
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


class Sentinel:
    """Match file contents against start-of-line sentinel."""

    def __init__(self, value, length=256):
        self._sentinel = value
        self._peek_length = length

    def __len__(self):
        return len(self._sentinel)

    def fits(self, instream):
        """Binary stream has the sentinel."""
        if instream.mode == 'w':
            return False
        buffer = instream.peek(self._peek_length)
        return (
            buffer.startswith(self._sentinel)
            or b'\n' + self._sentinel in buffer
            or b'\r' + self._sentinel in buffer
        )


###############################################################################
# filename pattern matchers

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
