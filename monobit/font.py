"""
monobit.font - representation of font

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from functools import wraps
from functools import partial
import logging
from types import SimpleNamespace

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


# pylint: disable=redundant-keyword-arg, no-member

###################################################################################################
# property management


# recognised yaff properties and converters from str
# this also defines the default order in yaff files
class RecognisedProperties(DefaultProps):

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


PROPERTIES = RecognisedProperties.__annotations__


# properties that must have the calculated value
_non_overridable=[]
# properties where the calculated value may be overridden but results in a notification
_notify_override=[]

def calculated_property(*args, override='accept'):
    """Decorator to take property from property table, if defined; calculate otherwise."""
    if not args:
        # return decorator with these arguments set as extra args
        return partial(calculated_property, override=override)
    fn, *_ = args
    name = fn.__name__

    @property
    @cache
    @wraps(fn)
    def _overridable_fn(self, *args, **kwargs):
        try:
            # get property through vars()
            # only use if explicitly set on the instance
            return vars(self._props)[name]
        except KeyError:
            pass
        return fn(self, *args, **kwargs)

    if override == 'reject':
        _non_overridable.append(name)
    elif override == 'notify':
        _notify_override.append(name)
    return _overridable_fn


###################################################################################################
# Font class


class Font:
    """Representation of font glyphs and metadata."""

    comment_prefix = '_comment_'

    ##########################################################################
    # constructor

    def __init__(self, glyphs=(), comments=None, properties=None):
        """Create new font."""
        if not properties:
            properties = {}
        if not comments:
            comments = {}
        if not isinstance(comments, dict):
            comments = {'': comments}
        self._glyphs = tuple(glyphs)
        # global comments
        self._comments = {_k: _v for _k, _v in comments.items()}
        # filter out comments given as properties starting with #
        self._comments.update({
            _k[len(self.comment_prefix):]: _v for _k, _v in properties.items()
            if _v and _k.startswith(self.comment_prefix)
        })
        properties = {
            _k: _v for _k, _v in properties.items()
            if not _k.startswith(self.comment_prefix)
        }
        # update properties
        # set encoding first so we can set labels
        # NOTE - we must be careful NOT TO ACCESS CACHED PROPERTIES
        #        until the constructor is complete
        properties = self._filter_properties(properties)
        self._props = RecognisedProperties(**properties)
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
        # identify multi-codepoint clusters
        self._grapheme_clusters = set(
            _c for _c in self._chars
            if _c and len(_c) > 1
        )


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

    def _filter_properties(self, properties):
        """Convert properties where needed."""
        if not properties:
            return {}
        properties = {normalise_property(_k): _v for _k, _v in properties.items()}
        for key, converter in reversed(list(PROPERTIES.items())):
            try:
                value = converter(properties.pop(key))
            except KeyError:
                continue
            except ValueError as e:
                logging.error('Could not set property `%s` to %s: %s', key, repr(value), e)
            if key in _non_overridable:
                logging.info(
                    "Property `%s` is not overridable and can't be changed to %s.",
                    key, repr(value)
                )
            else:
                properties[key] = value
                if key in _notify_override:
                    logging.info(
                        'Property `%s` is overridden to %s.',
                        key, repr(value)
                    )
        # append nonstandard properties
        return properties


    ##########################################################################
    # representation

    def __repr__(self):
        """Representation."""
        if not self.nondefault_properties:
            props = '{}'
        else:
            props = (
                '{\n'
                + ''.join(f"  '{_k}': '{_v}',\n" for _k, _v in self.nondefault_properties.items())
                + '}'
            )
        return f"Font(glyphs=<{len(self._glyphs)} glyphs>, properties={props})"


    ##########################################################################
    # copying


    def set_properties(self, **kwargs):
        """Return a copy with amended properties."""
        return Font(
            self._glyphs, self._comments, {**vars(self._props), **kwargs}
        )

    @scriptable(record=False)
    def add_comments(self, comment:str='', property:str=''):
        """
        Return a font with added comments.

        comment: comment to append
        property: property to append commend to; default is global comment
        """
        comments = {**self._comments}
        if property not in self._comments:
            comments[property] = ''
        comments[property] = extend_string(comments[property], comment)
        return Font(self._glyphs, comments, vars(self._props))


    def add_history(self, history):
        """Return a copy with a line added to history."""
        return self.set_properties(history=extend_string(self.history, history))


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

    def charmap(self):
        """Implied character map based on defined chars."""
        return charmaps.create({
            _glyph.codepoint: _glyph.char
            for _glyph in self._glyphs
            if _glyph.codepoint
            and _glyph.char
        }, name=f"implied-{self.name}")


    ##########################################################################
    # text rendering

    def get_glyphs(self, text, missing='raise'):
        """Get tuple of glyphs from text or bytes/codepoints input."""
        if isinstance(text, str):
            iter_text = self._iter_string
        else:
            iter_text = self._iter_codepoints
        return tuple(
            tuple(iter_text(_line, missing=missing))
            for _line in text.splitlines()
        )

    def _iter_string(self, string, missing='raise'):
        """Iterate over string, yielding glyphs."""
        remaining = string
        while remaining:
            # try grapheme clusters first
            for cluster in self._grapheme_clusters:
                if remaining.startswith(cluster):
                    unicode = cluster
                    remaining = remaining[len(cluster):]
                    break
            else:
                unicode, remaining = remaining[0], remaining[1:]
            yield self.get_glyph(key=unicode, missing=missing)

    def _iter_codepoints(self, codepoints, missing='raise'):
        """Iterate over bytes/tuple of int, yielding glyphs."""
        max_length = max(len(_cp) for _cp in self._codepoints.keys())
        remaining = tuple(codepoints)
        while remaining:
            # try multibyte clusters first
            for try_len in range(max_length, 1, -1):
                try:
                    yield self.get_glyph(key=remaining[:try_len], missing='raise')
                except KeyError:
                    pass
                else:
                    remaining = remaining[try_len:]
                    break
            else:
                yield self.get_glyph(key=remaining[:1], missing=missing)
                remaining = remaining[1:]


    ##########################################################################
    # property access

    def get_comments(self, property=''):
        """Get global or property comments."""
        return self._comments.get(property, ())


    @classmethod
    def default(cls, property):
        """Default value for a property."""
        return vars(RecognisedProperties).get(normalise_property(property), '')

    @property
    def nondefault_properties(self):
        """Non-default properties."""
        return vars(self._props)

    def __getattr__(self, attr):
        """Take property from property table."""
        if '_props' not in vars(self):
            logging.error('font._props not defined')
            raise AttributeError(attr)
        if attr.startswith('_'):
            # don't delegate private members
            raise AttributeError(attr)
        return getattr(self._props, attr)


    ##########################################################################
    # calculated properties

    @calculated_property
    def name(self):
        """Name of font."""
        if self.slant == self._property_defaults['slant']:
            slant = ''
        else:
            # title-case
            slant = self.slant.title()
        if self.setwidth == self._property_defaults['setwidth']:
            setwidth = ''
        else:
            setwidth = self.setwidth.title()
        if (slant or setwidth) and self.weight == self._property_defaults['weight']:
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
        if 'source-name' in self._props:
            return self._props.source_name.split('.')[0]
        return ''

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
            _glyph.height - _glyph.ink_offsets.top
            for _glyph in self._glyphs
        )

    @calculated_property
    def descent(self):
        """Get descent (defaults to bottom/vertical offset)."""
        if not self._glyphs:
            return 0
        # usually, descent is positive and offset is negative
        # negative descent would mean font descenders are all above baseline
        return -self.offset.y - min(_glyph.ink_offsets.bottom for _glyph in self._glyphs)

    @calculated_property(override='reject')
    def raster(self):
        """Minimum box encompassing all glyph matrices overlaid at fixed origin."""
        if not self._glyphs:
            return Coord(0, 0)
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
        lefts, bottoms, rights, tops = zip(*(_glyph.ink_bounds for _glyph in self._glyphs))
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
        ink_contained_y = self.line_height >= self.bounding_box.y
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
    def line_height(self):
        """Line height."""
        return self.pixel_size + self.leading


    ##########################################################################
    # font operations

    set = scriptable(set_properties, script_args=PROPERTIES, name='set')

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
        glyphs = (_glyph for _glyph in glyphs if _glyph is not None)
        return Font(glyphs, self._comments, vars(self._props))

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
        return Font(glyphs, self._comments, vars(self._props))

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
        return Font(glyphs, self._comments, vars(self._props))

    # replace with clone(glyphs=.., comments=.., properties=..)
    def with_glyph(self, glyph):
        """Return a font with a glyph added."""
        glyphs = list(self._glyphs)
        glyphs.append(glyph)
        return Font(glyphs, self._comments, vars(self._props))


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
            return Font(glyphs, self._comments, vars(self._props))

        locals()[_name] = _modify_glyphs


# scriptable font/glyph operations
operations = get_scriptables(Font)
