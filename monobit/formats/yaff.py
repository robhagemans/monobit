"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from types import SimpleNamespace
from itertools import count, zip_longest
from collections import deque

from ..matrix import to_text
from ..storage import loaders, savers
from ..encoding import charmaps
from ..streams import FileFormatError
from ..font import PROPERTIES, Font
from ..glyph import Glyph
from ..label import strip_matching, label
from ..label import Char, Codepoint, Tag, Label
from ..struct import Props


##############################################################################
# format parameters

_WHITESPACE = ' \t'
_CODESTART = _WHITESPACE + string.digits + string.ascii_letters + '_-."'

BOUNDARY_MARKER = '---'


##############################################################################


@loaders.register('yaff', 'yaffs', magic=(b'---',), name='monobit-yaff')
def load_yaff(instream, where=None):
    """Load font from a monobit .yaff file."""
    return _load_yaff(instream.text)

@savers.register(linked=load_yaff)
def save_yaff(fonts, outstream, where=None):
    """Write fonts to a monobit .yaff file."""
    YaffWriter().save(fonts, outstream.text)


@loaders.register('draw', 'text', 'txt', name='hexdraw')
def load_draw(instream, where=None, ink='#', paper='-'):
    """
    Load font from a hexdraw file.

    ink: character used for inked/foreground pixels
    paper: character used for uninked/background pixels
    """
    return _load_draw(instream.text, _ink=ink, _paper=paper)

@savers.register(linked=load_draw)
def save_draw(fonts, outstream, where=None, ink='#', paper='-'):
    """
    Save font to a hexdraw file.

    ink: character to use for inked/foreground pixels
    paper: character to use for uninked/background pixels
    """
    if len(fonts) > 1:
        raise FileFormatError("Can only save one font to hexdraw file.")
    DrawWriter(ink=ink, paper=paper).save(fonts[0], outstream.text)


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


def _load_draw(text_stream, _ink='', _paper=''):
    """Parse a yaff/yaffs file."""

    class _Converter(DrawConverter):
        ink=_ink or DrawConverter.ink
        paper=_paper or DrawConverter.paper

    reader = DrawReader()
    for line in text_stream:
        reader.step(line)
    return _Converter.get_font_from(reader)


class TextReader:
    """Parser for text-based font file."""

    # first/second pass constants
    separator = ':'
    comment = '#'
    # tuple of individual chars, need to be separate for startswith
    whitespace = tuple(' \t')

    def __init__(self):
        """Set up text reader."""
        # current element appending to
        self._current = ''
        # elements done
        self._elements = deque()

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
            # new key
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
                new_first = comments[:-1]
                new_second = [comments[-1], *others]
                clusters = [new_first, new_second, *clusters[1:]]
        return clusters


class TextConverter:
    """Convert text clusters to font."""

    # first/second pass constants
    separator = ':'
    comment = '#'

    # third-pass constants
    ink = '@'
    paper = '.'
    empty = '-'
    # convert key string to key object
    convert_key = staticmethod(label)

    # third pass: interpret clusters

    def __init__(self):
        """Set up converter."""
        self.props = Props()
        self.glyphs = []

    @classmethod
    def get_font_from(cls, reader):
        """Get clusters from reader and convert to Font."""
        props, glyphs = cls.convert_from(reader)
        return Font(glyphs=glyphs, properties=vars(props))

    @classmethod
    def convert_from(cls, reader):
        """Get clusters from reader and convert."""
        clusters = reader.get_clusters()
        # recursive call
        converter = cls()
        for cluster in clusters:
            converter.convert_cluster(cluster)
        return converter.props, converter.glyphs

    def convert_cluster(self, cluster):
        """Convert cluster."""
        # keys
        keys = tuple(
            _elem[:-len(self.separator)].strip()
            for _elem in cluster
            if _elem.endswith(self.separator)
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
            self.props[Font.comment_prefix] = comments
            return
        value, = values
        # if any line in the value has only glyph symbols, this cluster is a glyph
        is_glyph = value and any(_line for _line in value.splitlines() if self._line_is_glyph(_line))
        if is_glyph:
            keys = tuple(self.convert_key(_key) for _key in keys)
            chars = tuple(_key for _key in keys if isinstance(_key, Char))
            codepoints = tuple(_key for _key in keys if isinstance(_key, Codepoint))
            tags = tuple(_key for _key in keys if isinstance(_key, Tag))
            glyph = self._convert_glyph(value)
            # duplicate glyphs if we have multiple chars or codepoints
            self.glyphs.extend(
                glyph.modify(char=char, codepoint=cp, tags=tags, comments=comments)
                for char, cp, _ in zip_longest(chars, codepoints, [None], fillvalue=None)
            )
        else:
            # multiple labels translate into multiple keys with the same value
            for key in keys:
                self.props[key] = '\n'.join(_line for _line in value.splitlines() if _line)
                # property comments
                if comments:
                    self.props[Font.comment_prefix + key] = comments


    def _line_is_glyph(self, value):
        """Text line is a glyph."""
        value = value.strip()
        return value and (
            (value == self.empty)
            or not(set(value) - set(self.ink) - set(self.paper))
        )

    def _convert_glyph(self, value):
        """Parse single glyph."""
        lines = value.splitlines()
        glyph_lines = [
            _line.strip() for _line in lines
             if self._line_is_glyph(_line)
        ]
        if not glyph_lines:
            raise ValueError('Not a glyph definition.')
        elif glyph_lines == [self.empty]:
            glyph = Glyph()
        else:
            glyph = Glyph.from_matrix(glyph_lines, paper=self.paper)
        # glyph properties
        prop_lines = [
            _line for _line in lines
             if not self._line_is_glyph(_line)
        ]
        # new text reader on glyph property lines
        reader = TextReader()
        for line in prop_lines:
            reader.step(line)
            # recursive call
        props, glyphs = self.convert_from(reader)
        # ignore in-glyph comments
        props = {
            _k: _v
            for _k, _v in vars(props).items()
            if not _k.startswith('_')
        }
        glyph = glyph.modify(**props)
        return glyph

    def _convert_value(self, value):
        """Strip matching double quotes on a per-line basis."""
        return '\n'.join(strip_matching(_line, '"') for _line in value.splitlines())

    def _clean_comment(self, comment):
        """Remove common leading space from comment."""
        # normalise single leading space
        lines = comment.splitlines()
        lines = tuple(
            _line[len(self.comment):] if _line.startswith(self.comment) else _line
            for _line in lines
        )
        if all(_line.startswith(' ') for _line in lines if _line):
            return '\n'.join(_line[1:] for _line in lines)
        return '\n'.join(lines)


##############################################################################

class YaffParams:
    """Parameters for .yaff format."""

    # first/second pass constants
    separator = ':'
    comment = '#'
    # output only
    tab = '    '
    # tuple of individual chars, need to be separate for startswith
    whitespace = tuple(' \t')

    # third-pass constants
    ink = '@'
    paper = '.'
    empty = '-'
    # convert key string to key object
    convert_key = label


class YaffReader(TextReader, YaffParams):
    """Reader for .yaff files."""

class YaffConverter(TextConverter, YaffParams):
    """Converter for .yaff files."""


##############################################################################

class DrawParams:
    """Parameters for .draw format."""

    # first/second pass constants
    separator = ':'
    comment = '%'
    # output only
    tab = '\t'
    # tuple of individual chars, need to be separate for startswith
    whitespace = tuple(' \t')

    # third-pass constants
    ink = '#'
    paper = '-'
    empty = '-'

    @staticmethod
    def convert_key(keys):
        """Convert keys on input from .draw."""
        kwargs = dict(
            char='',
            codepoint=(),
            tags=(),
        )
        # only one key allowed in .draw, rest ignored
        key = keys[0]
        try:
            kwargs['char'] = chr(int(key, 16))
        except (TypeError, ValueError):
            kwargs['tags'] = [key]
        return kwargs


class DrawReader(TextReader, DrawParams):
    """Reader for .draw files."""


class DrawConverter(TextConverter, DrawParams):
    """Converter for .draw files."""


##############################################################################
##############################################################################
# write file


class TextWriter:

    separator = ':'
    comment = '#'
    tab = '    '

    ink = '@'
    paper = '.'
    empty = '-'

    def _write_glyph(self, outstream, glyph, label=None, suppress_codepoint=False):
        """Write out a single glyph in text format."""
        # glyph comments
        if glyph.comments:
            outstream.write('\n' + self._format_comment(glyph.comments))
        if label:
            labels = [label]
        else:
            labels = glyph.get_labels(suppress_codepoint=suppress_codepoint)
        if not labels:
            logging.warning('No labels for glyph: %s', glyph)
            return
        for _label in labels:
            outstream.write(f'{_label}{self.separator}\n')
        # glyph matrix
        # empty glyphs are stored as 0x0, not 0xm or nx0
        if not glyph.width or not glyph.height:
            glyphtxt = self.empty
        else:
            glyphtxt = to_text(
                glyph.as_matrix(),
                ink=self.ink, paper=self.paper, line_break='\n' + self.tab
            )
        tab = self.tab
        outstream.write(f'{tab}{glyphtxt}\n\n')
        # glyph properties
        if glyph.offset:
            outstream.write(f'{tab}offset: {str(glyph.offset)}\n')
        if glyph.tracking:
            outstream.write(f'{tab}tracking: {str(glyph.tracking)}\n')
        if glyph.kern_to:
            outstream.write(f'{tab}kern-to: \n')
            for line in str(glyph.kern_to).splitlines():
                outstream.write(f'{tab*2}{line}\n')
        for key, value in glyph.properties.items():
            outstream.write(f'{tab}{key}: {self._quote_if_needed(value)}\n')
        if glyph.offset or glyph.tracking or glyph.kern_to or glyph.properties:
            outstream.write('\n')
        outstream.write('\n')

    def _write_property(self, outstream, key, value, comments):
        """Write out a property."""
        if value is None:
            return
        # this may use custom string converter (e.g codepoint labels)
        value = str(value)
        if not value:
            return
        # write property comment
        if comments:
            outstream.write('\n' + self._format_comment(comments))
        # write key-value pair
        if '\n' not in value:
            outstream.write(f'{key}: {self._quote_if_needed(value)}\n')
        else:
            outstream.write(
                f'{key}:\n{self.tab}' '{}\n'.format(
                    f'\n{self.tab}'.join(
                        self._quote_if_needed(_line)
                        for _line in value.splitlines()
                    )
                )
            )

    def _format_comment(self, comments):
        """Format a multiline comment."""
        return '\n'.join(f'{self.comment} {_line}' for _line in comments.splitlines())

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


class YaffWriter(TextWriter, YaffParams):

    def save(self, fonts, outstream):
        """Write fonts to a plaintext stream as yaff."""
        for number, font in enumerate(fonts):
            if len(fonts) > 1:
                outstream.write(BOUNDARY_MARKER + '\n')
            logging.debug('Writing %s to section #%d', font.name, number)
            # write global comment
            if font.get_comments():
                outstream.write(self._format_comment(font.get_comments()) + '\n')
            # we always output name, font-size and spacing
            # plus anything that is different from the default
            props = {
                'name': font.name,
                'spacing': font.spacing,
                **font.nondefault_properties
            }
            if font.spacing in ('character-cell', 'multi-cell'):
                props['raster-size'] = font.raster_size
            else:
                props['bounding-box'] = font.bounding_box
            if props:
                # write recognised yaff properties first, in defined order
                ordered_keys = [
                    *(_k for _k in PROPERTIES if _k in props),
                    *(_k for _k in props if _k not in PROPERTIES)
                ]
                ordered_props = {_k: props[_k] for _k in ordered_keys}
                for key in ordered_keys:
                    self._write_property(outstream, key, props[key], font.get_comments(key))
                outstream.write('\n')
            for glyph in font.glyphs:
                self._write_glyph(
                    outstream, glyph, suppress_codepoint=charmaps.is_unicode(font.encoding)
                )


class DrawWriter(TextWriter, DrawParams):

    def __init__(self, ink='', paper=''):
        self.ink = ink or self.ink
        self.paper = paper or self.paper

    def save(self, font, outstream):
        """Write one font to a plaintext stream as hexdraw."""
        # write global comment
        if font.get_comments():
            outstream.write(self._format_comment(font.get_comments()) + '\n')
        # write glyphs
        for glyph in font.glyphs:
            if len(glyph.char) > 1:
                logging.warning(
                    "Can't encode grapheme cluster %s in .draw file; skipping.",
                    Char(glyph.char)
                )
                continue
            self._write_glyph(outstream, glyph, label=f'{ord(glyph.char):04x}')
