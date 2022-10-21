"""
monobit.font - representation of font

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from functools import wraps
from pathlib import PurePath
try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()

from .scripting import scriptable, get_scriptables, Any
from .glyph import Glyph, Coord, Bounds, number
from .encoding import charmaps, encoder
from .taggers import tagger
from .labels import Tag, Char, Codepoint, to_label
from .binary import ceildiv
from .struct import (
    extend_string, DefaultProps, normalise_property, as_tuple, writable_property, checked_property
)
from .taggers import tagmaps


# sentinel object
NOT_SET = object()


# pylint: disable=redundant-keyword-arg, no-member

###################################################################################################
# property management


# recognised yaff properties and converters from str
# this also defines the default order in yaff files
class FontProperties(DefaultProps):

    # naming - can be determined from source file if needed
    # full human name
    name: str
    # typeface/font family
    family: str

    # font metadata
    # can't be calculated
    # author or issuer
    author: str
    foundry: str
    # copyright string
    copyright: str
    # license string or similar
    notice: str
    # font version
    revision: str = '0'

    # font description
    # can't be calculated
    # serif, sans, etc.
    style: str
    # nominal point size
    point_size: number
    # normal, bold, light, ...
    weight: str = 'regular'
    # roman, italic, oblique, ...
    slant: str = 'roman'
    # normal, condensed, expanded, ...
    setwidth: str = 'normal'
    # underline, strikethrough, etc.
    decoration: str

    # target info
    # can't be calculated
    # target device name
    device: str
    # calculated or given
    # pixel aspect ratio - square pixel
    pixel_aspect: Coord.create = Coord(1, 1)
    # target resolution in dots per inch
    dpi: Coord.create

    # summarising quantities
    # determined from the bitmaps only

    # proportional, monospace, character-cell, multi-cell
    spacing: str
    # maximum raster (not necessarily ink) width/height
    raster_size: Coord.create
    # width, height of the character cell
    cell_size: Coord.create
    # overall ink bounds - overlay all glyphs with fixed origin and determine maximum ink extent
    bounding_box: Coord.create
    # average advance width, rounded to tenths
    average_width: number
    # maximum glyph advance width
    max_width: int
    # advance width of LATIN CAPITAL LETTER X
    cap_width: int
    # advance width of digits, if fixed.
    digit_width: int

    # descriptive typographic quantities
    # can be calculated or given, may affect rendering

    # height of lowercase x relative to baseline
    x_height: int
    # height of capital relative to baseline
    cap_height: int
    # can't be calculated, affect rendering (vertical positioning)
    # might affect e.g. composition of characters
    # recommended typographic ascent relative to baseline (not necessarily equal to top)
    ascent: int
    # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    descent: int
    # nominal pixel size, always equals ascent + descent
    pixel_size: int
    # vertical interline spacing, defined as line_height - pixel_size
    leading: int

    # metrics
    # can't be calculated, affect rendering

    # horizontal offset from leftward origin to matrix left edge
    left_bearing: int
    # horizontal offset from matrix right edge to rightward origin
    right_bearing: int
    # upward offset from origin to matrix bottom
    shift_up: int
    # downward offset from origin to matrix bottom - equal to -shift_up
    shift_down: int
    # vertical distance between consecutive baselines, in pixels
    line_height: int

    # vertical metrics
    # vertical offset from upward origin to matrix top edge
    top_bearing: int
    # vertical offset from matrix bottom edge to downward origin
    bottom_bearing: int
    # leftward offset from origin to matrix central vertical axis
    shift_left: int
    # horizontal distance between consecutive baselines, in pixels
    line_width: int

    # character properties
    # can't be calculated, affect rendering

    # character map, stored as normalised name
    encoding: charmaps.normalise
    # replacement for missing glyph
    default_char: to_label
    # word-break character (usually space)
    word_boundary: to_label = Char(' ')

    # rendering hints
    # may affect rendering if effects are applied

    # can be set to left-to-right, right-to-left to suggest a writing direction
    # though it is better determined through the bidirectional algorithm
    # the meaning of metrics is agnostic to writing direction
    direction: str = ''
    # number of pixels to smear in advance direction to simulate bold weight
    bold_smear: int = 1
    # number of pixels in underline
    # we don't implement the XLFD calculation based on average stem width
    underline_thickness: int = 1
    # position of underline below baseline. 0 means underline on baseline itself, 1 is one line below
    underline_descent: int
    # recommended superscript size in pixels.
    superscript_size: int
    # recommended subscript size in pixels.
    subscript_size: int
    # recommended superscript horizontal, vertical offset in pixels.
    superscript_offset: Coord.create
    # recommended subscript horizontal, vertical offset in pixels.
    subscript_offset: Coord.create
    # recommended small-capital size in pixels.
    small_cap_size: int
    # recommended space between words, in pixels
    word_space: int
    # recommended minimum space between words, in pixels
    min_word_space: int
    # recommended maximum space between words, in pixels
    max_word_space: int
    # recommended space between sentences, in pixels
    sentence_space: int

    # conversion metadata
    # can't be calculated, informational
    converter: str
    source_name: str
    source_format: str
    history: str


    @writable_property
    def name(self):
        """Full human-friendly name."""
        if self.slant == self._get_default('slant'):
            slant = ''
        else:
            # title-case
            slant = self.slant.title()
        if self.setwidth == self._get_default('setwidth'):
            setwidth = ''
        else:
            setwidth = self.setwidth.title()
        if (slant or setwidth) and self.weight == self._get_default('weight'):
            weight = ''
        else:
            weight = self.weight.title()
        if self.spacing in ('character-cell', 'multi-cell'):
            size = 'x'.join(str(_x) for _x in self.cell_size)
        else:
            size = str(self.point_size)
        return ' '.join(
            str(_x) for _x in (self.family, setwidth, weight, slant, size) if _x
        )

    @writable_property
    def family(self):
        """Name of font family."""
        # use source name if no family name defined
        stem = PurePath(self.source_name).stem
        # replace underscores with spaces
        stem = stem.replace('_', '-')
        # convert all-upper or all-lower to titlecase
        if stem == stem.upper() or stem == stem.lower():
            stem = stem.title()
        return stem

    @writable_property
    def foundry(self):
        """Author or issuer."""
        return self.author

    @writable_property
    def point_size(self):
        """Nominal point height."""
        # assume 72 points per inch (officially 72.27 pica points per inch)
        # if dpi not given assumes 72 dpi, so point-size == pixel-size
        return int(self.pixel_size * self.dpi.y / 72.)

    @writable_property
    def dpi(self):
        """Target screen resolution in dots per inch."""
        # if point-size has been overridden and dpi not set, determine from pixel-size & point-size
        if self._defined('point-size') is not None:
            dpi = (72 * self.pixel_size) // self.point_size
        else:
            # default: 72 dpi; 1 point == 1 pixel
            dpi = 72
        # stretch/shrink dpi.x if aspect ratio is not square
        return Coord((dpi*self.pixel_aspect.x)//self.pixel_aspect.y, dpi)

    ##########################################################################
    # metrics

    @checked_property
    def shift_down(self):
        """Downward shift - negative of shift-up."""
        return -self.shift_up


    @writable_property
    def line_height(self):
        """Vertical distance between consecutive baselines, in pixels."""
        if 'leading' in vars(self):
            return self.pixel_size + self.leading
        return self.pixel_size

    @writable_property
    def line_width(self):
        """Horizontal distance between consecutive baselines, in pixels."""
        return self.max_width


    ##########################################################################
    # typographic descriptors

    @writable_property
    def ascent(self):
        """Recommended typographic ascent relative to baseline (defaults to ink-top)."""
        if not self._font.glyphs:
            return 0
        return self.shift_up + max(
            _glyph.height - _glyph.padding.top
            for _glyph in self._font.glyphs
        )

    @writable_property
    def descent(self):
        """Recommended typographic descent relative to baseline (defaults to ink-bottom)."""
        if not self._font.glyphs:
            return 0
        # usually, descent is positive and offset is negative
        # negative descent would mean font descenders are all above baseline
        # padding is from raster edges, not in glyph coordines
        return - min(
            self.shift_up + _glyph.shift_up + _glyph.padding.bottom
            for _glyph in self._font.glyphs
        )

    @checked_property
    def pixel_size(self):
        """Get nominal pixel size (ascent + descent)."""
        return self.ascent + self.descent

    @writable_property
    def leading(self):
        """Vertical interline spacing, defined as (pixels between baselines) - (pixel size)."""
        return self.line_height - self.pixel_size

    ##########################################################################
    # summarising quantities

    @checked_property
    def spacing(self):
        """Monospace or proportional spacing."""
        # a _character-cell_ font is a font where all glyphs can be put inside an equal size cell
        # so that rendering the font becomes simply pasting in cells flush to each other. All ink
        # for a glyph must be inside the cell.
        #
        # this means that:
        # - all glyphs must have equal, positive advance width (except empty glyphs with advance zero).
        # - for each glyph, the advance is greater than or equal to the bounding box width.
        # - the line advance is greater than or equal to the font bounding box height.
        # - there is no kerning
        #
        # a special case is the _multi-cell_ font, where a glyph may take up 0, 1 or 2 cells.
        #
        # a _monospace_ font is a font where all glyphs have equal advance_width.
        #
        if not self._font.glyphs:
            return 'character-cell'
        if any(_glyph.advance_width < 0 or _glyph.right_kerning for _glyph in self._font.glyphs):
            return 'proportional'
        # don't count void glyphs (0 width and/or height) to determine whether it's monospace
        advances = set(_glyph.advance_width for _glyph in self._font.glyphs if _glyph.advance_width)
        monospaced = len(set(advances)) == 1
        bispaced = len(set(advances)) == 2
        ink_contained_y = self.line_height >= self.bounding_box.y
        ink_contained_x = all(
            _glyph.advance_width >= _glyph.bounding_box.x
            for _glyph in self._font.glyphs
        )
        if ink_contained_x and ink_contained_y:
            if monospaced:
                return 'character-cell'
            if bispaced:
                return 'multi-cell'
        if monospaced:
            return 'monospace'
        return 'proportional'

    @checked_property
    def raster(self):
        """Minimum box encompassing all glyph matrices overlaid at fixed origin, font origin coordinates."""
        if not self._font.glyphs:
            return Bounds(0, 0, 0, 0)
        lefts = tuple(_glyph.left_bearing for _glyph in self._font.glyphs)
        bottoms = tuple(_glyph.shift_up for _glyph in self._font.glyphs)
        rights = tuple(_glyph.left_bearing + _glyph.width for _glyph in self._font.glyphs)
        tops = tuple(_glyph.shift_up + _glyph.height for _glyph in self._font.glyphs)
        return Bounds(
            left=self.left_bearing + min(lefts),
            bottom=self.shift_up + min(bottoms),
            right=self.left_bearing + max(rights),
            top=self.shift_up + max(tops)
        )

    @checked_property
    def raster_size(self):
        """Minimum box encompassing all glyph matrices overlaid at fixed origin."""
        return Coord(
            self.raster.right - self.raster.left,
            self.raster.top - self.raster.bottom
        )

    @checked_property
    def cell_size(self):
        """Width, height of the character cell."""
        if self.spacing == 'proportional':
            return Coord(0, 0)
        # smaller of the (at most two) advance widths is the cell size
        # in a multi-cell font, some glyphs may take up two cells.
        cell_x = min(_glyph.advance_width for _glyph in self._font.glyphs if _glyph.advance_width)
        return Coord(cell_x, self.line_height)

    @checked_property
    def ink_bounds(self):
        """Minimum bounding box encompassing all glyphs at fixed origin, font origin cordinates."""
        nonempty = [
            _glyph for _glyph in self._font.glyphs
            if _glyph.bounding_box.x and _glyph.bounding_box.y
        ]
        if not nonempty:
            return Bounds(self.left_bearing, self.shift_up, self.left_bearing, self.shift_up)
        lefts, bottoms, rights, tops = zip(*(
            _glyph.ink_bounds
            for _glyph in nonempty
        ))
        return Bounds(
            left=self.left_bearing + min(lefts),
            bottom=self.shift_up + min(bottoms),
            right=self.left_bearing + max(rights),
            top=self.shift_up + max(tops)
        )

    @checked_property
    def bounding_box(self):
        """Dimensions of minimum bounding box encompassing all glyphs at fixed origin."""
        return Coord(
            self.ink_bounds.right - self.ink_bounds.left,
            self.ink_bounds.top - self.ink_bounds.bottom
        )

    @checked_property
    def padding(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        return Bounds(
            self.ink_bounds.left - self.raster.left,
            self.ink_bounds.bottom - self.raster_bottom,
            self.raster.right - self.ink_bounds.right,
            self.raster.top - self.ink_bounds.top,
        )

    @writable_property
    def average_width(self):
        """Get average glyph advance width."""
        if not self._font.glyphs:
            return self.left_bearing + self.right_bearing
        return (
            self.left_bearing
            + sum(_glyph.advance_width for _glyph in self._font.glyphs) / len(self._font.glyphs)
            + self.right_bearing
        )

    @writable_property
    def max_width(self):
        """Maximum glyph advance width."""
        if not self._font.glyphs:
            return self.left_bearing + self.right_bearing
        return (
            self.left_bearing
            + max(_glyph.advance_width for _glyph in self._font.glyphs)
            + self.right_bearing
        )

    @writable_property
    def cap_width(self):
        """Advance width of uppercase X."""
        try:
            return self._font.get_glyph(char='X').advance_width + self.left_bearing + self.right_bearing
        except KeyError:
            return 0

    @writable_property
    def x_height(self):
        """Ink height of lowercase x."""
        try:
            return self._font.get_glyph(char='x').bounding_box.y
        except KeyError:
            return 0

    @writable_property
    def cap_height(self):
        """Ink height of uppercase X."""
        try:
            return self._font.get_glyph(char='X').bounding_box.y
        except KeyError:
            return 0

    @writable_property
    def digit_width(self):
        """Advance width of digits, if fixed."""
        try:
            widths = set(
                self._font.get_glyph(char=_d).advance_width
                for _d in '$0123456789'
            )
        except KeyError:
            return 0
        if len(widths) == 1:
            return widths.pop()
        return 0


    ##########################################################################
    # rendering hints

    @writable_property
    def underline_descent(self):
        """
        Position of underline below baseline.
        0 means underline on baseline itself.
        """
        if not self._font.glyphs:
            return 0
        max_descent = -min(
            self.shift_up + _glyph.shift_up + _glyph.padding.bottom
            for _glyph in self._font.glyphs
        )
        # XLFD calculation says round(max_descent/2) but I think they mean this
        # they may meam something else with the 'top of the baseline'?
        return 1 + ceildiv(max_descent, 2)

    @writable_property
    def superscript_size(self):
        """Recommended superscript size in pixels."""
        return round(self.pixel_size * 0.6)

    @writable_property
    def superscript_offset(self):
        """Recommended superscript horizontal, vertical offset in pixels."""
        shift = round(self.pixel_size * 0.4)
        return Coord(shift, shift)

    @writable_property
    def subscript_size(self):
        """Recommended subscript size in pixels."""
        return round(self.pixel_size * 0.6)

    @writable_property
    def subscript_offset(self):
        """Recommended subscript horizontal, vertical offset in pixels."""
        shift = round(self.pixel_size * 0.4)
        return Coord(shift, shift)

    @writable_property
    def small_cap_size(self):
        """Recommended small-capital size in pixels."""
        return round(
            self.pixel_size * (
                (self.x_height + (self.cap_height - self.x_height) / 3)
                / self.cap_height
            )
        )

    @writable_property
    def word_space(self):
        """Recommended space between words, in pixels."""
        try:
            return self._font.get_glyph(char=' ').advance_width
        except KeyError:
            # convoluted XLFD calc just boils down to this?
            return round(self.pixel_size / 3)

    @writable_property
    def min_word_space(self):
        """Recommended minimum space between words, in pixels."""
        return round(0.75 * self.word_space)

    @writable_property
    def max_word_space(self):
        """Recommended maximum space between words, in pixels."""
        return round(1.5 * self.word_space)

    @writable_property
    def sentence_space(self):
        """Recommended space between sentences, in pixels."""
        return self.word_space


    ##########################################################################
    # character properties

    @writable_property
    def default_char(self):
        """Label for default character."""
        repl = '\ufffd'
        # TODO - make a font.chars property returning the keys object
        if repl not in self._font._chars:
            repl = ''
        return Char(repl)


    ##########################################################################
    # deprecated compatibility synonyms

    @writable_property('right_bearing')
    def tracking(self):
        """
        Horizontal offset from matrix right edge to rightward origin
        Deprecated synonym for right-bearing.
        """
        return self.right_bearing

    @as_tuple(('left_bearing', 'shift_up'), tuple_type=Coord.create)
    def offset(self):
        """
        (horiz, vert) offset from origin to matrix start
        Deprecated synonym for left-bearing, shift-up.
        """

    @writable_property('average_width')
    def average_advance(self):
        """Average advance width, rounded to tenths."""
        return self.average_width

    @writable_property('max_width')
    def max_advance(self):
        """Maximum glyph advance width."""
        return self.max_width

    @writable_property('cap_width')
    def cap_advance(self):
        """Advance width of LATIN CAPITAL LETTER X."""
        return self.cap_width


###################################################################################################
# Font class


class Font:
    """Representation of font glyphs and metadata."""

    def __init__(self, glyphs=(), *, comment=None, **properties):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        # construct lookup tables
        self._tags = {
            _tag: _index
            for _index, _glyph in enumerate(self._glyphs)
            for _tag in _glyph.tags
        }
        self._codepoints = {
            _glyph.codepoint: _index
            for _index, _glyph in enumerate(self._glyphs)
            if _glyph.codepoint
        }
        self._chars = {
            _glyph.char: _index
            for _index, _glyph in enumerate(self._glyphs)
            if _glyph.char
        }
        # comment can be str (just global comment) or mapping of property comments
        if not comment:
            pass
        elif isinstance(comment, str):
            properties['#'] = comment
        else:
            properties.update({f'#{_k}': _v for _k, _v in comment.items()})
        # update properties
        # set encoding first so we can set labels
        # NOTE - we must be careful NOT TO ACCESS CACHED PROPERTIES
        #        until the constructor is complete
        self._props = FontProperties(_font=self, **properties)


    ##########################################################################
    # representation

    def __repr__(self):
        """Representation."""
        elements = (
            f'glyphs=(...{len(self._glyphs)} glyphs...)' if self.glyphs else '',
            ',\n    '.join(f'{_k}={repr(_v)}' for _k, _v in self.properties.items()),
        )
        return '{}({})'.format(
            type(self).__name__,
            ', '.join(_e for _e in elements if _e)
        )


    ##########################################################################
    # copying

    def modify(
            self, glyphs=NOT_SET, *,
            comment=NOT_SET, **kwargs
        ):
        """Return a copy of the font with changes."""
        if glyphs is NOT_SET:
            glyphs = self._glyphs
        old_comment = self._get_comment_dict()
        if isinstance(comment, str):
            old_comment[''] = comment
        elif comment is not NOT_SET:
            old_comment.update(comment)
        # comment and properties are replaced keyword by keyword
        return type(self)(
            tuple(glyphs),
            comment=old_comment,
            **{**self.properties, **kwargs}
        )

    def append(
            self, glyphs=(), *,
            comment=None, **properties
        ):
        """Return a copy of the font with additions."""
        if not comment:
            comment = {}
        for key, comment in comment.items():
            old_comment = self.get_comment(key)
            if old_comment:
                comment[key] = extend_string(old_comment, comment)
        for key, value in properties.items():
            if key in self._props:
                properties[key] = extend_string(self._props[key], value)
        return self.modify(
            self._glyphs + tuple(glyphs),
            comment={**comment},
            **properties
        )

    def drop(self, *args):
        """Remove glyphs, comments or properties."""
        args = list(args)
        try:
            args.remove('glyphs')
            glyphs = ()
        except ValueError:
            # not in list
            glyphs = self._glyphs
        try:
            args.remove('comment')
            comment = {}
        except ValueError:
            comment = self._get_comment_dict()
        return type(self)(
            glyphs,
            comment=comment,
            **{
                _k: _v
                for _k, _v in self.properties.items()
                if _k not in args and not _k.startswith('#')
            }
        )

    ##########################################################################
    # property access

    def __getattr__(self, attr):
        """Take property from property table."""
        if '_props' not in vars(self):
            logging.error(type(self).__name__ + '._props not defined')
            raise AttributeError(attr)
        if attr.startswith('_'):
            # don't delegate private members
            raise AttributeError(attr)
        return getattr(self._props, attr)

    def get_comment(self, key=''):
        """Get global or property comment."""
        return getattr(self._props, f'#{key}', '')

    def _get_comment_dict(self):
        """Get all global and property comments as a dict."""
        return {
            _k[1:]: self._props[_k]
            for _k in self._props
            if _k.startswith('#')
        }

    @property
    def properties(self):
        """Non-defaulted properties in order of default definition list."""
        return {
            _k: self._props[_k]
            for _k in self._props
            if not _k.startswith('_') and not _k.startswith('#')
        }

    def is_known_property(self, key):
        """Field is a recognised property."""
        return self._props._known(key)


    ##########################################################################
    # glyph access

    @property
    def glyphs(self):
        return self._glyphs

    def get_glyph(self, label=None, *, char=None, codepoint=None, tag=None, missing='raise'):
        """Get glyph by char, codepoint or tag; default if not present."""
        try:
            index = self.get_index(label, tag=tag, char=char, codepoint=codepoint)
        except KeyError:
            if missing == 'default':
                return self.get_default_glyph()
            if missing == 'empty':
                return self.get_empty_glyph()
            if missing is None or isinstance(missing, Glyph):
                return None
            raise
        return self._glyphs[index]

    def get_index(self, label=None, *, char=None, codepoint=None, tag=None):
        """Get index for given label, if defined."""
        if 1 != len([_indexer for _indexer in (label, char, codepoint, tag) if _indexer is not None]):
            raise ValueError('get_index() takes exactly one parameter.')
        if isinstance(label, str):
            # first look for char - expected to be shorter - then tags
            try:
                return self._chars[label]
            except KeyError:
                pass
            try:
                return self._tags[label]
            except KeyError:
                pass
        # do we have the input string directly as a char or tag?
        if label is not None:
            # convert strings, numerics through standard rules
            label = to_label(label)
            if isinstance(label, str):
                char = label
            elif isinstance(label, bytes):
                codepoint = label
            elif isinstance(label, Tag):
                tag = label
        if tag is not None:
            try:
                return self._tags[Tag(tag)]
            except KeyError:
                raise KeyError(f'No glyph found matching tag={Tag(tag)}') from None
        if char is not None:
            try:
                return self._chars[Char(char)]
            except KeyError:
                raise KeyError(f'No glyph found matching char={Char(char)}') from None
        try:
            return self._codepoints[Codepoint(codepoint)]
        except KeyError:
            raise KeyError(f'No glyph found matching codepoint={Codepoint(codepoint)}') from None


    @cache
    def get_default_glyph(self):
        """Get default glyph; empty if not defined."""
        try:
            return self.get_glyph(self.default_char)
        except KeyError:
            pass
        return self.get_empty_glyph()

    @cache
    def get_empty_glyph(self):
        """Get blank glyph with zero advance_width (or minimal if zero not possible)."""
        return Glyph.blank(max(0, -self.left_bearing - self.right_bearing), self.raster_size.y)


    ##########################################################################
    # label access

    def get_chars(self):
        """Get list of characters covered by this font."""
        return list(self._chars.keys())

    def get_codepoints(self):
        """Get list of codepage codepoints covered by this font."""
        return list(self._codepoints.keys())

    def get_tags(self):
        """Get list of tags covered by this font."""
        return list(self._tags.keys())

    def get_charmap(self):
        """Implied character map based on defined chars."""
        return charmaps.create({
            _glyph.codepoint: _glyph.char
            for _glyph in self._glyphs
            if _glyph.codepoint
            and _glyph.char
        }, name=f"implied-{self.name}")


    ##########################################################################
    # font operations

    @scriptable
    def label(
            self, *,
            codepoint_from:encoder='', char_from:encoder='',
            tag_from:tagger='', comment_from:tagger='',
            overwrite:bool=False
        ):
        """
        Add character and codepoint labels.

        codepoint_from: encoder registered name or filename to use to set codepoints from character labels
        char_from: encoder registered name or filename to use to set characters from codepoint labels. Default: use font encoding.
        tag_from: tagger registered name or filename to use to set tag labels
        comment_from: tagger registered name or filename to use to set comments
        overwrite: overwrite existing codepoints and/or characters
        """
        nargs = sum(
            bool(_arg)
            for _arg in (codepoint_from, char_from, tag_from, comment_from)
        )
        if nargs > 1:
            raise ValueError(
                'Can only set one of character, codepoint, tag or comment with one label() call. '
                'Use separate calls to set more.'
            )
        # default action: label chars with font encoding
        if nargs == 0 and self.encoding:
            char_from = encoder(self.encoding)
        if overwrite or not self.encoding:
            if char_from:
                self.encoding = char_from.name
            elif codepoint_from:
                self.encoding = codepoint_from.name
        if codepoint_from:
            return self.modify(glyphs=tuple(
                _glyph.label(codepoint_from=codepoint_from, overwrite=overwrite)
                for _glyph in self._glyphs
            ))
        if char_from:
            return self.modify(glyphs=tuple(
                _glyph.label(char_from=char_from, overwrite=overwrite)
                for _glyph in self._glyphs
            ))
        if tag_from:
            return self.modify(glyphs=tuple(
                _glyph.label(tag_from=tag_from, overwrite=overwrite)
                for _glyph in self._glyphs
            ))
        if comment_from:
            return self.modify(glyphs=tuple(
                _glyph.label(comment_from=comment_from, overwrite=overwrite)
                for _glyph in self._glyphs
            ))
        return self

    # need converter from string to set of labels to script this
    #@scriptable
    def subset(self, labels=(), *, chars:set=(), codepoints:set=(), tags:set=()):
        """
        Return a subset of the font.

        labels: chars, codepoints or tags to include
        chars: chars to include
        codepoints: codepoints to include
        tags: tags to include
        """
        glyphs = (
            [self.get_glyph(_label, missing=None) for _label in labels]
            + [self.get_glyph(char=_char, missing=None) for _char in chars]
            + [self.get_glyph(codepoint=_codepoint, missing=None) for _codepoint in codepoints]
            + [self.get_glyph(tag=_tag, missing=None) for _tag in tags]
        )
        return self.modify(_glyph for _glyph in glyphs if _glyph is not None)

    #@scriptable
    def exclude(self, labels=(), *, chars:set=(), codepoints:set=(), tags:set=()):
        """
        Return a font excluding a subset.

        labels: chars, codepoints or tags to exclude
        chars: chars to exclude
        codepoints: codepoints to exclude
        tags: tags to exclude
        """
        if not any((labels, chars, codepoints, tags)):
            return self
        glyphs = [
            _glyph
            for _glyph in self._glyphs
            if (
                _glyph.char not in labels
                and _glyph.codepoint not in labels
                and _glyph.char not in chars
                and _glyph.codepoint not in codepoints
                and not (set(_glyph.tags) & set(tags))
                and not (set(_glyph.tags) & set(labels))
            )
        ]
        return self.modify(glyphs)


    # WARNING: this shadows builtin set() in any annotations for method definitions below
    @scriptable(script_args={
        _k.replace('_', '-'): _v
        for _k, _v in FontProperties.__annotations__.items()
    })
    def set(self, **kwargs):
        """Return a copy of the font with one or more recognised properties changed."""
        return self.modify(**kwargs)

    @scriptable
    def set_property(self, key:str, value:Any='', *, append:bool=False, remove:bool=False):
        """
        Return a copy of the font with a property changed or added.

        key: the property key to set or append a value to
        value: the new property value
        append: append to existing string value, if any
        remove: ignore value and remove key
        """
        if remove:
            value = None
        kwargs = {key: value}
        if append and not remove:
            return self.append(**kwargs)
        return self.modify(**kwargs)

    @scriptable
    def set_comment(self, value:str, *, key:str='', append:bool=False, remove:bool=False):
        """
        Return a copy of the font with a comment changed, added or removed.

        key: the property key to set or append a comment to, default is global comment
        value: the new comment
        append: append to existing comment, if any
        remove: ignore value and remove comment
        """
        if remove:
            # DefaultProps will skip keys with None values
            value = None
        comment = {key: value}
        if append and not remove:
            return self.append(comment=comment)
        return self.modify(comment=comment)


    ##########################################################################
    # inject Glyph operations into Font

    glyph_operations = get_scriptables(Glyph)
    for _name, _func in glyph_operations.items():

        @scriptable
        @wraps(_func)
        def _modify_glyphs(self, *args, operation=_func, **kwargs):
            glyphs = tuple(
                operation(_glyph, *args, **kwargs)
                for _glyph in self._glyphs
            )
            return  self.modify(glyphs)

        locals()[_name] = _modify_glyphs


# scriptable font/glyph operations
operations = get_scriptables(Font)
