"""
monobit.font - representation of font

(c) 2019--2021 Rob Hagemans
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

from .scripting import scriptable, get_scriptables
from .glyph import Glyph, Coord, Bounds, number
from .encoding import charmaps
from .label import Label, Tag, Char, Codepoint, label
from .struct import extend_string, DefaultProps, normalise_property


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
    # overall ink bounds - overlay all glyphs with fixed origin and determine maximum ink extent
    bounding_box: Coord.create
    # average advance width, rounded to tenths
    average_advance: number
    # advance width of LATIN CAPITAL LETTER X
    cap_advance: int

    # descriptive typographic quantities
    # can be calculated or given
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

    # metrics
    # can't be calculated, affect rendering
    # positioning relative to origin
    # left-to-right, right-to-left
    direction: str = 'left-to-right'
    # (horiz, vert) offset from origin to matrix start
    offset: Coord.create
    # horizontal offset from matrix end to next origin
    tracking: int
    # interline spacing, defined as (pixels between baselines) - (pixel size)
    leading: int

    # character set
    # can't be calculated, affect rendering
    encoding: charmaps.normalise
    # replacement for missing glyph
    default_char: label
    # word-break character (usually space)
    word_boundary: label = Char(' ')

    # conversion metadata
    # can't be calculated, informational
    converter: str
    source_name: str
    source_format: str
    history: str


calculated_property = FontProperties._calculated_property



###################################################################################################
# Font class


class Font:
    """Representation of font glyphs and metadata."""

    def __init__(self, glyphs=(), *, comments=None, **properties):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        # comments can be str (just global comment) or mapping of property comments
        if not comments:
            self._comments = {}
        elif isinstance(comments, str):
            self._comments = {'': comments}
        else:
            self._comments = {_k: _v for _k, _v in comments.items()}
        # update properties
        # set encoding first so we can set labels
        # NOTE - we must be careful NOT TO ACCESS CACHED PROPERTIES
        #        until the constructor is complete
        self._props = FontProperties(**properties)
        # add labels if unset (needs encoding property)
        self._add_labels()
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


    def _add_labels(self):
        """Add character and codepoint labels."""
        has_codepoint = any(_glyph.codepoint for _glyph in self._glyphs)
        has_char = any(_glyph.char for _glyph in self._glyphs)
        # update glyph codepoints
        # use index as codepoint if no codepoints or chars set
        if not has_codepoint and not has_char:
            self._glyphs = tuple(
                _glyph.modify(codepoint=(_index,))
                for _index, _glyph in enumerate(self._glyphs)
            )
        # update glyph labels
        encoding = self._get_encoder()
        if encoding is not None:
            self._glyphs = tuple(
                _glyph.add_labels(encoding)
                for _glyph in self._glyphs
            )

    def _get_encoder(self):
        """Get encoding object."""
        try:
            return charmaps[self._props.encoding]
        except KeyError:
            return None


    ##########################################################################
    # representation

    def __repr__(self):
        """Representation."""
        elements = (
            f'glyphs=(...{len(self._glyphs)} glyphs...)' if self.glyphs else '',
            ', '.join(f'{_k}={_v}' for _k, _v in self.properties.items()),
        )
        return '{}({})'.format(
            type(self).__name__,
            ', '.join(_e for _e in elements if _e)
        )


    ##########################################################################
    # copying

    def modify(
            self, glyphs=NOT_SET, *,
            comments=NOT_SET, **kwargs
        ):
        """Return a copy of the glyph with changes."""
        if glyphs is NOT_SET:
            glyphs = self._glyphs
        if comments is NOT_SET:
            comments = self._comments
        return type(self)(
            tuple(glyphs),
            comments=comments,
            **{**self.properties, **kwargs}
        )

    def add(
            self, glyphs=(), *,
            comments=None, **properties
        ):
        """Return a copy of the glyph with changes."""
        if not comments:
            comments = {}
        if glyphs:
            glyphs = self._glyphs + tuple(glyphs)
        for property, comment in comments.items():
            if property in self._comments:
                comments[property] = extend_string(self._comments[property], comment)
        for property, value in properties.items():
            if property in self._props:
                properties[property] = extend_string(self._props[property], value)
        return self.modify(
            glyphs,
            comments={**self._comments, **comments},
            **properties
        )

    def add_history(self, history):
        """Return a copy with a line added to history."""
        return self.modify(history=extend_string(self.history, history))

    def drop_properties(self, *args):
        """Remove custom properties."""
        return self.modify(**{_k: None for _k in args})


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

    @property
    def comments(self):
        """Get global comments."""
        return self._comments.get('', '')

    def get_comments(self, property=''):
        """Get global or property comments."""
        return self._comments.get(normalise_property(property), '')

    @classmethod
    def default(cls, property):
        """Default value for a property."""
        return vars(FontProperties).get(normalise_property(property), '')

    @property
    def properties(self):
        """Non-defaulted properties in order of default definition list."""
        return {_k: self._props[_k] for _k in self._props}


    ##########################################################################
    # glyph access

    @property
    def glyphs(self):
        return self._glyphs

    def get_glyph(self, key=None, *, char=None, codepoint=None, tag=None, missing='raise'):
        """Get glyph by char, codepoint or tag; default if not present."""
        try:
            return self._glyphs[self.get_index(key, tag=tag, char=char, codepoint=codepoint)]
        except KeyError:
            if missing == 'default':
                return self.get_default_glyph()
            if missing == 'empty':
                return self.get_empty_glyph()
            if missing == 'raise':
                raise
            return missing

    def get_index(self, key=None, *, char=None, codepoint=None, tag=None):
        """Get index for given key or tag, if defined."""
        if 1 != len([_indexer for _indexer in (key, char, codepoint, tag) if _indexer is not None]):
            raise ValueError('get_index() takes exactly one parameter.')
        if isinstance(key, Char):
            char = key
        elif isinstance(key, Codepoint):
            codepoint = key
        elif isinstance(key, Tag):
            tag = key
        elif key is not None:
            # unspecified key, deduct from type
            # str -> char; tuple/list/bytes -> codepoint
            # a tag can only be specified explicitly
            if isinstance(key, str):
                char = key
            else:
                # let Codepoint deal with interpretation
                codepoint = Codepoint(key).value
        if tag is not None:
            try:
                return self._tags[Tag(tag).value]
            except KeyError:
                raise KeyError(f'No glyph found matching tag={Tag(tag)}') from None
        if char is not None:
            try:
                return self._chars[Char(char).value]
            except KeyError:
                raise KeyError(f'No glyph found matching char={Char(char)}') from None
        try:
            return self._codepoints[Codepoint(codepoint).value]
        except KeyError:
            raise KeyError(f'No glyph found matching codepoint={Codepoint(codepoint)}') from None


    @cache
    def get_default_glyph(self):
        """Get default glyph; empty if not defined."""
        try:
            return self.get_glyph(self.default_char)
        except KeyError:
            return self.get_empty_glyph()

    @cache
    def get_empty_glyph(self):
        """Get blank glyph with zero advance (or minimal if zero not possible)."""
        return Glyph.blank(max(0, -self.offset.x - self.tracking), self.raster_size.y)


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
    # calculated properties

    @calculated_property
    def name(self):
        """Name of font."""
        if self.slant == self.default('slant'):
            slant = ''
        else:
            # title-case
            slant = self.slant.title()
        if self.setwidth == self.default('setwidth'):
            setwidth = ''
        else:
            setwidth = self.setwidth.title()
        if (slant or setwidth) and self.weight == self.default('weight'):
            weight = ''
        else:
            weight = self.weight.title()
        return ' '.join(
            str(_x) for _x in (self.family, setwidth, weight, slant, self.point_size) if _x
        )

    @calculated_property
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

    @calculated_property(override='notify')
    def point_size(self):
        """Nominal point height."""
        # assume 72 points per inch (officially 72.27 pica points per inch)
        # if dpi not given assumes 72 dpi, so point-size == pixel-size
        return int(self.pixel_size * self.dpi.y / 72.)

    @calculated_property(override='reject')
    def pixel_size(self):
        """Get nominal pixel size (ascent + descent)."""
        if not self._glyphs:
            return 0
        return self.ascent + self.descent

    @calculated_property
    def dpi(self):
        """Target screen resolution in dots per inch."""
        # if point-size has been overridden and dpi not set, determine from pixel-size & point-size
        if 'point-size' in self._props:
            dpi = (72 * self.pixel_size) // self.point_size
        else:
            # default: 72 dpi; 1 point == 1 pixel
            dpi = 72
        # stretch/shrink dpi.x if aspect ratio is not square
        return Coord((dpi*self.pixel_aspect.x)//self.pixel_aspect.y, dpi)

    @calculated_property
    def ascent(self):
        """Get ascent (defaults to max ink height above baseline)."""
        if not self._glyphs:
            return 0
        return self.offset.y + max(
            _glyph.height - _glyph.padding.top
            for _glyph in self._glyphs
        )

    @calculated_property
    def descent(self):
        """Get descent (defaults to bottom/vertical offset)."""
        if not self._glyphs:
            return 0
        # usually, descent is positive and offset is negative
        # negative descent would mean font descenders are all above baseline
        return -self.offset.y - min(_glyph.padding.bottom for _glyph in self._glyphs)

    @calculated_property(override='reject')
    def raster(self):
        """Minimum box encompassing all glyph matrices overlaid at fixed origin."""
        if not self._glyphs:
            return Bounds(0, 0, 0, 0)
        lefts = tuple(_glyph.offset.x for _glyph in self._glyphs)
        bottoms = tuple(_glyph.offset.y for _glyph in self._glyphs)
        rights = tuple(_glyph.offset.x + _glyph.width for _glyph in self._glyphs)
        tops = tuple(_glyph.offset.y + _glyph.height for _glyph in self._glyphs)
        return Bounds(left=min(lefts), bottom=min(bottoms), right=max(rights), top=max(tops))

    @calculated_property(override='reject')
    def raster_size(self):
        """Minimum box encompassing all glyph matrices overlaid at fixed origin."""
        return Coord(
            self.raster.right - self.raster.left,
            self.raster.top - self.raster.bottom
        )

    @calculated_property(override='reject')
    def ink_bounds(self):
        """Minimum bounding box encompassing all glyphs at fixed origin, font origin cordinates."""
        if not self._glyphs:
            return Bounds(self.offset.x, self.offset.y, self.offset.x, self.offset.y)
        lefts, bottoms, rights, tops = zip(*(
            _glyph.ink_bounds
            for _glyph in self._glyphs
            if _glyph.bounding_box.x and _glyph.bounding_box.y
        ))
        return Bounds(
            left=self.offset.x + min(lefts),
            bottom=self.offset.y + min(bottoms),
            right=self.offset.x + max(rights),
            top=self.offset.y + max(tops)
        )

    @calculated_property(override='reject')
    def bounding_box(self):
        """Dimensions of minimum bounding box encompassing all glyphs at fixed origin."""
        return Coord(
            self.ink_bounds.right - self.ink_bounds.left,
            self.ink_bounds.top - self.ink_bounds.bottom
        )

    @calculated_property(override='reject')
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
        # a _monospace_ font is a font where all glyphs have equal advance.
        #
        if not self._glyphs:
            return 'character-cell'
        if any(_glyph.advance < 0 or _glyph.kern_to for _glyph in self._glyphs):
            return 'proportional'
        # don't count void glyphs (0 width and/or height) to determine whether it's monospace
        advances = set(_glyph.advance for _glyph in self._glyphs if _glyph.advance)
        monospaced = len(set(advances)) == 1
        bispaced = len(set(advances)) == 2
        ink_contained_y = self.line_spacing >= self.bounding_box.y
        ink_contained_x = all(
            _glyph.advance >= _glyph.bounding_box.x
            for _glyph in self._glyphs
        )
        if ink_contained_x and ink_contained_y:
            if monospaced:
                return 'character-cell'
            if bispaced:
                return 'multi-cell'
        if monospaced:
            return 'monospace'
        return 'proportional'

    @calculated_property
    def default_char(self):
        """Label for default character."""
        repl = '\ufffd'
        if repl not in self._chars:
            repl = ''
        return Char(repl)

    @calculated_property(override='notify')
    def average_advance(self):
        """Get average glyph advance width, rounded to tenths of pixels."""
        if not self._glyphs:
            return self.offset.x + self.tracking
        return (
            self.offset.x
            + sum(_glyph.advance for _glyph in self._glyphs) / len(self._glyphs)
            + self.tracking
        )

    @calculated_property(override='notify')
    def max_advance(self):
        """Maximum glyph advance width."""
        if not self._glyphs:
            return self.offset.x + self.tracking
        return (
            self.offset.x
            + max(_glyph.advance for _glyph in self._glyphs)
            + self.tracking
        )

    @calculated_property(override='notify')
    def cap_advance(self):
        """Advance width of uppercase X."""
        try:
            return self.get_glyph('X').advance + self.offset.x + self.tracking
        except KeyError:
            return 0

    @calculated_property(override='notify')
    def x_height(self):
        """Ink height of lowercase x."""
        try:
            return self.get_glyph('x').bounding_box.y
        except KeyError:
            return 0

    @calculated_property(override='notify')
    def cap_height(self):
        """Ink height of uppercase X."""
        try:
            return self.get_glyph('X').bounding_box.y
        except KeyError:
            return 0

    @calculated_property(override='reject')
    def line_spacing(self):
        """Distance between consecutive baselines, in pixels."""
        return self.pixel_size + self.leading


    ##########################################################################
    # font operations

    set = scriptable(modify, script_args=FontProperties.__annotations__, name='set')

    @scriptable
    def subset(self, keys=(), *, chars:set=(), codepoints:set=(), tags:set=()):
        """
        Return a subset of the font.

        chars: chars to include
        codepoints: codepoints to include
        tags: tags to include
        """
        glyphs = (
            [self.get_glyph(_key, missing=None) for _key in keys]
            + [self.get_glyph(char=_char, missing=None) for _char in chars]
            + [self.get_glyph(codepoint=_codepoint, missing=None) for _codepoint in codepoints]
            + [self.get_glyph(tag=_tag, missing=None) for _tag in tags]
        )
        return self.modify(_glyph for _glyph in glyphs if _glyph is not None)

    @scriptable
    def without(self, keys=(), *, chars:set=(), codepoints:set=(), tags:set=()):
        """Return a font excluding a subset."""
        if not any((keys, chars, codepoints, tags)):
            return self
        glyphs = [
            _glyph
            for _glyph in self._glyphs
            if (
                _glyph.char not in keys
                and _glyph.codepoint not in keys
                and _glyph.char not in chars
                and _glyph.codepoint not in codepoints
                and not (set(_glyph.tags) & set(tags))
            )
        ]
        return self.modify(glyphs)

    def merged_with(self, other):
        """Merge glyphs from other font into this one. Existing glyphs have preference."""
        glyphs = list(self._glyphs)
        encoder = self._get_encoder()
        for glyph in other.glyphs:
            # don't overwrite chars we already have
            if glyph.char not in set(self._chars):
                # exclude tags we already have
                new_tags = set(glyph.tags) - set(self._tags)
                # update codepoint based on this font's encoding
                if encoder is not None:
                    new_codepoint = encoder.codepoint(glyph.char)
                    glyph = glyph.modify(tags=new_tags, codepoint=new_codepoint)
                else:
                    glyph = glyph.modify(tags=new_tags)
                glyphs.append(glyph)
        return self.modify(glyphs)


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
