"""
monobit.glyph - representation of single glyph

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import numbers
from typing import NamedTuple

try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()

from .encoding import is_graphical
from .labels import Codepoint, Char, Tag, to_label
from .raster import Raster
from .struct import (
    DefaultProps, normalise_property, extend_string,
    writable_property, as_tuple, checked_property
)


# sentinel object
NOT_SET = object()


##############################################################################
# base data types

def number(value=0):
    """Convert to int or float."""
    if isinstance(value, str):
        value = float(value)
    if not isinstance(value, numbers.Real):
        raise ValueError("Can't convert `{}` to number.".format(value))
    if value == int(value):
        value = int(value)
    return value


class Bounds(NamedTuple):
    """4-coordinate tuple."""
    left: int
    bottom: int
    right: int
    top: int


class Coord(NamedTuple):
    """Coordinate tuple."""
    x: int
    y: int

    def __str__(self):
        return '{} {}'.format(self.x, self.y)

    @classmethod
    def create(cls, coord=0):
        if isinstance(coord, Coord):
            return coord
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
        if not coord:
            return cls(0, 0)
        raise ValueError("Can't convert `{}` to coordinate pair.".format(coord))

    def __add__(self, other):
        return Coord(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Coord(self.x - other.x, self.y - other.y)

    def __bool__(self):
        return bool(self.x or self.y)


##############################################################################
# kerning table

class KernTable(dict):
    """char -> int."""

    # we use from (dict):
    # - empty table is falsy
    # - get(), items(), iter()

    def __init__(self, table=None):
        """Set up kerning table."""
        if not table:
            table = {}
        if isinstance(table, str):
            table = dict(
                _row.split(None, 1)
                for _row in table.splitlines()
            )
        table = {
            to_label(_k): int(_v)
            for _k, _v in table.items()
        }
        super().__init__(table)

    def __str__(self):
        """Convert kerning table to multiline string."""
        return '\n'.join(
            f'{_k} {_v}'
            for _k, _v in self.items()
        )

    def get_for_glyph(self, second):
        """Get kerning amount for given second glyph."""
        try:
            return self[second.char]
        except KeyError:
            pass
        try:
            return self[second.codepoint]
        except KeyError:
            pass
        for tag in second.tags:
            try:
                return self[Tag(tag)]
            except KeyError:
                pass
        # no kerning is zero kerning
        return 0


##############################################################################
# glyph properties

class GlyphProperties(DefaultProps):
    """Recognised properties for Glyph."""

    # horizontal offset from leftward origin to matrix left edge
    left_bearing: int
    # horizontal offset from matrix right edge to rightward origin
    right_bearing: int
    # upward offset from origin to matrix bottom
    shift_up: int
    # downward offset from origin to matrix left edge - equal to -shift_up
    shift_down: int
    # kerning - pairwaise additional right-bearing
    right_kerning: KernTable
    # kerning - pairwaise additional left-bearing
    left_kerning: KernTable

    # vertical metrics
    # vertical offset from upward origin to matrix top edge
    top_bearing: int
    # vertical offset from matrix bottom edge to downward origin
    bottom_bearing: int
    # leftward offset from origin to matrix left edge
    shift_left: int


    @checked_property
    def shift_down(self):
        """Downward shift - negative of shift-up."""
        return -self.shift_up

    @checked_property
    def advance_width(self):
        """Internal advance width of glyph, including internal bearings."""
        return self.left_bearing + self.width + self.right_bearing

    @checked_property
    def advance_height(self):
        """Internal advance width of glyph, including internal bearings."""
        return self.top_bearing + self.height + self.bottom_bearing

    @checked_property
    def width(self):
        """Raster width of glyph."""
        return self._glyph.get_width()

    @checked_property
    def height(self):
        """Raster height of glyph."""
        return self._glyph.get_height()

    @checked_property
    def ink_bounds(self):
        """Minimum box encompassing all ink, in glyph origin coordinates."""
        bounds = Bounds(
            left=self.left_bearing + self.padding.left,
            bottom=self.shift_up + self.padding.bottom,
            right=self.left_bearing + self.width - self.padding.right,
            top=self.shift_up + self.height - self.padding.top,
        )
        # more intuitive result for blank glyphs
        if bounds.left == bounds.right or bounds.top == bounds.bottom:
            return Bounds(0, 0, 0, 0)
        return bounds

    @checked_property
    def bounding_box(self):
        """Dimensions of minimum bounding box encompassing all ink."""
        return Coord(
            self.ink_bounds.right - self.ink_bounds.left,
            self.ink_bounds.top - self.ink_bounds.bottom
        )

    @checked_property
    def padding(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        return Bounds(*self._glyph.get_padding())


    ##########################################################################
    # deprecated compatibility synonymms

    @writable_property('kern_to')
    def kern_to(self):
        """Deprecated synonym of right-kerning."""
        return self.right_kerning

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


##############################################################################
# glyph

class Glyph(Raster):
    """Single glyph."""

    def __init__(
            self, pixels=(), *,
            labels=(), codepoint=b'', char='', tags=(), comment='',
            **properties
        ):
        """Create glyph from tuple of tuples."""
        # raster data
        super().__init__(pixels)
        # labels
        for label in labels:
            label = to_label(label)
            if isinstance(label, Char):
                char = char or label
            elif isinstance(label, Codepoint):
                codepoint = codepoint or label
            else:
                tags += (label,)
        self._codepoint = Codepoint(codepoint)
        self._char = Char(char)
        self._tags = tuple(Tag(_tag) for _tag in tags if _tag)
        # comment
        if not isinstance(comment, str):
            raise TypeError('Glyph comment must be a single string.')
        self._comment = comment
        # recognised properties
        # access needed for calculated properties
        self._props = GlyphProperties(_glyph=self, **properties)


    ##########################################################################
    # representation

    def __repr__(self):
        """Text representation."""
        elements = (
            f"char={repr(self._char)}" if self._char else '',
            f"codepoint={repr(self._codepoint)}" if self._codepoint else '',
            f"tags={repr(self._tags)}" if self._tags else '',
            "comment=({})".format(
                "\n  '" + "\n',\n  '".join(self.comment.splitlines()) + "'"
            ) if self._comment else '',
            ', '.join(f'{_k}={_v}' for _k, _v in self.properties.items()),
            "pixels=({})".format(
                self.as_text(start="\n  '", end="',")
            ) if self._pixels else ''
        )
        return '{}({})'.format(
            type(self).__name__,
            ', '.join(_e for _e in elements if _e)
        )


    ##########################################################################
    # copying

    def modify(
            self, pixels=NOT_SET, *,
            labels=(), tags=NOT_SET, char=NOT_SET, codepoint=NOT_SET, comment=NOT_SET,
            **kwargs
        ):
        """Return a copy of the glyph with changes."""
        if pixels is NOT_SET:
            pixels = self._pixels
        if tags is NOT_SET:
            tags = self._tags
        if codepoint is NOT_SET:
            codepoint = self._codepoint
        if char is NOT_SET:
            char = self._char
        if comment is NOT_SET:
            comment = self._comment
        return type(self)(
            tuple(pixels),
            labels=labels,
            codepoint=Codepoint(codepoint),
            char=Char(char),
            tags=tuple(Tag(_t) for _t in tags),
            comment=comment,
            **{**self.properties, **kwargs}
        )

    def label(
            self, codepoint_from=None, char_from=None,
            tag_from=None, comment_from=None,
            overwrite=False
        ):
        """
           Set labels or comment using provided encoder or tagger object.

           char_from: Encoder object used to set char labels
           codepoint_from: Encoder object used to set codepoint labels
           tag_from: Tagger object used to set tag labels
           comment_from: Tagger object used to set comment
           overwrite: overwrite codepoint or char if already given
        """
        if sum(
                _arg is not None
                for _arg in (codepoint_from, char_from, tag_from, comment_from)
            ) > 1:
            raise ValueError(
                'Can only set one of character, codepoint, tag or comment with one label() call. '
                'Use separate calls to set more.'
           )
        labels = self.get_labels()
        # use codepage to find codepoint if not set
        if codepoint_from and (overwrite or not self.codepoint):
            return self.modify(codepoint=codepoint_from.codepoint(*labels))
        # use codepage to find char if not set
        if char_from and(overwrite or not self.char):
            return self.modify(char=char_from.char(*labels))
        if tag_from:
            return self.modify(
                tags=self.tags + (tag_from.tag(*labels),)
            )
        if comment_from:
            return self.modify(
                comment=extend_string(self.comment, comment_from.comment(*labels))
            )
        return self

    def append(
            self, *,
            comment=None, **properties
        ):
        """Return a copy of the glyph with changes."""
        if not comment:
            comment = ''
        comment = extend_string(self._comment, comment)
        for property, value in properties.items():
            if property in self._props:
                properties[property] = extend_string(self._props[property], value)
        # do not record glyph history
        try:
            history = properties.pop('history')
            #logging.debug("Ignoring glyph history '%s'", history)
        except KeyError:
            pass
        return self.modify(
            comment=comment,
            **properties
        )

    def drop(self, *args):
        """Remove labels, comment or properties."""
        args = list(args)
        try:
            args.remove('pixels')
            pixels = ()
        except ValueError:
            pixels = self._pixels
        try:
            args.remove('char')
            char = ''
        except ValueError:
            char = self._char
        try:
            args.remove('codepoint')
            codepoint = ()
        except ValueError:
            codepoint = self._codepoint
        try:
            args.remove('tags')
            tags = ()
        except ValueError:
            tags = self._tags
        try:
            args.remove('comment')
            comment = ''
        except ValueError:
            comment = self._comment
        args = [normalise_property(_arg) for _arg in args]
        properties = {
            _k: _v
            for _k, _v in self.properties.items()
            if normalise_property(_k) not in args
        }
        return type(self)(
            pixels,
            tags=tags, codepoint=codepoint, char=char,
            comment=comment,
            **properties
        )


    ##########################################################################
    # property access

    def __getattr__(self, attr):
        """Take attribute from property table if not defined here."""
        if '_props' not in vars(self):
            logging.error(type(self).__name__ + '._props not defined')
            raise AttributeError(attr)
        if attr.startswith('_'):
            # don't delegate private members
            raise AttributeError(attr)
        return getattr(self._props, attr)

    @property
    def comment(self):
        return self._comment

    @classmethod
    def default(cls, property):
        """Default value for a property."""
        return vars(GlyphProperties).get(normalise_property(property), '')

    @property
    def properties(self):
        """Non-defaulted properties in order of default definition list."""
        return {
            _k.replace('_', '-'): self._props[_k]
            for _k in self._props if not _k.startswith('_')
        }


    ##########################################################################
    # label access

    @property
    def tags(self):
        return self._tags

    @property
    def char(self):
        return self._char

    @property
    def codepoint(self):
        return self._codepoint

    def get_labels(self):
        """Get glyph labels."""
        labels = []
        # don't write out codepoints for unicode fonts as we have u+XXXX already
        if self.codepoint:
            labels.append(self._codepoint)
        if self.char:
            labels.append(self._char)
        labels.extend(self._tags)
        return tuple(labels)
