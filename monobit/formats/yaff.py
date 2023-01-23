"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from dataclasses import dataclass, field
from itertools import count, zip_longest
from collections import deque

from ..storage import loaders, savers
from ..encoding import charmaps
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..labels import strip_matching
from ..properties import normalise_property


##############################################################################
# interface


@loaders.register('yaff', 'yaffs', magic=(b'---',), name='yaff')
def load_yaff(instream, where=None):
    """Load font from a monobit .yaff file."""
    return _load_yaff(instream.text)

@savers.register(linked=load_yaff)
def save_yaff(fonts, outstream, where=None):
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
    quotable = ('"', "'", ':', ' ')
    glyphchars = (ink, paper, empty)

##############################################################################
##############################################################################
# read file


def _load_yaff(text_stream):
    """Parse a yaff/yaffs file."""
    reader = YaffReader()
    fonts = []
    has_next_section = True
    while has_next_section:
        reader = YaffReader()
        has_next_section = reader.parse_section(text_stream)
        fonts.append(reader.get_font())
    return fonts


@dataclass
class YaffElement:
    keys: list = field(default_factory=list)
    value: list = field(default_factory=list)
    comment: list = field(default_factory=list)
    indent: int = 0


class YaffReader:
    """Parser for text-based font file."""

    def __init__(self):
        """Set up text reader."""
        # current element appending to
        # elements done
        self._elements = deque()

    # first pass: lines to elements

    def _yield_element(self, current):
        """Close and append current element and start a new one."""
        if current.keys or current.value or current.comment:
            self._elements.append(current)
        return YaffElement()

    def parse_section(self, text_stream):
        """Parse a single yaff section."""
        current = YaffElement()
        for line in text_stream:
            # strip trailing whitespace
            contents = line.rstrip()
            if contents == BOUNDARY_MARKER:
                self._yield_element(current)
                # ignore empty sections
                if self._elements:
                    return True
            if not contents:
                # ignore empty lines except while already parsing comments
                if (
                        current.comment
                        and not current.value
                        and not current.keys
                    ):
                    current.comment.append('')
            else:
                startchar = contents[:1]
                if startchar == YaffParams.comment:
                    if current.keys or current.value:
                        # new comment starts new element
                        current = self._yield_element(current)
                    current.comment.append(contents[1:])
                elif startchar not in YaffParams.whitespace:
                    if current.value:
                        # new key when we have a value starts a new element
                        current = self._yield_element(current)
                    # note that we don't use partition() for the first check
                    # as we have to allow for : inside (quoted) glyph labels
                    if contents[-1:] == YaffParams.separator:
                        current.keys.append(contents[:-1])
                    else:
                        # this must be a property key, not a glyph label
                        # new key, separate at the first :
                        # prop keys must be alphanum so no need to worry about quoting
                        key, sep, value = contents.partition(YaffParams.separator)
                        # yield key and value
                        # yaff does not allow multiline values starting on the key line
                        current.keys.append(key.rstrip())
                        current.value.append(value.lstrip())
                        current = self._yield_element(current)
                else:
                    # first line in value
                    if not current.value:
                        current.indent = len(contents) - len(contents.lstrip())
                    # continue building value
                    # do not strip all whitespace as we need it for multiline glyph props
                    # but strip the first line's indent
                    current.value.append(contents[current.indent:])
        self._yield_element(current)
        return False

    # second pass: top comment

    def get_clusters(self):
        """Convert top comment cluster and return."""
        clusters = self._elements
        # separate out global top comment
        if clusters and clusters[0]:
            top = clusters[0]
            comments = top.comment
            # find last empty line which separates global from prop comment
            try:
                index = len(comments) - comments[::-1].index('')
            except ValueError:
                index = len(comments) + 1
            if len(comments) > 1:
                global_comment = YaffElement(comment=comments[:index-1])
                top.comment = comments[index:]
                clusters.appendleft(global_comment)
        return clusters


    # third pass: interpret clusters

    def get_font(self):
        """Get clusters from reader and convert to Font."""
        clusters = self.get_clusters()
        # recursive call
        glyphs, props, comments = convert_clusters(clusters)
        return Font(glyphs, comment=comments, **props)


def convert_clusters(clusters):
    """Convert cluster."""
    props = {}
    comments = {}
    glyphs = []
    for cluster in clusters:
        if not cluster.keys:
            # global comment
            comments[''] = normalise_comment(cluster.comment)
        elif not set(cluster.value[0]) - set(YaffParams.glyphchars):
            # if first line in the value consists of glyph symbols, it's a glyph
            # note that the set diff is significantly faster than all() on a genexp
            glyphs.append(_convert_glyph(cluster))
        else:
            key, value, comment = convert_property(cluster)
            if value:
                props[key] = value
            # property comments
            if comment:
                comments[key] = comment
    return glyphs, props, comments

def convert_property(cluster):
    """Convert property cluster."""
    # there should not be multiple keys for a property
    key = cluster.keys.pop(0)
    if cluster.keys:
        logging.warning('ignored excess keys: %s', cluster.keys)
    # Props object converts only non-leading underscores
    # so we need to make sure we turn those into dashes
    key = key.replace('_', '-')
    value = '\n'.join(strip_matching(_line, '"') for _line in cluster.value)
    comment = normalise_comment(cluster.comment)
    return key, value, comment

def _convert_glyph(cluster):
    """Parse single glyph."""
    keys = cluster.keys
    lines = cluster.value
    comment = normalise_comment(cluster.comment)
    # find first property row
    # note empty lines have already been dropped by reader
    is_prop = tuple(YaffParams.separator in _line for _line in lines)
    try:
        first_prop = is_prop.index(True)
    except ValueError:
        first_prop = len(lines)
    raster = lines[:first_prop]
    prop_lines = lines[first_prop:]
    if all(set(_line) == set([YaffParams.empty]) for _line in raster):
        raster = Raster.blank(width=len(raster[0])-1, height=len(raster)-1)
    # new text reader on glyph property lines
    reader = YaffReader()
    reader.parse_section(prop_lines)
    # ignore in-glyph comments
    props = dict(
        convert_property(cluster)[:2]
        for cluster in reader.get_clusters()
        if cluster.keys
    )
    # labels
    glyph = Glyph(
        raster, _0=YaffParams.paper, _1=YaffParams.ink,
        labels=keys, comment=comment, **props
    )
    return glyph


def normalise_comment(lines):
    """Remove common single leading space"""
    if all(_line[0] == ' ' for _line in lines if _line):
        return '\n'.join(_line[1:] for _line in lines)
    return '\n'.join(lines)



##############################################################################
##############################################################################
# write file


def _globalise_glyph_metrics(mod_glyphs):
    """If all glyph props are equal, take them global."""
    properties = {}
    for key in (
            'shift-up', 'left-bearing', 'right-bearing',
            'shift-left', 'top-bearing', 'bottom-bearing',
        ):
        distinct = set(
            getattr(_g, normalise_property(key))
            for _g in mod_glyphs
        )
        if len(distinct) == 1:
            mod_glyphs = tuple(_g.drop(key) for _g in mod_glyphs)
            value = distinct.pop()
            # NOTE - these all have zero defaults
            if value != 0:
                properties[key] = value
    return mod_glyphs, properties


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
        props.update(font.properties)
        glyphs, global_metrics = _globalise_glyph_metrics(font.glyphs)
        props.update(global_metrics)
        if props:
            # write recognised yaff properties first, in defined order
            for key, value in props.items():
                _write_property(outstream, key, value, font.get_comment(key))
            outstream.write('\n')
        for glyph in glyphs:
            _write_glyph(outstream, glyph)

def _write_glyph(outstream, glyph, label=None):
    """Write out a single glyph in text format."""
    # glyph comments
    if glyph.comment:
        outstream.write(
            '\n' + format_comment(glyph.comment, YaffParams.comment) + '\n'
        )
    if label:
        labels = [label]
    else:
        labels = glyph.get_labels()
    if not labels:
        outstream.write(f'{YaffParams.separator}\n')
    for _label in labels:
        outstream.write(f'{str(_label)}{YaffParams.separator}\n')
    # glyph matrix
    # empty glyphs are stored as 0x0, not 0xm or nx0
    if not glyph.width or not glyph.height:
        glyphtxt = f'{YaffParams.tab}{YaffParams.empty}\n'
    else:
        glyphtxt = glyph.as_text(
            start=YaffParams.tab,
            ink=YaffParams.ink, paper=YaffParams.paper,
            end='\n'
        )
    outstream.write(glyphtxt)
    if glyph.properties:
        outstream.write(f'\n')
    for key, value in glyph.properties.items():
        _write_property(outstream, key, value, None, indent=YaffParams.tab)
    if glyph.properties:
        outstream.write('\n')
    outstream.write('\n')

def _write_property(outstream, key, value, comments, indent=''):
    """Write out a property."""
    if value is None:
        return
    # this may use custom string converter (e.g codepoint labels)
    value = str(value)
    # write property comment
    if comments:
        outstream.write(
            f'\n{indent}{format_comment(comments, YaffParams.comment)}\n'
        )
    if not key.startswith('_'):
        key = key.replace('_', '-')
    # write key-value pair
    if '\n' not in value:
        outstream.write(f'{indent}{key}: {_quote_if_needed(value)}\n')
    else:
        outstream.write(
            f'{indent}{key}:\n{indent}{YaffParams.tab}' + '{}\n'.format(
                f'\n{indent}{YaffParams.tab}'.join(
                    _quote_if_needed(_line)
                    for _line in value.splitlines()
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
            or all(_c in YaffParams.glyphchars for _c in value)
        ):
        return f'"{value}"'
    return value


def format_comment(comments, comment_char):
    """Format a multiline comment."""
    return '\n'.join(
        f'{comment_char} {_line}'
        for _line in comments.splitlines()
    )
