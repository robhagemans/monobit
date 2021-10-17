"""
monobit.font - representation of font

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from functools import wraps
from typing import NamedTuple
import numbers
import logging
import unicodedata

from .base import scriptable
from .glyph import Glyph
from .encoding import charmaps
from .label import Label, Tag, Char, Codepoint, label


def number(value=0):
    """Convert to int or float."""
    if isinstance(value, str):
        value = float(value)
    if not isinstance(value, numbers.Real):
        raise ValueError("Can't convert `{}` to number.".format(value))
    if value == int(value):
        value = int(value)
    return value


class Coord(NamedTuple):
    """Coordinate tuple."""
    x: int
    y: int

    def __str__(self):
        return '{} {}'.format(self.x, self.y)

    @classmethod
    def create(cls, coord=0):
        if isinstance(coord, numbers.Real):
            return cls(coord, coord)
        if isinstance(coord, str):
            splits = coord.split(' ')
            if len(splits) == 1:
                return cls(number(splits[0]), number(splits[0]))
            elif len(splits) == 2:
                return cls(number(splits[0]), number(splits[1]))
        if isinstance(coord, tuple):
            if len(coord) == 2:
                return cls(number(coord[0]), number(coord[1]))
        raise ValueError("Can't convert `{}` to coordinate pair.".format(coord))


class KerningTable:
    """(str, str) -> int."""

    def __init__(self, table=None):
        """Set up kerning table."""
        if not table:
            table = {}
        if isinstance(table, str):
            table = {
                tuple(_row.split()[:2]): _row.split()[2]
                for _row in table.splitlines()
            }
        self._table = {
            (_k[0], _k[1]): int(_v)
            for _k, _v in table.items()
        }

    def __str__(self):
        """Convert kerning table to multiline string."""
        return '\n'.join(
            f'{_k[0]} {_k[1]} {_v}'
            for _k, _v in self._table.items()
        )

    def items(self):
        """Iterate over items."""
        return self._table.items()



# recognised yaff properties and converters from str
# this also defines the default order in yaff files
PROPERTIES = {

    # naming - can be determined from source file if needed
    'name': str, # full human name
    'family': str, # typeface/font family

    # font metadata
    # can't be calculated
    'foundry': str, # author or issuer
    'copyright': str, # copyright string
    'notice': str, # e.g. license string
    'revision': str, # font version

    # font description
    # can't be calculated
    'style': str, # serif, sans, etc.
    'point-size': number, # nominal point size
    'weight': str, # normal, bold, light, etc.
    'slant': str, # roman, italic, oblique, etc
    'setwidth': str, # normal, condensed, expanded, etc.
    'decoration': str, # underline, strikethrough, etc.

    # target info
    # can't be calculated
    'device': str, # target device name
    # calculated or given
    'dpi': Coord.create, # target resolution in dots per inch

    # summarising quantities
    # determined from the bitmaps only
    'spacing': str, # proportional, monospace, character-cell, multi-cell
    'max-raster-size': Coord.create, # maximum raster (not necessarily ink) width/height
    'bounding-box': Coord.create, # overall ink bounds - overlay all glyphs with fixed origin and determine maximum ink extent
    'average-advance': number, # average advance width, rounded to tenths
    'cap-advance': int, # advance width of LATIN CAPITAL LETTER X

    # descriptive typographic quantities
    # can be calculated or given
    'x-height': int, # height of lowercase x relative to baseline
    'cap-height': int, # height of capital relative to baseline
    # can't be calculated, don't currently affect rendering
    # might affect e.g. composition of characters
    'ascent': int, # recommended typographic ascent relative to baseline (not necessarily equal to top)
    'descent': int, # recommended typographic descent relative to baseline (not necessarily equal to bottom)
    'pixel-size': int, # nominal pixel size, always equals ascent + descent

    # metrics
    # can't be calculated, affect rendering
    # positioning relative to origin
    'direction': str, # left-to-right, right-to-left
    'offset': Coord.create, # (horiz, vert) offset from origin to matrix start
    'tracking': int, # horizontal offset from matrix end to next origin
    'leading': int, # interline spacing, defined as (pixels between baselines) - (max raster height)

    # character set
    # can't be calculated, affect rendering
    'encoding': charmaps.normalise,
    'default-char': label, # use question mark to replace missing glyph
    'word-boundary': label, # word-break character (usually space)

    # conversion metadata
    # can't be calculated, informational
    'converter': str,
    'source-name': str,
    'source-format': str,

    # kerning table (at the end because it's long)
    # pairwise kerning (defined as adjustment to tracking)
    'kerning': KerningTable,
}

# calculated properties
# properties that must have the calculated value
_NON_OVERRIDABLE = ('spacing', 'max-raster-size', 'pixel-size', 'average-advance', 'cap-advance',)
# properties where the calculated value may be overridden
_OVERRIDABLE = ('dpi', 'name', 'family', 'x-height', 'cap-height',)


class Font:
    """Representation of font glyphs and metadata."""

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
        self._comments = {_k: tuple(_v) for _k, _v in comments.items()}
        # update properties
        self._properties = {}
        if properties:
            properties = {self._normalise_property(_k): _v for _k, _v in properties.items()}
            for key, converter in reversed(list(PROPERTIES.items())):
                try:
                    value = converter(properties.pop(key))
                except KeyError:
                    continue
                except ValueError as e:
                    logging.error('Could not set property %s: %s', key, e)
                # don't set property values that equal the default
                # we need to ensure we use underscore variants, or default functions won't get called
                default_value = getattr(self, key.replace('-', '_'))
                if value != default_value:
                    if key in _NON_OVERRIDABLE:
                        logging.warning(
                            "Property `%s` value can't be set to %s. Keeping calculated value %s.",
                            key, str(value), str(default_value)
                        )
                    else:
                        self._properties[key] = value
                        if key in _OVERRIDABLE:
                            logging.info(
                                'Property `%s` value set to %s, while calculated value is %s.',
                                key, str(value), str(default_value)
                            )
            # append nonstandard properties
            self._properties.update(properties)
        # set encoding first so we can set labels
        self._add_encoding_data()
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

    def _add_encoding_data(self):
        """Add unicode annotations for codepage."""
        has_codepoint = any(_glyph.codepoint for _glyph in self._glyphs)
        has_char = any(_glyph.char for _glyph in self._glyphs)
        # update glyph codepoints
        # use index as codepoint if no codepoints or chars set
        if not has_codepoint and not has_char:
            self._glyphs = tuple(
                _glyph.set_annotations(codepoint=(_index,))
                for _index, _glyph in enumerate(self._glyphs)
            )
        # update glyph unicode annotations
        encoding = self._get_encoder()
        if encoding is not None:
            self._glyphs = [
                _glyph.set_encoding_annotations(encoding)
                for _glyph in self._glyphs
            ]

    def _get_encoder(self):
        """Get encoding object."""
        try:
            return charmaps[self._properties['encoding']]
        except KeyError:
            return None

    def _normalise_property(self, property):
        """Return property name with underscores replaced."""
        # don't modify namespace properties
        if '.' in property:
            return property
        return property.replace('_', '-')

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
        if isinstance(key, Label):
            return self.get_index(**key.indexer())
        if 1 != len([_indexer for _indexer in (key, char, codepoint, tag) if _indexer is not None]):
            raise ValueError('get_index() takes exactly one parameter.')
        if key is not None:
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
                return self._tags[tag]
            except KeyError:
                raise KeyError(f'No glyph found matching tag={Tag(tag)}') from None
        if char is not None:
            try:
                return self._chars[char]
            except KeyError:
                raise KeyError(f'No glyph found matching char={Char(char)}') from None
        try:
            return self._codepoints[codepoint]
        except KeyError:
            raise KeyError(f'No glyph found matching codepoint={Codepoint(codepoint)}') from None


    def get_default_glyph(self):
        """Get default glyph; empty if not defined."""
        try:
            return self.get_glyph(self.default_char)
        except KeyError:
            return self.get_empty_glyph()

    def get_empty_glyph(self):
        """Get blank glyph with zero advance (or minimal if zero not possible)."""
        return Glyph.blank(max(0, -self.offset.x - self.tracking), self.max_raster_size.y)


    ##########################################################################
    # text / character access

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

    def _iter_string(self, string):
        """Iterate over string, yielding unicode characters."""
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
            yield unicode

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

    def render(self, text, fore=1, back=0, *, margin=(0, 0), scale=(1, 1), missing='default'):
        """Render text string to bitmap."""
        if isinstance(text, str):
            chars = [
                list(self._iter_string(_line))
                for _line in text.splitlines()
            ]
            glyphs = [
                [self.get_glyph(_c, missing=missing) for _c in _line]
                for _line in chars
            ]
        else:
            glyphs = [
                list(self._iter_codepoints(_line, missing=missing))
                for _line in text.splitlines()
            ]
            chars = [[_g.char for _g in _line] for _line in glyphs]
        # kerning currently only works for str
        if self.kerning:
            kerning = {
                (self.get_glyph(_key[0]).char, self.get_glyph(_key[1]).char): _value
                for _key, _value in self.kerning.items()
            }
            kernings = [
                [
                    kerning.get((_char, _next), 0)
                    for _char, _next in zip(_line[:-1], _line[1:])
                ] + [0]
                for _line in chars
            ]
        else:
            kernings = [[0] * len(_line) for _line in glyphs]
        # determine dimensions
        margin_x, margin_y = margin
        if not glyphs:
            width = 2 * margin_x
        else:
            width = 2 * margin_x + max(
                (
                    sum(_glyph.width for _glyph in _row)
                    + (self.offset.x + self.tracking) * len(_row)
                )
                for _row in glyphs
            )
        line_height = self.max_raster_size.y + self.leading
        height = 2 * margin_y + line_height * len(glyphs)
        line_output = [
            [0 for _ in range(width)]
            for _ in range(height)
        ]
        # get to initial origin
        grid_top = margin_y
        for row, kernrow in zip(glyphs, kernings):
            x, y = 0, 0
            for glyph, kerning in zip(row, kernrow):
                matrix = glyph.as_matrix(1, 0)
                # apply pre-offset so that x,y is logical coordinate of grid origin
                x, y = x + self.offset.x, y + self.offset.y
                # grid coordinates of grid origin
                grid_x, grid_y = margin_x + x, grid_top + self.ascent - y
                # add ink, taking into account there may be ink already in case of negative bearings
                for work_y in range(glyph.height):
                    y_index = grid_y - work_y - 1
                    if 0 <= y_index < height:
                        row = line_output[y_index]
                        for work_x, ink in enumerate(matrix[glyph.height - work_y - 1]):
                            if 0 <= grid_x + work_x < width:
                                row[grid_x + work_x] |= ink
                # advance
                x += glyph.width
                # apply post-offset
                x, y = x + self.tracking + kerning, y - self.offset.y
            grid_top += line_height
        output = []
        output.extend(line_output)
        scale_x, scale_y = scale
        output = tuple(
            tuple((fore if _item else back) for _item in _row for _ in range(scale_x))
            for _row in output for _ in range(scale_y)
        )
        return output


    ##########################################################################
    # comments

    def get_comments(self, property=''):
        """Get global or property comments."""
        return self._comments.get(property, ())

    @scriptable
    def add_comments(self, new_comment:str='', property:str=''):
        """Return a font with added comments."""
        comments = {**self._comments}
        if property not in self._comments:
            comments[property] = ()
        comments[property] += tuple(new_comment.splitlines())
        return Font(self._glyphs, comments, self._properties)

    # move to glyph.with_name()
    @scriptable
    def add_glyph_names(self):
        """Add unicode glyph names as comments, if no comment already exists."""
        glyphs = list(self._glyphs)
        for char, index in self._chars.items():
            name = ', '.join(unicodedata.name(_cp, '') for _cp in char)
            if name and not self._glyphs[index].comments:
                try:
                    category = unicodedata.category(char)
                except TypeError:
                    # multi-codepoint glyphs
                    category = ''
                if category.startswith('C'):
                    description = '{}'.format(name)
                else:
                    description = '[{}] {}'.format(char, name)
                glyphs[index] = glyphs[index].add_annotations(comments=(description,))
        return Font(glyphs, self._comments, self._properties)


    ##########################################################################
    # properties

    @scriptable
    def set_encoding(self, encoding:str=''):
        """
        Return a copy with codepoints relabelled through a different codepage.
        """
        properties = {**self._properties}
        properties['encoding'] = encoding
        return Font(self._glyphs, self._comments, properties)

    def set_properties(self, **kwargs):
        """Return a copy with amended properties."""
        return Font(
            self._glyphs, self._comments, {**self._properties, **kwargs}
        )

    @property
    def nondefault_properties(self):
        """Non-default properties."""
        return {**self._properties}

    def __getattr__(self, attr):
        """Take property from property table."""
        attr = self._normalise_property(attr)
        try:
            return self._properties[attr]
        except KeyError:
            pass
        try:
            # if in yaff property list, return default
            return self._yaff_properties[attr]
        except KeyError:
            pass
        try:
            # if in yaff property list, return default
            return PROPERTIES[attr]()
        except KeyError as e:
            raise AttributeError(e) from e

    def yaffproperty(fn):
        """Take property from property table, if defined; calculate otherwise."""
        @wraps(fn)
        def _cached_fn(self, *args, **kwargs):
            try:
                return self._properties[self._normalise_property(fn.__name__)]
            except KeyError:
                pass
            return fn(self, *args, **kwargs)
        return property(_cached_fn)

    # default properties

    _yaff_properties = {
        'revision': '0', # font version
        'weight': 'regular', # normal, bold, light, etc.
        'slant': 'roman', # roman, italic, oblique, etc
        'setwidth': 'normal', # normal, condensed, expanded, etc.
        'direction': 'left-to-right', # left-to-right, right-to-left
        'encoding': '',
        'word-boundary': label('u+0020'), # word-break character (usually space)
    }

    @yaffproperty
    def name(self):
        """Name of font."""
        weight = '' if self.weight == self._yaff_properties['weight'] else self.weight.title()
        slant = '' if self.slant == self._yaff_properties['slant'] else self.slant.title()
        #encoding = '' if self.encoding == self._yaff_properties['encoding'] else f'({self.encoding})'
        return ' '.join(
            str(_x) for _x in (self.family, weight, slant, self.point_size) if _x
        )

    @yaffproperty
    def family(self):
        """Name of font family."""
        # use source name if no family name defined
        if 'source-name' in self._properties:
            return self.source_name.split('.')[0]
        return ''

    @yaffproperty
    def point_size(self):
        """Nominal point height."""
        # assume 72 points per inch (officially 72.27 pica points per inch)
        # if dpi not given assumes 72 dpi, so point-size == pixel-size
        return int(self.pixel_size * self.dpi.y / 72.)

    @yaffproperty
    def pixel_size(self):
        """Get nominal pixel size (ascent + descent)."""
        if not self._glyphs:
            return 0
        return self.ascent + self.descent

    @yaffproperty
    def ascent(self):
        """Get ascent (defaults to max ink height above baseline)."""
        if not self._glyphs:
            return 0
        return self.offset.y + max(
            # ink_offsets[3] is offset from top
            _glyph.height - _glyph.ink_offsets[3]
            for _glyph in self._glyphs
        )

    @yaffproperty
    def descent(self):
        """Get descent (defaults to bottom/vertical offset)."""
        if not self._glyphs:
            return 0
        # ink_offsets[1] is offset from bottom
        # usually, descent is positive and offset is negative
        # negative descent would mean font descenders are all above baseline
        return -self.offset.y - min(_glyph.ink_offsets[1] for _glyph in self._glyphs)

    @yaffproperty
    def dpi(self):
        """Target screen resolution in dots per inch."""
        # if point-size has been overridden and dpi not set, determine from pixel-size & point-size
        if 'point-size' in self._properties:
            dpi = (72 * self.pixel_size) // self.point_size
            return Coord(dpi, dpi)
        # default: 72 dpi; 1 point == 1 pixel
        return Coord(72, 72)

    @property
    def max_raster_size(self):
        """Get maximum raster width and height, in pixels."""
        if not self._glyphs:
            return Coord(0, 0)
        return Coord(
            max(_glyph.width for _glyph in self._glyphs),
            max(_glyph.height for _glyph in self._glyphs)
        )

    @property
    def bounding_box(self):
        """Minimum bounding box encompassing all glyphs at fixed origin."""
        if not self._glyphs:
            return Coord(0, 0)
        # all glyphs share the font's offset
        # so to align glyph origins we need to align raster origins - bottom left for LTR fonts
        lefts, bottoms, rights, tops = zip(*(_glyph.ink_coordinates for _glyph in self._glyphs))
        return Coord(max(rights) - min(lefts), max(tops) - min(bottoms))

    @yaffproperty
    def default_char(self):
        """Label for default character."""
        repl = '\ufffd'
        if repl not in self._chars:
            repl = ''
        return Char(repl)

    @yaffproperty
    def average_advance(self):
        """Get average glyph advance width, rounded to tenths of pixels."""
        if not self._glyphs:
            return self.offset.x + self.tracking
        return (
            self.offset.x
            + sum(_glyph.width for _glyph in self._glyphs) / len(self._glyphs)
            + self.tracking
        )

    @yaffproperty
    def spacing(self):
        """Monospace or proportional spacing."""
        if not self._glyphs:
            return 'character-cell'
        # don't count void glyphs (0 width and/or height) to determine whether it's monospace
        widths = set(_glyph.width for _glyph in self._glyphs if _glyph.width)
        heights = set(_glyph.height for _glyph in self._glyphs if _glyph.height)
        min_width = min(widths)
        # mono- or multi-cell fonts: equal heights, no ink outside cell, widths are fixed multiples
        if (
                len(heights) == 1
                and self.offset.x >= 0 and self.tracking >= 0 and self.leading >= 0
                and min_width > 3 and not any(_width % min_width for _width in widths)
            ):
            if len(widths) == 1:
                return 'character-cell'
            return 'multi-cell'
        if len(widths) == 1:
            return 'monospace'
        return 'proportional'

    @yaffproperty
    def cap_advance(self):
        """Advance width of uppercase X."""
        try:
            return self.get_glyph('X').width + self.offset.x + self.tracking
        except KeyError:
            return 0

    @yaffproperty
    def x_height(self):
        """Ink height of lowercase x."""
        try:
            return self.get_glyph('x').ink_height
        except KeyError:
            return 0

    @yaffproperty
    def cap_height(self):
        """Ink height of uppercase X."""
        try:
            return self.get_glyph('X').ink_height
        except KeyError:
            return 0

    ##########################################################################
    # font operations

    @scriptable
    def subset(self, keys:set=(), tags:set=()):
        """Return a subset of the font."""
        keys = list(keys)
        tags = list(tags)
        glyphs = (
            [self.get_glyph(_key, missing=None) for _key in keys]
            + [self.get_glyph(tag=_tag, missing=None) for _tag in tags]
        )
        glyphs = (_glyph for _glyph in glyphs if _glyph is not None)
        return Font(glyphs, self._comments, self._properties)

    @scriptable
    def without(self, keys:set=(), tags:set=()):
        """Return a font excluding a subset."""
        keys = set(keys)
        tags = set(tags)
        if not keys and not tags:
            return self
        glyphs = [
            _glyph
            for _glyph in self._glyphs
            if (
                _glyph.char not in keys
                and _glyph.codepoint not in keys
                and not (set(_glyph.tags) & tags)
            )
        ]
        return Font(glyphs, self._comments, self._properties)

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
                    glyph = glyph.set_annotations(tags=new_tags, codepoint=new_codepoint)
                else:
                    glyph = glyph.set_annotations(tags=new_tags)
                glyphs.append(glyph)
        return Font(glyphs, self._comments, self._properties)

    # replace with clone(glyphs=.., comments=.., properties=..)
    def with_glyph(self, glyph):
        """Return a font with a glyph added."""
        glyphs = list(self._glyphs)
        glyphs.append(glyph)
        return Font(glyphs, self._comments, self._properties)


    ##########################################################################
    # inject Glyph operations into Font

    for _name, _func in Glyph.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a font with modified glyphs."""
                glyphs = [
                    operation(_glyph, *args, **kwargs)
                    for _glyph in self._glyphs
                ]
                return Font(glyphs, self._comments, self._properties)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
