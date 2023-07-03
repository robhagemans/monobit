"""
monobit.formats.text.yaff - monobit-yaff format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from dataclasses import dataclass, field
from itertools import count, zip_longest
from collections import deque
from functools import cached_property

from ...storage import loaders, savers
from ...encoding import charmaps
from ...magic import FileFormatError
from ...font import Font, FontProperties
from ...glyph import Glyph
from ...raster import Raster
from ...labels import Label, strip_matching
from ...properties import Props
from ...basetypes import Coord, passthrough
from .draw import NonEmptyBlock, DrawComment, Empty, Unparsed, iter_blocks
from .draw import format_comment


##############################################################################
# interface

@loaders.register(
    name='yaff',
    # maybe, if multi-section
    magic=(b'---',),
    patterns=('*.yaff', '*.yaffs',),
)
def load_yaff(instream, allow_empty:bool=False):
    """
    Load font from a monobit .yaff file.

    allow_empty: allow files with no glyphs (default: False)
    """
    return _load_yaffs(instream.text, allow_empty)


@savers.register(
    linked=load_yaff,
)
def save_yaff(fonts, outstream):
    """Write fonts to a monobit .yaff file."""
    _save_yaff(fonts, outstream.text)


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
    # tuple of individual chars, need to be separate for startswith
    whitespace = tuple(' \t')

    # third-pass constants
    ink = '@'
    paper = '.'
    empty = '-'

    # string to be quoted if one of these chars at start and/or end
    quotable = (':', ' ')
    glyphchars = (ink, paper, empty)


# deprecated compatibility synonymms
_DEPRECATED_SYNONYMS = {
    'kern_to': 'right_kerning',
    'tracking': 'right_bearing',
    'offset': ('left_bearing', 'shift_up'),

    'average_advance': 'average_width',
    'max_advance': 'max_width',
    'cap_advance': 'cap_width',
}
def _set_property(propsdict, key, value):
    try:
        key = _DEPRECATED_SYNONYMS[key]
    except KeyError:
        pass
    if isinstance(key, tuple):
        for key, value in zip(key, Coord.create(value)):
            propsdict[key] = value
    else:
        propsdict[key] = value


##############################################################################
# read file


def _load_yaffs(text_stream, allow_empty):
    """Parse a yaff or yaffs file."""
    fonts = []
    reader = SectionIterator(text_stream)
    while not reader.eof:
        font = _read_yaff(reader)
        # if no glyphs, ignore it - may not be yaff at all
        if font.glyphs or allow_empty:
            fonts.append(font)
    return fonts


class SectionIterator:

    def __init__(self, textstream):
        self._stream = textstream
        self.eof = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.eof:
            raise StopIteration()
        line = self._stream.readline()
        if not line:
            self.eof = True
            raise StopIteration()
        if line[:3] == BOUNDARY_MARKER:
            raise StopIteration()
        else:
            return line


def _read_yaff(text_stream):
    """Parse a monobit yaff file."""
    blocktypes = (
        YaffComment, YaffProperty, YaffGlyph, YaffPropertyOrGlyph,
        Empty, Unparsed
    )
    glyphs = []
    font_comments = []
    font_props = {}
    font_prop_comms = {}
    current_comment = []
    for block in iter_blocks(text_stream, blocktypes):
        if isinstance(block, (YaffGlyph, YaffPropertyOrGlyph)) and block.is_glyph():
            glyphs.append(block.get_glyph_value() | Props(
                comment='\n\n'.join(current_comment),
            ))
            current_comment = []
        elif isinstance(block, (YaffProperty, YaffPropertyOrGlyph)):
            key = block.get_key()
            value = block.get_value()
            _set_property(font_props, key, value)
            font_prop_comms[key] = '\n\n'.join(current_comment)
            current_comment = []
        if not glyphs and not font_props:
            font_comments.extend(current_comment)
            current_comment = []
        if isinstance(block, YaffComment):
            current_comment.append(block.get_value())
        elif not isinstance(block, (YaffProperty, YaffGlyph, YaffPropertyOrGlyph)):
            logging.debug('Unparsed lines: %s', block.get_value())
    font_comments.extend(current_comment)
    # construct glyphs, including path-only glyphs
    glyphs = (
        Glyph(**vars(_g)) if _g.pixels or not hasattr(_g, 'path')
        else Glyph.from_path(**vars(_g - 'pixels'))
        for _g in glyphs
    )
    return Font(
        glyphs, **font_props,
        comment={'': '\n\n'.join(font_comments), **font_prop_comms},
    )


class YaffComment(DrawComment):

    def starts(self, line):
        return line[:1] == YaffParams.comment


class YaffMultiline(NonEmptyBlock, YaffParams):

    def __init__(self, line):
        self.indent = 0
        super().__init__(line)

    def ends(self, line):
        if self.indent:
            # dedent
            return line and line[:1] not in self.whitespace
        if line and line[:1] in self.whitespace:
            return False
        # gather multiple labels without values, but break on line with value
        return line.rstrip()[-1:] != self.separator

    def append(self, line):
        line = line.rstrip()
        self.lines.append(line)
        if not self.indent and line and line[:1] in self.whitespace:
            self.indent = len(line) - len(line.lstrip())


class YaffGlyph(YaffMultiline):

    label_chars = tuple('"' + "'" + string.digits)

    def starts(self, line):
        return line and (line[:1] in self.label_chars) or '+' in line

    def get_value(self):
        labels = tuple(_l[:-1] for _l in self.lines[:self.n_keys])
        lines = (_l[self.indent:] for _l in self.lines[self.n_keys:])
        lines = tuple(_l for _l in lines if _l)
        # locate glyph properties
        i = 0
        for i, line in enumerate(lines):
            if line[:1] not in (self.paper, self.ink) and set(line) != set(self.empty):
                break
        else:
            i += 1
        raster = lines[:i]
        properties = {}
        key = None
        for line in lines[i:]:
            if line[:1] in self.whitespace:
                # follow-up lines in multiline glyph properties
                # note - won't work with deprecated synonyms
                if not properties[key]:
                    properties[key] = line.strip()
                else:
                    properties[key] = '\n'.join((properties[key], line.strip()))
            else:
                # first line of property
                # one-line glyph properties
                key, _, value = line.partition(self.separator)
                key = normalise_property(key)
                value = value.strip()
                _set_property(properties, key, value)
        # deal with sized empties (why?)
        if all(set(_line) == set([self.empty]) for _line in raster):
            raster = Raster.blank(width=len(raster[0])-1, height=len(raster)-1)
        return Props(
            pixels=Raster(raster, _0=self.paper, _1=self.ink),
            labels=labels, **properties
        )

    def _count_keys(self):
        return sum(
            _line[-1:] == self.separator and _line[:1] not in self.whitespace
            for _line in self.lines
        )
    n_keys = cached_property(_count_keys)

    def is_glyph(self):
        return True

    get_glyph_value = get_value



def normalise_property(field):
    # preserve distinction between starting underscore (internal) and starting dash (user property)
    return field.replace('-', '_')


# keywords that take a label value
# these need special treatment as quotes must not be stripped
_LABEL_VALUED_KEYS = tuple(
    _k for _k, _v in FontProperties.__annotations__.items() if _v == Label
)


class YaffProperty(NonEmptyBlock, YaffParams):

    def starts(self, line):
        return (
            line[:1] not in self.whitespace
            and line[-1:] != self.separator
            and self.separator in line
        )

    def get_value(self):
        key, _, value = self.lines[0].partition(self.separator)
        # label values need special treatment as quotes must not be stripped
        if key in _LABEL_VALUED_KEYS:
            return value
        return _strip_quotes(value)

    def get_key(self):
        key, _, _ = self.lines[0].partition(self.separator)
        return normalise_property(key)


def _strip_quotes(line):
    line = line.strip()
    if len(line) > 1 and line[0] == line[-1] == '"':
        return line[1:-1]
    return line


class YaffPropertyOrGlyph(YaffMultiline):

    def starts(self, line):
        return line[:1] not in self.whitespace and line[-1:] == self.separator

    def get_value(self):
        return '\n'.join(_strip_quotes(_l) for _l in self.lines[1:])

    def get_key(self):
        return normalise_property(self.lines[0][:-1])

    # glyph block with plain label

    get_glyph_value = YaffGlyph.get_value
    n_keys = cached_property(YaffGlyph._count_keys)

    def is_glyph(self):
        if self.n_keys > 1:
            return True
        # n_keys == 1, so first non-key line is 1
        first = self.lines[1].lstrip()
        # multiline block with single key
        # may be property or (deprecated) glyph with plain label
        # we need to check the contents
        return first[:1] in (self.ink, self.paper) or set(first) == set(self.empty)


##############################################################################
# write file

def globalise_glyph_metrics(glyphs):
    """If all glyph props are equal, take them global."""
    properties = {}
    for key in (
            'shift_up', 'left_bearing', 'right_bearing',
            'shift_left', 'top_bearing', 'bottom_bearing',
            'scalable_width',
        ):
        distinct = set(_g.get_defined(key) for _g in glyphs)
        if len(distinct) == 1:
            value = distinct.pop()
            if value is not None:
                properties[key] = value
    return properties


def _save_yaff(fonts, outstream):
    """Write fonts to a plaintext stream as yaff."""
    for number, font in enumerate(fonts):
        if len(fonts) > 1:
            outstream.write(BOUNDARY_MARKER + '\n')
        logging.debug('Writing %s to section #%d', font.name, number)
        # write global comment
        if font.get_comment():
            outstream.write(
                format_comment(font.get_comment(), YaffParams.comment)
                + '\n\n'
            )
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
        props.update(font.get_properties())
        global_metrics = globalise_glyph_metrics(font.glyphs)
        # keep only nonzero or non-default globalised properties
        props.update({
            _k: _v for _k, _v in global_metrics.items()
            if _v or _v != Glyph.get_default(_k)
        })
        if props:
            # write recognised yaff properties first, in defined order
            for key, value in props.items():
                if value != font.get_default(key):
                    _write_property(outstream, key, value, font.get_comment(key))
            outstream.write('\n')
        for glyph in font.glyphs:
            _write_glyph(outstream, glyph, global_metrics)

def _write_glyph(outstream, glyph, global_metrics):
    """Write out a single glyph in text format."""
    # glyph comments
    if glyph.comment:
        outstream.write(
            '\n' + format_comment(glyph.comment, YaffParams.comment) + '\n'
        )
    labels = glyph.get_labels() or ['']
    for _label in labels:
        outstream.write(f'{str(_label)}{YaffParams.separator}\n')
    # glyph matrix
    # empty glyphs are stored as 0x0, not 0xm or nx0
    if not glyph.pixels.width or not glyph.pixels.height:
        glyphtxt = f'{YaffParams.tab}{YaffParams.empty}\n'
    else:
        glyphtxt = glyph.pixels.as_text(
            start=YaffParams.tab,
            ink=YaffParams.ink, paper=YaffParams.paper,
            end='\n'
        )
    outstream.write(glyphtxt)
    properties = glyph.get_properties()
    for key in global_metrics:
        properties.pop(key, None)
    if properties:
        outstream.write(f'\n')
    for key, value in properties.items():
        if value != glyph.get_default(key):
            _write_property(outstream, key, value, None, indent=YaffParams.tab)
    if properties:
        outstream.write('\n')
    outstream.write('\n')

def _write_property(outstream, key, value, comments, indent=''):
    """Write out a property."""
    if value is None:
        return
    # write property comment
    if comments:
        outstream.write(
            f'\n{indent}{format_comment(comments, YaffParams.comment)}\n'
        )
    key = key.replace('_', '-')
    # write key-value pair
    if isinstance(value, Label) or not isinstance(value, str):
        # do not quote converted non-strings (plus Tag and Char which are str)
        # note that these need special treatment in the reader, or it
        # will strip quotes and misinterpret some labels
        # so non-ascii or single-char tags will be converted to Char not Tag
        quoter = passthrough
    else:
        quoter = _quote_if_needed
    value = str(value)
    if '\n' not in value:
        outstream.write(f'{indent}{key}: {quoter(value)}\n')
    else:
        outstream.write(
            f'{indent}{key}:\n{indent}{YaffParams.tab}' + '{}\n'.format(
                f'\n{indent}{YaffParams.tab}'.join(
                    quoter(_line) for _line in value.splitlines()
                )
            )
        )

def _quote_if_needed(value):
    """See if string value needs double quotes."""
    value = str(value)
    if (
            not value
            or value[0] in YaffParams.quotable
            or value[-1] in YaffParams.quotable
            or value[0] == value[-1] == '"'
            or all(_c in YaffParams.glyphchars for _c in value)
        ):
        return f'"{value}"'
    return value
