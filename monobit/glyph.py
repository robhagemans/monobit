"""
monobit.glyph - representation of single glyph

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()

from .encoding import is_graphical
from .labels import Codepoint, Char, Tag, to_label
from .raster import Raster, NOT_SET
from .struct import (
    DefaultProps, normalise_property, extend_string,
    writable_property, as_tuple, checked_property
)
from .basetypes import Coord, Bounds, number
from .scripting import scriptable


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

    # compatibility synonyms
    kern_to: KernTable
    tracking: int
    offset: Coord.create


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
        return self._glyph.width

    @checked_property
    def height(self):
        """Raster height of glyph."""
        return self._glyph.height

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
        return self._glyph.padding


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
            labels=(), codepoint=b'', char='', tag='', comment='',
            _0=NOT_SET, _1=NOT_SET,
            **properties
        ):
        """Create glyph from tuple of tuples."""
        # raster data
        super().__init__(pixels, _0=_0, _1=_1)
        # labels
        labels = (
            Char(char), Codepoint(codepoint), Tag(tag),
            *(to_label(_l) for _l in labels)
        )
        self._labels = tuple(_l for _l in labels if _l)
        # comment
        if not isinstance(comment, str):
            raise TypeError('Glyph comment must be a single string.')
        self._comment = comment
        # recognised properties
        # access needed for calculated properties
        self._props = GlyphProperties(_glyph=self, **properties)

    def __eq__(self, other):
        """Equality."""
        if (self.width, self.height) != (other.width, other.height):
            return False
        for p in (*self.properties.keys(), *other.properties.keys()):
            p = normalise_property(p)
            if not getattr(self, p) == getattr(other, p):
                return False
        return self.as_matrix() == other.as_matrix()


    ##########################################################################
    # representation

    def __repr__(self):
        """Text representation."""
        elements = (
            f"labels={repr(self._labels)}" if self._labels else '',
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
            labels=NOT_SET, tag=NOT_SET, char=NOT_SET, codepoint=NOT_SET,
            comment=NOT_SET,
            _0=NOT_SET, _1=NOT_SET,
            **kwargs
        ):
        """Return a copy of the glyph with changes."""
        if pixels is NOT_SET:
            pixels = self._pixels
        if tag is NOT_SET:
            tag = ''
        if codepoint is NOT_SET:
            codepoint = b''
        if char is NOT_SET:
            char = ''
        if labels is NOT_SET:
            labels = self._labels
        if comment is NOT_SET:
            comment = self._comment
        if _0 is NOT_SET:
            _0 = self._0
        if _1 is NOT_SET:
            _1 = self._1
        return type(self)(
            tuple(pixels),
            labels=labels,
            codepoint=codepoint,
            char=char,
            tag=tag,
            comment=comment,
            _0=_0, _1=_1,
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
            return self.modify(tag=tag_from.tag(*labels))
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
            args.remove('labels')
            labels = ()
        except ValueError:
            labels = self._labels
        try:
            args.remove('comment')
            comment = ''
        except ValueError:
            comment = self._comment
        args = tuple(normalise_property(_arg) for _arg in args)
        properties = {
            _k: _v
            for _k, _v in self.properties.items()
            if normalise_property(_k) not in args
        }
        return type(self)(
            pixels,
            labels=labels,
            comment=comment,
            _0=self._0, _1=self._1,
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
        return tuple(_l for _l in self._labels if isinstance(_l, Tag))

    @property
    def chars(self):
        return tuple(_l for _l in self._labels if isinstance(_l, Char))

    @property
    def codepoints(self):
        return tuple(_l for _l in self._labels if isinstance(_l, Codepoint))

    @property
    def char(self):
        if self.chars:
            return self.chars[0]
        return Char()

    @property
    def codepoint(self):
        if self.codepoints:
            return self.codepoints[0]
        return Codepoint()

    def get_labels(self):
        """Get glyph labels."""
        return self._labels


    ##########################################################################
    # glyph transformations

    @scriptable
    def reduce(self, *, adjust_metrics:bool=True, blank_empty:bool=True):
        """
        Return a glyph reduced to the bounding box.

        adjust_metrics: make the operation render-invariant (default: True)
        blank_empty: reduce blank glyphs to empty (default: True)
        """
        if (not blank_empty) and self.is_blank():
            return self.crop(
                self.width, self.height-1, 0, 0,
                adjust_metrics=adjust_metrics
            )
        return self.crop(*self.padding, adjust_metrics=adjust_metrics)


    @scriptable
    def mirror(self, *, adjust_metrics:bool=True):
        """
        Reverse pixels horizontally.

        adjust_metrics: also reverse metrics (default: True)
        """
        glyph = super().mirror()
        if adjust_metrics:
            return glyph.modify(
                left_bearing=self.right_bearing,
                right_bearing=self.left_bearing,
                shift_left=-self.shift_left
                #shift_left around central axis, so should differ at most 1 pixel
            )
        return glyph

    @scriptable
    def flip(self, *, adjust_metrics:bool=True):
        """
        Reverse pixels vertically.

        adjust_metrics: also reverse metrics (default: True)
        """
        glyph = super().flip()
        if adjust_metrics:
            return glyph.modify(
                top_bearing=self.bottom_bearing,
                bottom_bearing=self.top_bearing,
                # flip about baseline
                shift_up=-self.height - self.shift_up
            )
        # Font should adjust ascent <-> descent and global bearings
        return glyph

    @scriptable
    def transpose(self, *, adjust_metrics:bool=True):
        """
        Transpose glyph.

        adjust_metrics: also transpose metrics (default: True)
        """
        glyph = super().transpose()
        if adjust_metrics:
            return glyph.modify(
                top_bearing=self.left_bearing,
                left_bearing=self.top_bearing,
                right_bearing=self.bottom_bearing,
                bottom_bearing=self.right_bearing,
                shift_left=self.shift_up+self.height//2,
                shift_up=self.shift_left-self.width//2
            )

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
        # reduce raster
        glyph = super().crop(left, bottom, right, top)
        if adjust_metrics:
            return glyph.modify(
                # horizontal metrics
                left_bearing=self.left_bearing + left,
                right_bearing=self.right_bearing + right,
                shift_up=self.shift_up + bottom,
                # vertical metrics
                top_bearing=self.top_bearing + top,
                bottom_bearing=self.bottom_bearing + bottom,
                shift_left=self.shift_left + self.width//2 - glyph.width//2,
            )
        # a Font may also have to ensure line_height remains unchanged
        return glyph

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
        # reduce raster
        glyph = super().expand(left, bottom, right, top)
        if adjust_metrics:
            return glyph.modify(
                # horizontal metrics
                left_bearing=self.left_bearing - left,
                right_bearing=self.right_bearing - right,
                shift_up=self.shift_up - bottom,
                # vertical metrics
                top_bearing=self.top_bearing - top,
                bottom_bearing=self.bottom_bearing - bottom,
                shift_left=self.shift_left + self.width//2 - glyph.width//2,
            )
        # a Font may also have to ensure line_height remains unchanged
        return glyph

    @scriptable
    def stretch(self, factor_x:int=1, factor_y:int=1, *, adjust_metrics:bool=True):
        """
        Stretch glyph by repeating rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        adjust_metrics: also stretch metrics (default: True)
        """
        glyph = super().stretch(factor_x, factor_y)
        if adjust_metrics:
            return glyph.modify(
                left_bearing=factor_x*self.left_bearing,
                right_bearing=factor_x*self.right_bearing,
                top_bearing=factor_y*self.top_bearing,
                bottom_bearing=factor_y*self.bottom_bearing,
                shift_up=factor_y*self.shift_up,
                shift_left=factor_x*self.shift_left,
            )
        return glyph

    @scriptable
    def shrink(
            self, factor_x:int=1, factor_y:int=1,
            *, adjust_metrics:bool=True
        ):
        """
        Remove rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        adjust_metrics: also stretch metrics (default: True)
        """
        glyph = super().shrink(factor_x, factor_y)
        if adjust_metrics:
            return glyph.modify(
                left_bearing=self.left_bearing // factor_x,
                right_bearing=self.right_bearing // factor_x,
                top_bearing=self.top_bearing // factor_y,
                bottom_bearing=self.bottom_bearing // factor_y,
                shift_up=self.shift_up // factor_y,
                shift_left=self.shift_left // factor_x,
            )
        return glyph


    @scriptable
    def smear(
            self, *, left:int=0, right:int=0, up:int=0, down:int=0,
            adjust_metrics:bool=True
        ):
        """
        Repeat inked pixels.

        left: number of times to repeat inked pixel leftwards
        right: number of times to repeat inked pixel rightwards
        up: number of times to repeat inked pixel upwards
        down: number of times to repeat inked pixel downwards
        adjust_metrics: ensure advances stay the same (default: True)
        """
        return super().smear(
                left=left, right=right, up=up, down=down,
                adjust_metrics=adjust_metrics
        )
