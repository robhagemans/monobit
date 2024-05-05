"""
monobit.encoding.charmaps - character maps

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import unicodedata
from pathlib import Path
from html.parser import HTMLParser
from importlib.resources import files
from functools import cached_property, wraps, partial

from ..base.binary import align, int_to_bytes
from ..base import reverse_dict
from ..core.labels import Codepoint, Char, to_label, to_range
from .unicode import is_printable, is_fullwidth, unicode_name
from .base import (
    Encoder, EncoderBuilder, NotFoundError, register_reader, encoding_readers
)
from . import tables


class Unicode(Encoder):
    """Convert between unicode and UTF-32 ordinals."""

    def __init__(self):
        """Unicode converter."""
        super().__init__('unicode')

    @staticmethod
    def char(*labels):
        """Convert codepoint to character."""
        for label in labels:
            codepoint = to_label(label)
            if isinstance(codepoint, bytes):
                # ensure codepoint length is a multiple of 4
                codepoint = codepoint.rjust(align(len(codepoint), 2), b'\0')
                # convert as utf-32 chunks
                chars = tuple(
                    chr(int.from_bytes(codepoint[_start:_start+4], 'big'))
                    for _start in range(0, len(codepoint), 4)
                )
                try:
                    return Char(''.join(chars))
                except ValueError:
                    return Char('')

    @staticmethod
    def codepoint(*labels):
        """Convert character to codepoint."""
        for label in labels:
            char = to_label(label)
            if isinstance(char, str):
                # we used to normalise to NFC here, presumably to reduce multi-codepoint situations
                # but it leads to inconsistency between char and codepoint for canonically equivalent chars
                #char = unicodedata.normalize('NFC', char)
                return Codepoint(b''.join(ord(_c).to_bytes(4, 'big') for _c in char))
        return Codepoint()

    def __repr__(self):
        """Representation."""
        return type(self).__name__ + '()'


class Charmap(Encoder):
    """Convert between unicode and ordinals using stored dictionary."""

    def __init__(self, mapping=None, *, name=''):
        """Create charmap from a dictionary codepoint -> char."""
        super().__init__(name=name)
        if not mapping:
            mapping = {}
            name = ''
        # copy dict
        self._ord2chr = {**mapping}

    @cached_property
    def _chr2ord(self):
        return reverse_dict(self._ord2chr)

    def char(self, *labels):
        """Convert codepoint sequence to character, return empty string if missing."""
        for label in labels:
            codepoint = to_label(label)
            if isinstance(codepoint, bytes):
                try:
                    return Char(self._ord2chr[codepoint])
                except KeyError as e:
                    return Char('')

    def codepoint(self, *labels):
        """Convert character to codepoint sequence, return empty tuple if missing."""
        for label in labels:
            char = to_label(label)
            if isinstance(char, str):
                try:
                    return Codepoint(self._chr2ord[char])
                except KeyError as e:
                    return Codepoint()

    @property
    def mapping(self):
        return {**self._ord2chr}

    def __len__(self):
        """Number of defined codepoints."""
        return len(self._ord2chr)

    def __eq__(self, other):
        """Compare to other Charmap."""
        return isinstance(other, Charmap) and (self._ord2chr == other._ord2chr)

    # charmap operations

    def __sub__(self, other):
        """Return encoding with only characters that differ from right-hand side."""
        return Charmap(
            mapping={_k: _v for _k, _v in self._ord2chr.items() if other.char(_k) != _v},
            name=f'[{self.name}]-[{other.name}]'
        )

    def __or__(self, other):
        """Return encoding overlaid with all characters defined in right-hand side."""
        return Charmap(mapping=self._ord2chr | other._ord2chr, name=f'{self.name}')

    def distance(self, other):
        """Return number of different code points."""
        other_only = set(other._ord2chr) - set(self._ord2chr)
        self_only = set(self._ord2chr) - set(other._ord2chr)
        different = set(
            _k for _k, _v in self._ord2chr.items()
            if _k in other._ord2chr and other.char(_k) != _v
        )
        return len(different) + len(other_only) + len(self_only)

    def subset(self, codepoint_range):
        """Return encoding only for given range of codepoints."""
        codepoint_range = list(to_range(codepoint_range))
        return Charmap(
            mapping={
                _k: _v
                for _k, _v in self._ord2chr.items()
                if (_k in codepoint_range) or (len(_k) == 1 and _k[0] in codepoint_range)
            },
            name=self.name
        )

    def shift(self, by=0x80):
        """
        Increment all codepoints by the given amount.

        by: amount to increment
        """
        return Charmap(
            mapping={
                bytes(Codepoint(int(Codepoint(_k))+by)): _v
                for _k, _v in self._ord2chr.items()
            },
            name=f'shift-{by:x}[{self.name}]'
        )

    # representations

    def chart(self, page=0):
        """Chart of page in charmap."""
        bg = '\u2591'
        cps = range(256)
        cps = (((page, _c) if page else (_c,)) for _c in cps)
        chars = tuple(self.char(_cp) for _cp in cps)
        rows = [(_r, chars[16*_r:16*(_r+1)]) for _r in range(16)]
        # omit empty rows
        for startr, chars in rows:
            if any(chars):
                break
        for stopr, chars in rows[::-1]:
            if any(chars):
                break
        rows = rows[startr:stopr+1]
        def _reprchar(c):
            if c:
                if not is_printable(c):
                    c = '\ufffd'
                if not is_fullwidth(c):
                    c += ' '
                # deal with Nonspacing Marks while keeping table format
                if unicodedata.category(c[:1]) == 'Mn':
                    c = ' ' + c
            else:
                c = bg * 2
            return c
        rows = (
            (_r, bg.join(_reprchar(_c) for _c in _chars))
            for _r, _chars in rows
        )
        return ''.join((
            '#     ', ' '.join(f'_{_c:x}' for _c in range(16)), '\n# ',
            '  +', '-'*48, '-', '\n# ',
            '\n# '.join(
                ''.join((f'{_r:x}_|', bg, _chars, bg))
                for _r, _chars in rows
            )
        ))

    def table(self):
        """Mapping table"""
        return '\n'.join(
            f'0x{_k.hex()}: u+{ord(_v):04X}  # {unicode_name(_v)}' for _k, _v in self._ord2chr.items()
        )

    def __repr__(self):
        """Representation."""
        if self._ord2chr:
            mapping = f'<{len(self._ord2chr)} code points>'
            chart = f'\n{self.chart()}\n'
            return (
                f"{type(self).__name__}(name='{self.name}', mapping={mapping}){chart}"
            )
        return (
            f"{type(self).__name__}()"
        )


class EncoderLoader(EncoderBuilder):
    """Lazily create new encoder from file."""

    def __init__(self, filename, *, format=None, name='', **kwargs):
        if not name:
            name = Path(filename).stem
        filename = str(filename)
        # inputs that look like explicit paths used directly
        # otherwise it's relative to the tables package
        if filename.startswith('/') or filename.startswith('.'):
            path = Path(filename)
        else:
            path = files(tables) / filename
        if not path.exists():
            raise NotFoundError(f'Charmap file `{filename}` does not exist')
        format = format or path.suffix[1:].lower()
        try:
            reader, format_kwargs = encoding_readers[format]
        except KeyError as exc:
            raise NotFoundError(f'Undefined charmap file format {format}.') from exc
        super().__init__(partial(reader, name, path, **format_kwargs, **kwargs))


###############################################################################
# charmap loaders


def _charmap_loader(fn):
    """Decorator for the shared parts of charmap loaders."""

    @wraps(fn)
    def _load(name, path, *args, **kwargs):
        try:
            data = path.read_bytes()
        except EnvironmentError as exc:
            raise NotFoundError(f'Could not load charmap file `{str(path)}`: {exc}')
        if not data:
            raise NotFoundError(f'No data in charmap file `{str(path)}`')
        mapping = fn(data, *args, **kwargs)
        return Charmap(mapping, name=name)

    return _load


@register_reader('txt')
@register_reader('enc')
@register_reader('map')
@register_reader('ucp', separator=':', joiner=',')
@register_reader('adobe', separator='\t', joiner=None, codepoint_column=1, unicode_column=0)
@_charmap_loader
def _from_text_columns(
        data, *, comment='#', separator=None, joiner='+', codepoint_column=0, unicode_column=1,
        codepoint_base=16, unicode_base=16, inline_comments=True, ignore_errors=False,
    ):
    """Extract character mapping from text columns in file data (as bytes)."""
    mapping = {}
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        if line.startswith('START') or line.startswith('END'):
            # xfonts .enc files - STARTENCODING, STARTMAPPING etc.
            continue
        # strip off comments
        if inline_comments:
            line = line.split(comment)[0]
        # split unicodepoint and hex string
        splitline = line.split(separator)
        if len(splitline) > max(codepoint_column, unicode_column):
            cp_str, uni_str = splitline[codepoint_column], splitline[unicode_column]
            cp_str = cp_str.strip()
            uni_str = uni_str.strip()
            # right-to-left marker in mac codepages
            uni_str = uni_str.replace('<RL>+', '').replace('<LR>+', '')
            # reverse-video marker in kreativekorp codepages
            uni_str = uni_str.replace('<RV>+', '')
            # czyborra's codepages have U+ in front
            if uni_str.upper().startswith('U+'):
                uni_str = uni_str[2:]
            # ibm-ugl codepage has U in front
            if uni_str.upper().startswith('U'):
                uni_str = uni_str[1:]
            # czyborra's codepages have = in front
            if cp_str.upper().startswith('='):
                cp_str = cp_str[1:]
            try:
                # allow sequence of codepoints
                # multibyte code points can also be given as single large number
                # note that the page bytewidth of the codepoints is assumed to be 1
                cp_point = b''.join(
                    int_to_bytes(int(_substr, codepoint_base))
                    for _substr in cp_str.split(joiner)
                )
                if unicode_base == 'char':
                    # the character itself is in the column, utf-8 encoded
                    char = uni_str
                else:
                    # allow sequence of unicode code points separated by 'joiner'
                    char = ''.join(
                        chr(int(_substr, unicode_base))
                        for _substr in uni_str.split(joiner)
                    )
                if char != '\uFFFD':
                    # u+FFFD replacement character is used to mark undefined code points
                    mapping[cp_point] = char
            except (ValueError, TypeError) as e:
                # ignore malformed lines
                if not ignore_errors:
                    logging.warning('Could not parse line in text charmap file: %s [%s]', e, repr(line))
    return mapping


@register_reader('ucm')
@_charmap_loader
def _from_ucm_charmap(data):
    """Extract character mapping from icu ucm / linux charmap file data (as bytes)."""
    # only deals with sbcs
    comment = '#'
    escape = '\\'
    # precision indicator
    precision = '|'
    mapping = {}
    parse = False
    for line in data.decode('utf-8-sig').splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == comment):
            continue
        if line.startswith('<comment_char>'):
            comment = line.split()[-1].strip()
        elif line.startswith('<escape_char>'):
            escape = line.split()[-1].strip()
        elif line.startswith('CHARMAP'):
            parse = True
            continue
        elif line.startswith('END CHARMAP'):
            parse = False
        if not parse:
            continue
        # split columns
        splitline = line.split()
        # ignore malformed lines
        exc = ''
        cp_bytes, uni_str = '', ''
        for item in splitline:
            if item.startswith('<U'):
                # e.g. <U0000> or <U2913C>
                uni_str = item[2:-1]
            elif item.startswith(escape + 'x'):
                cp_str = item.replace(escape + 'x', '')
                cp_bytes = bytes.fromhex(cp_str)
            elif item.startswith(precision):
                # precision indicator
                # |0 - A “normal”, roundtrip mapping from a Unicode code point and back.
                # |1 - A “fallback” mapping only from Unicode to the codepage, but not back.
                # |2 - A subchar1 mapping. The code point is unmappable, and if a substitution is
                #      performed, then the subchar1 should be used rather than the subchar.
                #      Otherwise, such mappings are ignored.
                # |3 - A “reverse fallback” mapping only from the codepage to Unicode, but not back
                #      to the codepage.
                # |4 - A “good one-way” mapping only from Unicode to the codepage, but not back.
                if item[1:].strip() != '0':
                    # only accept 'normal' mappings
                    # should we also allow "reverse fallback" ?
                    break
        else:
            if not uni_str or not cp_str:
                logging.warning('Could not parse line in ucm charmap file: %s.', repr(line))
                continue
            if cp_bytes in mapping:
                logging.debug('Ignoring redefinition of code point %s', cp_bytes)
            else:
                mapping[cp_bytes] = chr(int(uni_str, 16))
    return mapping


@register_reader('html')
@_charmap_loader
def _from_wikipedia(data, table=0, column=0, range=None):
    """
    Scrape charmap from table in Wikipedia.
    Reads matrix tables with class="chset".
    table: target table; 0 for 1st chset table, etc.
    column: target column if multiple unicode points provided per cell.
    range: range to read, read all if range is empty
    """

    class _WikiParser(HTMLParser):
        """HTMLParser object to read Wikipedia tables."""

        def __init__(self):
            """Set up Wikipedia parser."""
            super().__init__()
            # output dict
            self.mapping = {}
            # state variables
            # parsing chset table
            self.table = False
            self.count = 0
            # data element
            self.td = False
            # the unicode point is surrounded by <small> tags
            self.small = False
            # parse row header
            self.th = False
            # current codepoint
            self.current = 0

        def handle_starttag(self, tag, attrs):
            """Change state upon encountering start tag."""
            attrs = dict(attrs)
            if (
                    tag == 'table'
                    and 'class' in attrs
                    and 'chset' in attrs['class']
                ):
                if self.count == table:
                    self.table = True
                    self.th = False
                    self.td = False
                    self.small = False
                self.count += 1
            elif self.table:
                if tag == 'td':
                    self.td = True
                    self.small = False
                elif tag == 'small':
                    self.small = True
                elif tag == 'th':
                    self.th = True

        def handle_endtag(self, tag):
            """Change state upon encountering end tag."""
            if tag == 'table':
                self.table = False
                self.th = False
                self.td = False
                self.small = False
            elif tag == 'td':
                self.td = False
                self.current += 1
            elif tag == 'style':
                self.small = False
            elif tag == 'th':
                self.th = False

        def handle_data(self, data):
            """Parse cell data, depending on state."""
            # row header provides first code point of the row
            if self.th and len(data) == 2 and data[-1] == '_':
                self.current = int(data[0],16) * 16
            # unicode point in <small> tag in table cell
            if self.td and self.small:
                cols = data.split()
                if len(cols) > column:
                    data = cols[column]
                if len(data) >= 4:
                    # unicode point
                    if data.lower().startswith('u+'):
                        data = data[2:]
                    # pylint: disable=unsupported-membership-test
                    if not range or self.current in range:
                        try:
                            char = chr(int(data, 16))
                        except ValueError:
                            # not a unicode point
                            pass
                        else:
                            self.mapping[bytes((self.current,))] = char

    parser = _WikiParser()
    parser.feed(data.decode('utf-8-sig'))
    return parser.mapping
