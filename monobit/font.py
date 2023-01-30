"""
monobit.font - representation of font

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from functools import wraps, partial
from pathlib import PurePath
from unicodedata import normalize
try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()

from .scripting import scriptable, get_scriptables, Any
from .glyph import Glyph
from .raster import turn_method
from .basetypes import Coord, Bounds
from .basetypes import to_int
from .encoding import charmaps, encoder
from .taggers import tagger
from .labels import Tag, Char, Codepoint, Label, to_label
from .binary import ceildiv
from .properties import (
    extend_string, DefaultProps, normalise_property, as_tuple,
    writable_property, checked_property
)
from .taggers import tagmaps


# sentinel object
NOT_SET = object()


# pylint: disable=redundant-keyword-arg, no-member

###############################################################################
# property management


# recognised yaff properties and converters from str
# this also defines the default order in yaff files
class FontProperties(DefaultProps):

    # naming - can be determined from source file if needed
    # full human name
    name: str
    # typeface/font family
    family: str
    # unique id
    font_id: str

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
    point_size: float
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
    pixel_aspect: Coord = Coord(1, 1)
    # target resolution in dots per inch
    dpi: Coord

    # summarising quantities
    # determined from the bitmaps only

    # proportional, monospace, character-cell, multi-cell
    spacing: str
    # maximum raster (not necessarily ink) width/height
    raster_size: Coord
    # width, height of the character cell
    cell_size: Coord
    # overall ink bounds - overlay all glyphs with fixed origin and determine maximum ink extent
    bounding_box: Coord
    # average advance width, rounded to tenths
    average_width: float
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
    # 'descent' for vertical rendering
    left_extent: int
    # 'ascent' for vertical rendering
    right_extent: int
    # nominal pixel size, always equals ascent + descent
    pixel_size: int
    # vertical interline spacing, defined as line_height - pixel_size
    leading: int

    # metrics
    # can't be calculated, affect rendering

    # vertical distance between consecutive baselines, in pixels
    line_height: int
    # horizontal distance between consecutive baselines, in pixels
    line_width: int

    # character properties
    # can't be calculated, affect rendering

    # character map, stored as normalised name
    encoding: charmaps.normalise
    # replacement for missing glyph
    default_char: Label
    # word-break character (usually space)
    word_boundary: Label = Char(' ')

    # rendering hints
    # may affect rendering if effects are applied

    # can be set to left-to-right, right-to-left to suggest a writing direction
    # though it is better determined through the bidirectional algorithm
    # the meaning of metrics is agnostic to writing direction
    direction: str = ''
    # number of pixels to smear in advance direction to simulate bold weight
    bold_smear: int = 1
    # pitch when simulating italic by shearing glyphs
    italic_pitch: Coord = (1, 1)
    # thickness of outline effect, in pixels
    outline_thickness: int = 1
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
    superscript_offset: Coord
    # recommended subscript horizontal, vertical offset in pixels.
    subscript_offset: Coord
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

    # type converters for compatibility synonyms
    average_advance: float
    max_advance: int
    cap_advance: int

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
        # change underscored/spaced filenames to camelcase font name
        # replace underscores with spaces
        stem = stem.replace('_', ' ')
        # convert all-upper or all-lower to titlecase
        if stem == stem.upper() or stem == stem.lower():
            stem = stem.title()
        stem = stem.replace(' ', '')
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

    @writable_property
    def line_height(self):
        """Vertical distance between consecutive baselines, in pixels."""
        if 'leading' in vars(self):
            return self.pixel_size + self.leading
        return max(self.raster_size.y, self.pixel_size)

    @writable_property
    def line_width(self):
        """Horizontal distance between consecutive baselines, in pixels."""
        return self.max_width


    ##########################################################################
    # typographic descriptors

    @writable_property
    def ascent(self):
        """
        Recommended typographic ascent relative to baseline.
        Defaults to ink-top.
        """
        if not self._font.glyphs:
            return 0
        return max(0, self.ink_bounds.top)

    @writable_property
    def descent(self):
        """
        Recommended typographic descent relative to baseline.
        Defaults to ink-bottom.
        """
        if not self._font.glyphs:
            return 0
        # if ink bounds go below the baseline, use them as descent
        return max(0, -self.ink_bounds.bottom)

    @checked_property
    def pixel_size(self):
        """Get nominal pixel size. Equals ascent + descent."""
        return self.ascent + self.descent

    @writable_property
    def leading(self):
        """
        Vertical interline spacing,
        defined as (pixels between baselines) - (pixel size).
        """
        return self.line_height - self.pixel_size

    ##########################################################################
    # summarising quantities

    @checked_property
    def spacing(self):
        """Monospace or proportional spacing."""
        # a _character-cell_ font is a font where all glyphs can be put inside
        # an equal size cell so that rendering the font becomes simply pasting
        # cells flush to each other. All ink for a glyph must be inside the cell.
        #
        # this means that:
        # - all glyphs must have equal, positive advance width
        #   (except empty glyphs with advance zero).
        # - for each glyph, the advance is greater than or equal to
        #   the bounding box width.
        # - the line advance is greater than or equal to the font bounding box
        #   height.
        # - there is no kerning
        #
        # a special case is the _multi-cell_ font,
        # where a glyph may take up 0, 1 or 2 cells.
        #
        # a _monospace_ font is a font where all glyphs have equal advance_width.
        #
        if not self._font.glyphs:
            return 'character-cell'
        if any(
                _glyph.advance_width < 0 or _glyph.right_kerning
                for _glyph in self._font.glyphs
            ):
            return 'proportional'
        # don't count void glyphs (0 width and/or height)
        # to determine whether it's monospace
        advances = set(
            _glyph.advance_width
            for _glyph in self._font.glyphs if _glyph.advance_width
        )
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
        """
        Minimum box encompassing all glyph matrices overlaid at fixed origin,
        bottom-left origin coordinates.
        """
        if not self._font.glyphs:
            return Bounds(0, 0, 0, 0)
        return Glyph._get_common_raster(*self._font.glyphs)

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
        if not self._font.glyphs or self.spacing == 'proportional':
            return Coord(0, 0)
        # smaller of the (at most two) advance widths is the cell size
        # in a multi-cell font, some glyphs may take up two cells.
        cell_x = min(
            _glyph.advance_width
            for _glyph in self._font.glyphs if _glyph.advance_width
        )
        return Coord(cell_x, self.line_height)

    @checked_property
    def ink_bounds(self):
        """
        Minimum bounding box encompassing all glyphs at fixed origin,
        bottom-left origin cordinates.
        """
        nonempty = [
            _glyph for _glyph in self._font.glyphs
            if _glyph.bounding_box.x and _glyph.bounding_box.y
        ]
        if not nonempty:
            return Bounds(0, 0, 0, 0)
        lefts, bottoms, rights, tops = zip(*(
            _glyph.ink_bounds
            for _glyph in nonempty
        ))
        return Bounds(
            left=min(lefts),
            bottom=min(bottoms),
            right=max(rights),
            top=max(tops)
        )

    @checked_property
    def bounding_box(self):
        """
        Dimensions of minimum bounding box encompassing all glyphs
        at fixed bottom-left origin.
        """
        return Coord(
            self.ink_bounds.right - self.ink_bounds.left,
            self.ink_bounds.top - self.ink_bounds.bottom
        )

    @checked_property
    def padding(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        return Bounds(
            self.ink_bounds.left - self.raster.left,
            self.ink_bounds.bottom - self.raster.bottom,
            self.raster.right - self.ink_bounds.right,
            self.raster.top - self.ink_bounds.top,
        )

    @writable_property
    def average_width(self):
        """Get average glyph advance width."""
        if not self._font.glyphs:
            return 0
        return (
            sum(_glyph.advance_width for _glyph in self._font.glyphs)
            / len(self._font.glyphs)
        )

    @writable_property
    def max_width(self):
        """Maximum glyph advance width."""
        if not self._font.glyphs:
            return 0
        return max(_glyph.advance_width for _glyph in self._font.glyphs)

    @writable_property
    def cap_width(self):
        """Advance width of uppercase X."""
        try:
            return self._font.get_glyph(char='X').advance_width
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
            _glyph.shift_up + _glyph.padding.bottom
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
        if repl not in self._font.get_chars():
            repl = ''
        return Char(repl)


    ##########################################################################
    # deprecated compatibility synonyms

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


###############################################################################
# Font class


class Font:
    """Representation of font glyphs and metadata."""

    def __init__(self, glyphs=(), *, comment=None, **properties):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        # construct lookup tables
        self._labels = {
            _label: _index
            for _index, _glyph in enumerate(self._glyphs)
            for _label in _glyph.get_labels()
        }
        # comment can be str (just global comment) or mapping of property comments
        if not comment:
            pass
        elif isinstance(comment, str):
            properties['#'] = comment
        else:
            properties.update({f'#{_k}': _v for _k, _v in comment.items()})
        self._glyphs, properties = self._apply_metrics(self._glyphs, properties)
        # update properties
        # set encoding first so we can set labels
        # NOTE - we must be careful NOT TO ACCESS CACHED PROPERTIES
        #        until the constructor is complete
        self._props = FontProperties(_font=self, **properties)

    @staticmethod
    def _apply_metrics(glyphs, props):
        """Apply globally specified glyph metrics."""
        glyph_metrics = {
            _k: props[_k]
            for _k in (
                'shift_up', 'left_bearing', 'right_bearing',
                'shift_left', 'top_bearing', 'bottom_bearing',
                'tracking', 'offset',
            )
            if _k in props
        }
        props = {
            _k: _v
            for _k, _v in props.items()
            if _k not in glyph_metrics
        }
        if glyph_metrics:
            # create a dummy glyph to ensure values get converted to right type
            glob = Glyph(**glyph_metrics)
            # localise glyph metrics
            glyphs = tuple(
                _g.modify(**{
                    _k: _g.get_property(_k) + _v
                    for _k, _v in glob.properties.items()
                })
                for _g in glyphs
            )
        return glyphs, props


    ##########################################################################
    # representation

    def __repr__(self):
        """Representation."""
        elements = (
            f'glyphs=(...{len(self._glyphs)} glyphs...)' if self._glyphs else '',
            ',\n    '.join(
                f'{normalise_property(_k)}={repr(_v)}'
                for _k, _v in self.properties.items()
            ),
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
        properties = {
            _k: _v
            for _k, _v in vars(self._props).items()
            if not _k.startswith('_') and not _k.startswith('#')
        }
        properties.update({
            normalise_property(_k): _v
            for _k, _v in kwargs.items()
        })
        return Font(
            tuple(glyphs),
            comment=old_comment,
            **properties
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
        if glyphs:
            # apply any _LazyTransformedItems
            glyphs = (*self.glyphs, *glyphs)
        else:
            glyphs = NOT_SET
        return self.modify(glyphs, comment={**comment}, **properties)

    def drop(self, *args):
        """Remove glyphs, comments or properties."""
        args = list(args)
        try:
            args.remove('glyphs')
            glyphs = ()
        except ValueError:
            # not in list
            glyphs = NOT_SET
        try:
            args.remove('comment')
            comment = {'': None}
        except ValueError:
            comment = {}
        none_args = {normalise_property(_k): None for _k in args}
        # remove property comments for dropped properties
        comment.update(none_args)
        return self.modify(
            glyphs,
            comment=comment,
            **none_args,
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
        key = normalise_property(key)
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
            _k.replace('_', '-'): self._props[_k]
            for _k in self._props
            if not _k.startswith('_') and not _k.startswith('#')
            and self._props[_k] != self._props._get_default(_k)
        }

    def is_known_property(self, key):
        """Field is a recognised property."""
        return self._props._known(key)

    def get_property(self, key):
        """Get value for property."""
        key = normalise_property(key)
        return getattr(self._props, key, '')


    ##########################################################################
    # glyph access

    @property
    def glyphs(self):
        return self._glyphs

    @cache
    def _compose_glyph(self, char):
        """Compose glyph by overlaying components."""
        # first check if a canonical equivalent is stored
        nfc = Char(normalize('NFC', char))
        try:
            index = self.get_index(nfc)
            return self._glyphs[index]
        except KeyError:
            pass
        char = Char(normalize('NFD', char))
        indices = (self.get_index(_c) for _c in char)
        indices = tuple(indices)
        return Glyph.overlay(*(self._glyphs[_i] for _i in indices))

    def get_glyph(
            self, label=None, *,
            char=None, codepoint=None, tag=None,
            missing='raise'
        ):
        """Get glyph by char, codepoint or tag; default if not present."""
        try:
            index = self.get_index(
                label, tag=tag, char=char, codepoint=codepoint
            )
            return self.glyphs[index]
        except KeyError:
            label = to_label(label)
            # if not found and the label is a composed unicode character
            # try to compose the glyph from its elements
            if isinstance(label, Char):
                char = Char(label)
            if char:
                try:
                    return self._compose_glyph(char)
                except KeyError:
                    pass
            if missing == 'default':
                return self.get_default_glyph()
            if missing == 'empty':
                return self.get_empty_glyph()
            if missing is None or isinstance(missing, Glyph):
                return missing
            raise

    def get_index(self, label=None, *, char=None, codepoint=None, tag=None):
        """Get index for given label, if defined."""
        if 1 != len([
                _indexer for _indexer in (label, char, codepoint, tag)
                if _indexer is not None
            ]):
            raise ValueError('get_index() takes exactly one parameter.')
        if char is not None:
            label = Char(char)
        elif codepoint is not None:
            label = Codepoint(codepoint)
        elif tag is not None:
            label = Tag(tag)
        elif isinstance(label, str):
            # first look for char - expected to be shorter - then tags
            try:
                return self._labels[Char(label)]
            except KeyError:
                pass
            try:
                return self._labels[Tag(label)]
            except KeyError:
                pass
        # do we have the input string directly as a char or tag?
        elif label is not None:
            # convert strings, numerics through standard rules
            label = to_label(label)
        try:
            return self._labels[label]
        except KeyError:
            pass
        raise KeyError(f'No glyph found matching label={label}')

    @cache
    def get_default_glyph(self):
        """Get default glyph; empty if not defined."""
        return self.get_glyph(self.default_char, missing='empty')

    @cache
    def get_empty_glyph(self):
        """Get blank glyph with zero advance_width and advance_height"""
        return Glyph.blank()


    ##########################################################################
    # label access

    @cache
    def get_chars(self):
        """Get tuple of characters covered by this font."""
        return tuple(_c for _c in self._labels if isinstance(_c, Char))

    @cache
    def get_codepoints(self):
        """Get tuple of codepage codepoints covered by this font."""
        return tuple(_c for _c in self._labels if isinstance(_c, Codepoint))

    @cache
    def get_tags(self):
        """Get tuple of tags covered by this font."""
        return tuple(_c for _c in self._labels if isinstance(_c, Tag))

    @cache
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
            overwrite:bool=False, match_whitespace:bool=True,
        ):
        """
        Add character and codepoint labels.

        codepoint_from: encoder registered name or filename to use to set codepoints from character labels
        char_from: encoder registered name or filename to use to set characters from codepoint labels. Default: use font encoding.
        tag_from: tagger registered name or filename to use to set tag labels
        comment_from: tagger registered name or filename to use to set comments
        overwrite: overwrite existing codepoints and/or characters
        match_whitespace: do not give blank glyphs a non-whitespace char label (default: true)
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
            if not char_from:
                logging.warning(f'Encoding `{self.encoding}` not recognised.')
                return self
        encoding = self.encoding
        if overwrite or not self.encoding:
            if char_from:
                encoding = char_from.name
            elif codepoint_from:
                encoding = codepoint_from.name
        kwargs = dict(
            overwrite=overwrite,
            match_whitespace=match_whitespace,
        )
        if codepoint_from:
            kwargs.update(dict(codepoint_from=codepoint_from))
        elif char_from:
            kwargs.update(dict(char_from=char_from))
        elif tag_from:
            kwargs.update(dict(tag_from=tag_from))
        elif comment_from:
            kwargs.update(dict(comment_from=comment_from))
        else:
            return self
        return self.modify(encoding=encoding, glyphs=tuple(
            _glyph.label(**kwargs)
            for _glyph in self.glyphs
        ))

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
        labels = (
            set(labels)
            | set(Char(_c) for _c in chars)
            | set(Codepoint(_c) for _c in codepoints)
            | set(Tag(_c) for _c in tags)
        )
        if not any((labels, chars, codepoints, tags)):
            return self
        glyphs = [
            _glyph
            for _glyph in self.glyphs
            if not (set(_glyph.get_labels()) & set(labels))
        ]
        return self.modify(glyphs)


    # WARNING: this shadows builtin set() in any annotations for method definitions below
    @scriptable(script_args=FontProperties.__annotations__.items())
    def set(self, **kwargs):
        """Return a copy of the font with one or more recognised properties changed."""
        kwargs = {
            _k: (_v if _v != '' else None)
            for _k, _v in kwargs.items()
        }
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
    # transformations

    def _apply_to_all_glyphs(self, operation, **kwargs):
        return _LazyTransformedFont(self, operation, **kwargs)


    # orthogonal transformations

    @scriptable
    def mirror(self, *, adjust_metrics:bool=True):
        """
        Reverse horizontally.

        adjust_metrics: also reverse metrics (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.mirror, adjust_metrics=adjust_metrics
        )
        if not adjust_metrics:
            return font
        return font.modify(
            direction={
                'left-to-right': 'right-to-left',
                'right-to-left': 'left-to-right',
            }.get(font.direction, font.direction)
        )

    @scriptable
    def flip(self, *, adjust_metrics:bool=True):
        """
        Reverse vertically.

        adjust_metrics: also reverse metrics (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.flip, adjust_metrics=adjust_metrics
        )
        if not adjust_metrics:
            return font
        return font.modify(
            direction={
                'top-to-bottom': 'bottom-to-top',
                'bottom-to-top': 'top-to-bottom',
            }.get(font.direction, font.direction)
        )

    @scriptable
    def transpose(self, *, adjust_metrics:bool=True):
        """
        Swap horizontal and vertical directions.

        adjust_metrics: also transpose metrics (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.transpose, adjust_metrics=adjust_metrics
        )
        if not adjust_metrics:
            return font
        return font.modify(
            line_height=font.line_width,
            line_width=font.line_height,
            direction={
                'left-to-right': 'top-to-bottom',
                'right-to-left': 'bottom-to-top',
                'top-to-bottom': 'left-to-right',
                'bottom-to-top': 'right-to-left',
            }.get(font.direction, font.direction)
        )

    # implement turn() based on the above
    turn = scriptable(turn_method)

    # raster resizing

    @scriptable
    def crop(
            self, left:int=0, bottom:int=0, right:int=0, top:int=0,
            *, adjust_metrics:bool=True
        ):
        """
        Crop the raster.

        left: number of columns to remove from left
        bottom: number of rows to remove from bottom
        right: number of columns to remove from right
        top: number of rows to remove from top
        adjust_metrics: make the operation render-invariant (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.crop,
            left=left, bottom=bottom, right=right, top=top, adjust_metrics=adjust_metrics
        )
        if not adjust_metrics:
            return font
        # fix line-advances to ensure they remain unchanged
        return font.modify(
            line_height=self.line_height,
            line_width=self.line_width,
        )

    @scriptable
    def expand(
            self, left:int=0, bottom:int=0, right:int=0, top:int=0,
            *, adjust_metrics:bool=True
        ):
        """
        Add blank space to raster.

        left: number of columns to add on left
        bottom: number of rows to add on bottom
        right: number of columns to add on right
        top: number of rows to add on top
        adjust_metrics: make the operation render-invariant (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.expand,
            left=left, bottom=bottom, right=right, top=top,
            adjust_metrics=adjust_metrics
        )
        if not adjust_metrics:
            return font
        # fix line-advances to ensure they remain unchanged
        return font.modify(
            line_height=self.line_height,
            line_width=self.line_width,
        )

    @scriptable
    def reduce(self, *, adjust_metrics:bool=True):
        """
        Reduce glyphs to their bounding box.

        adjust_metrics: make the operation render-invariant (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.reduce,
            adjust_metrics=adjust_metrics,
        )
        if not adjust_metrics:
            return font
        # fix line-advances to ensure they remain unchanged
        return font.modify(
            line_height=self.line_height,
            line_width=self.line_width,
        )

    @scriptable
    def inflate(self, *, adjust_metrics:bool=True):
        """
        Pad glyphs to include positive bearings and line spacing.
        Any negative bearings remain unchanged.

        adjust_metrics: make the operation render-invariant (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.inflate,
            adjust_metrics=adjust_metrics,
        )
        if not adjust_metrics:
            return font
        glyphs = tuple(
            _g.expand(
                top=max(0, self.line_height-_g.height),
                left=max(0, (self.line_width-_g.width)//2),
                right=max(0, (self.line_width-_g.width + 1)//2),
            )
            for _g in self.glyphs
        )
        # fix line-advances to ensure they remain unchanged
        return font.modify(
            glyphs,
            line_height=self.line_height,
            line_width=self.line_width,
        )

    # scaling

    @scriptable
    def stretch(
            self, factor_x:int=1, factor_y:int=1,
            *, adjust_metrics:bool=True
        ):
        """
        Stretch by repeating rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        adjust_metrics: also stretch metrics (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.stretch,
            factor_x=factor_x, factor_y=factor_y,
            adjust_metrics=adjust_metrics,
        )
        if not adjust_metrics:
            return font
        # fix line-advances to ensure they remain unchanged
        return font.modify(
            line_height=self.line_height * factor_y,
            line_width=self.line_width * factor_x,
        )

    @scriptable
    def shrink(
            self, factor_x:int=1, factor_y:int=1,
            *, adjust_metrics:bool=True
        ):
        """
        Shrink by removing rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        adjust_metrics: also stretch metrics (default: True)
        """
        font = self._apply_to_all_glyphs(
            Glyph.shrink,
            factor_x=factor_x, factor_y=factor_y,
            adjust_metrics=adjust_metrics,
        )
        if not adjust_metrics:
            return font
        # fix line-advances to ensure they remain unchanged
        return font.modify(
            line_height=self.line_height // factor_y,
            line_width=self.line_width // factor_x,
        )

    # ink effects

    @scriptable
    def smear(
            self, *, left:int=None, down:int=None, right:int=None, up:int=None,
            adjust_metrics:bool=True
        ):
        """
        Repeat inked pixels.

        left: number of times to repeat inked pixel leftwards
        right: number of times to repeat inked pixel rightwards
               (default: use bold-smear value)
        up: number of times to repeat inked pixel upwards
        down: number of times to repeat inked pixel downwards
        adjust_metrics: ensure advances stay the same (default: True)
        """
        if set((left, down, right, up)) == set((None,)):
            right = self.bold_smear
        right = right or 0
        left = left or 0
        down = down or 0
        up = up or 0
        return self._apply_to_all_glyphs(
            Glyph.smear,
            left=left, down=down, right=right, up=up,
            adjust_metrics=adjust_metrics,
        )

    @scriptable
    def underline(self, descent:int=None, thickness:int=None):
        """
        Add a line.

        descent: number of pixels the underline is below the baseline
                 (default: use underline-descent value)
        thickness: number of pixels the underline extends downward
                   (default: use underline-thickness value)
        """
        if descent is None:
            descent = self.underline_descent
        if thickness is None:
            thickness = self.underline_thickness
        return self._apply_to_all_glyphs(
            Glyph.underline,
            descent=descent, thickness=thickness
        )

    @scriptable
    def shear(self, *, direction:str='right', pitch:Coord=None):
        """
        Create a slant by dislocating diagonally, keeping
        the horizontal baseline fixed.

        direction: direction to move the top of the glyph (default: 'right').
        pitch: angle of the slant, given as (x, y) coordinate
               (default: use italic-pitch value).
        """
        if pitch is None:
            pitch = self.italic_pitch
        return self._apply_to_all_glyphs(
            Glyph.shear,
            direction=direction, pitch=pitch
        )

    @scriptable
    def outline(self, *, thickness:int=None):
        """
        Outline glyph.

        thickness: number of pixels in outline in each direction
                   (default: use outline-thickness value).
        """
        if thickness is None:
            thickness = self.outline_thickness
        return self._apply_to_all_glyphs(
            Glyph.outline,
            thickness = thickness
        )


    # inject remaining Glyph transformations into Font

    for _name, _func in get_scriptables(Glyph).items():
        if _name not in locals():

            @scriptable
            @wraps(_func)
            def _modify_glyphs(self, _func=_func, **kwargs):
                return self._apply_to_all_glyphs(_func, **kwargs)

            locals()[_name] = _modify_glyphs


# scriptable font/glyph operations
operations = get_scriptables(Font)


from collections.abc import Sequence

class _LazyTransformedItems(Sequence):
    """Sequence that applies transformation on access."""

    def __init__(self, items, func):
        self._items = items
        self._func = func

    @cache
    def __getitem__(self, index):
        return self._func(self._items[index])

    def __len__(self):
        return len(self._items)


class _LazyTransformedFont(Font):
    """Font that applies transformation on glyph access."""

    def __init__(self, font, transformation, **kwargs):
        """Initialise, compose functions if needed."""
        self._glyphs = font._glyphs
        self._labels = font._labels
        # TODO: fix hack
        self._props = font._props
        self._props._frozen = False
        self._props._font = self
        self._props._frozen = True
        if isinstance(font, _LazyTransformedFont):
            prev_func = font._func
            def _wrapped(font):
                return transformation(prev_func(font), **kwargs)
            self._func = _wrapped
        else:
            self._func = partial(transformation, **kwargs)
        self._transformed_glyphs = _LazyTransformedItems(self._glyphs, self._func)

    def modify(self, glyphs=NOT_SET, **kwargs):
        if glyphs is NOT_SET or isinstance(glyphs, _LazyTransformedItems):
            return type(self)(super().modify(glyphs, **kwargs), self._func)
        # glyphs have been accessed and are no longer LazyTransformed
        # avoid double-applying transformations
        return super().modify(glyphs, **kwargs)


    @property
    def glyphs(self):
        return self._transformed_glyphs

    @cache
    def _compose_glyph(self, char):
        """Compose glyph by overlaying components."""
        # transformation may not commute with composition (e.g. outline)
        # don't compose transformed glyphs, but transform the composed glyph
        glyph = super()._compose_glyph(char)
        return self._func(glyph)
