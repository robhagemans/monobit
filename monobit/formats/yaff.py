"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from types import SimpleNamespace
from itertools import count, zip_longest
from collections import deque

from ..storage import loaders, savers
from ..encoding import charmaps
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..basetypes import Any
from ..labels import strip_matching, Tag
from ..struct import Props


##############################################################################
# interface


@loaders.register('yaff', 'yaffs', magic=(b'---',), name='yaff')
def load_yaff(instream, where=None):
    """Load font from a monobit .yaff file."""
    return _load_yaff(instream.text)

@savers.register(linked=load_yaff)
def save_yaff(fonts, outstream, where=None):
    """Write fonts to a monobit .yaff file."""
    YaffWriter().save(fonts, outstream.text)


##############################################################################
# format parameters

BOUNDARY_MARKER = '---'


class YaffParams:
    """Parameters for .yaff format."""

    # first/second pass constants
    separator = ':'
    comment = '#'
    # output only
    tab = '    '
    separator_space = '\n'
    # tuple of individual chars, need to be separate for startswith
    whitespace = tuple(' \t')

    # third-pass constants
    ink = '@'
    paper = '.'
    empty = '-'
    # convert key string to key object - handled by Glyph constructor
    convert_key = staticmethod(Any)


##############################################################################
##############################################################################
# read file


def _load_yaff(text_stream):
    """Parse a yaff/yaffs file."""
    reader = YaffReader()
    fonts = []
    for line in text_stream:
        if line.strip() == BOUNDARY_MARKER:
            fonts.append(YaffConverter.get_font_from(reader))
            reader.reset()
        else:
            reader.step(line)
    fonts.append(YaffConverter.get_font_from(reader))
    return fonts


class TextReader:
    """Parser for text-based font file."""

    # first/second pass constants
    separator: str
    comment: str
    # tuple of individual chars, need to be separate for startswith
    whitespace: str

    def __init__(self, indent=0):
        """Set up text reader."""
        # current element appending to
        self._current = ''
        # elements done
        self._elements = deque()
        # indentation level
        self._indent = indent

    # first pass: lines to elements

    def get_clusters(self):
        """Convert elements to clusters and return."""
        self._yield_element()
        # run second pass and append
        return self._build_clusters(self._elements)

    def reset(self):
        """Reset parser for new section."""
        self._elements = deque()
        self._current = ''

    def _yield_element(self):
        """Close and append current element and start a new one."""
        if self._current:
            self._elements.append(self._current)
        self._current = ''

    def step(self, line):
        """Parse a single line."""
        # strip indent
        line = line[self._indent:]
        # strip trailing whitespace
        contents = line.rstrip()
        if contents.startswith(self.comment):
            if self._current and not self._current.startswith(self.comment):
                # new comment
                self._yield_element()
            self._step_value(contents)
        elif not contents.strip():
            # ignore empty lines except while parsing comments
            if self._current.startswith(self.comment):
                # new comment
                self._yield_element()
        elif not contents.startswith(self.whitespace):
            # glyph label
            if contents.endswith(self.separator):
                self._yield_element()
                self._step_value(contents)
                self._yield_element()
            else:
                # new key, separate at the first :
                # keys must be alphanum so no need to worry about quoting
                key, sep, value = contents.partition(self.separator)
                self._yield_element()
                # yield key
                self._step_value(key + sep)
                self._yield_element()
                # start building value
                self._step_value(value.lstrip())
        else:
            # continue building value
            self._step_value(contents)

    def _step_value(self, contents):
        """Continue building value."""
        if self._current:
            self._current += '\n' + contents
        else:
            self._current = contents

    # second pass: elements to clusters

    def _build_clusters(self, elements):
        """Group elements into clusters."""
        clusters = []
        # current cluster
        current = []
        for element in elements:
            # drop empty elements at top
            if clusters or element:
                current.append(element)
            # each cluster ends with a value
            # it can start with multiple keys and comments in no given order
            if element and not element.startswith(self.comment) and not element.endswith(self.separator):
                # yield cluster
                clusters.append(current)
                current = []
        # separate out global top comment
        if clusters and clusters[0]:
            comments = [
                _elem for _elem in clusters[0] if _elem.startswith(self.comment) or not _elem
            ]
            if comments:
                others = [
                    _elem for _elem in clusters[0] if _elem and not _elem.startswith(self.comment)
                ]
                if len(comments) > 1:
                    new_first = comments[:-1]
                    new_second = [comments[-1], *others]
                    clusters = [new_first, new_second, *clusters[1:]]
                else:
                    clusters = [comments, others, *clusters[1:]]
        return clusters


class YaffReader(YaffParams, TextReader):
    """Reader for .yaff files."""


class TextConverter:
    """Convert text clusters to font."""

    # first/second pass constants
    separator: str
    comment: str
    whitespace: str

    # third-pass constants
    ink: str
    paper: str
    empty: str

    @staticmethod
    def convert_key(keystr):
        """Convert key string to key object."""
        raise NotImplementedError


    # third pass: interpret clusters

    def __init__(self):
        """Set up converter."""
        self.props = Props()
        self.comments = {}
        self.glyphs = []

    @classmethod
    def get_font_from(cls, reader):
        """Get clusters from reader and convert to Font."""
        conv = cls._convert_from(reader)
        if not conv.glyphs:
            raise FileFormatError('No glyphs found in yaff file.')
        return Font(conv.glyphs, comment=conv.comments, **vars(conv.props))

    @classmethod
    def _convert_from(cls, reader):
        """Get clusters from reader and convert."""
        clusters = reader.get_clusters()
        # recursive call
        converter = cls()
        for cluster in clusters:
            converter.convert_cluster(cluster)
        return converter

    def convert_cluster(self, cluster):
        """Convert cluster."""
        # keys
        keys = tuple(
            _elem[:-len(self.separator)].strip()
            for _elem in cluster
            if _elem.endswith(self.separator) and not _elem.startswith(self.comment)
        )
        comments = tuple(
            _elem
            for _elem in cluster
            if _elem.startswith(self.comment)
        )
        comments = self._clean_comment('\n'.join(comments))
        values = tuple(
            _elem
            for _elem in cluster
            if _elem and not _elem.startswith(self.comment) and not _elem.endswith(self.separator)
        )
        if len(values) > 1:
            raise ValueError('Cluster with multiple value elements')
        if not values:
            if keys:
                raise ValueError('Cluster with keys but without value element')
            # global comment
            self.comments[''] = comments
            return
        value, = values
        origlines = value.splitlines()
        striplines = tuple(_line.strip() for _line in origlines)
        lines = tuple(_line for _line in striplines if _line)
        # if any line in the value has only glyph symbols, this cluster is a glyph
        is_glyph = lines and self._line_is_glyph(lines[0])
        if is_glyph:
            self.glyphs.append(self._convert_glyph(keys, origlines, striplines, comments))
        else:
            # multiple labels translate into multiple keys with the same value
            lines = (strip_matching(_line, '"') for _line in lines)
            propvalue = '\n'.join(lines)
            for key in keys:
                # Props object converts only non-leading underscores (for internal use)
                # so we need to mae sure e turn those into dashes or we'll drop the prop
                key = key.replace('_', '-')
                self.props[key] = propvalue
                # property comments
                if comments:
                    self.comments[key] = comments


    def _line_is_glyph(self, value):
        """Text line is a glyph."""
        return value and (
            (value == self.empty)
            or not(set(value) - set((self.ink, self.paper, ' ', '\t', '\n')))
        )

    def _convert_glyph(self, keys, lines, striplines, comments):
        """Parse single glyph."""
        # find first indent
        # note we shouldn't have mixed indents.
        # skip leading empties
        indent = len(lines[0]) - len(lines[0].lstrip())
        is_glyph = tuple(self._line_is_glyph(_line) for _line in striplines)
        # find first property row
        try:
            first_prop = is_glyph.index(False)
        except ValueError:
            first_prop = len(striplines)
        glyph_lines = striplines[:first_prop]
        prop_lines = lines[first_prop:]
        if glyph_lines == (self.empty,):
            glyph_lines = ()
        # new text reader on glyph property lines
        reader = TextReader(indent)
        # set fields so we have a .yaff or .draw reader
        reader.separator = self.separator
        reader.comment = self.comment
        reader.whitespace = self.whitespace
        for line in prop_lines:
            reader.step(line)
        # recursive call
        # ignore in-glyph comments
        props = self._convert_from(reader).props
        # labels
        # only necessary to support .draw at this stage
        # yaff labels handled by Glyph
        keys = tuple(self.convert_key(_key) for _key in keys)
        glyph = Glyph(
            glyph_lines, _0=self.paper, _1=self.ink,
            labels=keys, comment=comments, **vars(props)
        )
        return glyph

    def _convert_value(self, value):
        """Strip matching double quotes on a per-line basis."""
        return '\n'.join(strip_matching(_line, '"') for _line in value.splitlines())

    @classmethod
    def _clean_comment(self, comment):
        """Remove common leading space from comment."""
        # normalise single leading space
        lines = comment.splitlines()
        lines = tuple(
            _line[len(self.comment):] if _line.startswith(self.comment) else _line
            for _line in lines
        )
        return normalise_comment(lines)


def normalise_comment(lines):
    """Remove common single leading space"""
    if all(_line.startswith(' ') for _line in lines if _line):
        return '\n'.join(_line[1:] for _line in lines)
    return '\n'.join(lines)


class YaffConverter(YaffParams, TextConverter):
    """Converter for .yaff files."""


##############################################################################
##############################################################################
# write file

class TextWriter:

    # override these by inheriting a params class
    separator: str
    comment: str
    tab: str
    separator_space: str

    ink: str
    paper: str
    empty: str

    def _write_glyph(self, outstream, glyph, label=None):
        """Write out a single glyph in text format."""
        # glyph comments
        if glyph.comment:
            outstream.write('\n' + format_comment(glyph.comment, self.comment) + '\n')
        if label:
            labels = [label]
        else:
            labels = glyph.get_labels()
        if not labels:
            logging.debug('No labels for glyph: %s', glyph)
            outstream.write(f'{self.separator}{self.separator_space}')
        for _label in labels:
            outstream.write(f'{str(_label)}{self.separator}{self.separator_space}')
        # glyph matrix
        # empty glyphs are stored as 0x0, not 0xm or nx0
        if not glyph.width or not glyph.height:
            glyphtxt = f'{self.tab}{self.empty}\n'
        else:
            glyphtxt = glyph.as_text(
                start=self.tab, ink=self.ink, paper=self.paper, end='\n'
            )
        outstream.write(glyphtxt)
        if glyph.properties:
            outstream.write(f'\n')
        for key, value in glyph.properties.items():
            self._write_property(outstream, key, value, None, indent=self.tab)
        if glyph.properties:
            outstream.write('\n')
        outstream.write('\n')

    def _write_property(self, outstream, key, value, comments, indent=''):
        """Write out a property."""
        if value is None:
            return
        # this may use custom string converter (e.g codepoint labels)
        value = str(value)
        # write property comment
        if comments:
            outstream.write(f'\n{indent}' + format_comment(comments) + '\n', self.comment)
        if not key.startswith('_'):
            key = key.replace('_', '-')
        # write key-value pair
        if '\n' not in value:
            outstream.write(f'{indent}{key}: {self._quote_if_needed(value)}\n')
        else:
            outstream.write(
                f'{indent}{key}:\n{indent}{self.tab}' + '{}\n'.format(
                    f'\n{indent}{self.tab}'.join(
                        self._quote_if_needed(_line)
                        for _line in value.splitlines()
                    )
                )
            )

    def _quote_if_needed(self, value):
        """See if string value needs double quotes."""
        value = str(value)
        if (
                (value.startswith('"') and value.endswith('"'))
                # leading or trailing space
                or value[:1].isspace() or value[-1:].isspace()
                # anything that could be mistaken for a glyph
                or all(_c in (self.ink, self.paper, self.empty) for _c in value)
            ):
            return f'"{value}"'
        return value


def format_comment(comments, comment_char):
    """Format a multiline comment."""
    return '\n'.join(
        f'{comment_char} {_line}'
        for _line in comments.splitlines()
    )


class YaffWriter(TextWriter, YaffParams):

    def save(self, fonts, outstream):
        """Write fonts to a plaintext stream as yaff."""
        for number, font in enumerate(fonts):
            if len(fonts) > 1:
                outstream.write(BOUNDARY_MARKER + '\n')
            logging.debug('Writing %s to section #%d', font.name, number)
            # write global comment
            if font.get_comment():
                outstream.write(format_comment(
                    font.get_comment() + '\n\n',
                    self.comment
                ))
            # we always output name, font-size and spacing
            # plus anything that is different from the default
            props = {
                'name': font.name,
                'spacing': font.spacing,
            }
            if font.spacing in ('character-cell', 'multi-cell'):
                props['cell_size'] = font.cell_size
            else:
                props['bounding_box'] = font.bounding_box
            props.update(font.properties)
            if props:
                # write recognised yaff properties first, in defined order
                for key, value in props.items():
                    self._write_property(outstream, key, value, font.get_comment(key))
                outstream.write('\n')
            for glyph in font.glyphs:
                self._write_glyph(outstream, glyph)
