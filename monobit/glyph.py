"""
monobit.glyph - representation of single glyph

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from functools import cache

from .encoding import is_graphical, is_blank
from .labels import Codepoint, Char, Tag, to_label
from .raster import Raster, NOT_SET, turn_method
from .properties import Props, extend_string
from .cachedprops import HasProps, checked_property, writable_property
from .basetypes import Coord, Bounds, to_number
from .scripting import scriptable
from .vector import StrokePath


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
            to_label(_k): to_number(_v)
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
        for label in second.get_labels():
            try:
                return self[label]
            except KeyError:
                pass
        # no kerning is zero kerning
        return 0


##############################################################################
# glyph properties

class GlyphProperties:
    """Default, calculated and settable properties for glyph."""

    # horizontal offset from leftward origin to matrix left edge
    left_bearing: int = 0
    # horizontal offset from matrix right edge to rightward origin
    right_bearing: int = 0
    # upward offset from origin to matrix bottom
    shift_up: int = 0
    # kerning - pairwaise additional right-bearing
    right_kerning: KernTable = KernTable()
    # kerning - pairwaise additional left-bearing
    left_kerning: KernTable = KernTable()

    # vertical metrics
    # vertical offset from upward origin to matrix top edge
    top_bearing: int = 0
    # vertical offset from matrix bottom edge to downward origin
    bottom_bearing: int = 0
    # leftward offset from origin to matrix left edge
    shift_left: int = 0

    # path segments for stroke fonts
    path: StrokePath = StrokePath()

    # overridable
    scalable_width: float
    scalable_height: float

    # non overridable known properties
    advance_width: int
    advance_height: int
    width: int
    height: int
    ink_bounds: Bounds
    bounding_box: Coord
    padding: Bounds
    raster: Bounds
    raster_size: Coord


class Glyph(HasProps):
    """Single glyph including raster and properties."""

    _defaults = vars(GlyphProperties)
    _converters = HasProps.get_converters(GlyphProperties)


    @checked_property
    def advance_width(self):
        """Internal advance width of glyph, including internal bearings."""
        return self.left_bearing + self.width + self.right_bearing

    @checked_property
    def advance_height(self):
        """Internal advance width of glyph, including internal bearings."""
        return self.top_bearing + self.height + self.bottom_bearing

    @writable_property
    def scalable_width(self):
        """Overridable, fractional advance width."""
        return self.advance_width

    @writable_property
    def scalable_height(self):
        """Overridable, fractional advance height."""
        return self.advance_height

    @checked_property
    def width(self):
        """Raster width of glyph."""
        return self._pixels.width

    @checked_property
    def height(self):
        """Raster height of glyph."""
        return self._pixels.height

    @checked_property
    def ink_bounds(self):
        """Minimum box encompassing all ink, relative to bottom left."""
        # pylint: disable=no-member
        bounds = Bounds(
            self.raster.left + self.padding.left,
            self.raster.bottom + self.padding.bottom,
            self.raster.right - self.padding.right,
            self.raster.top - self.padding.top,
        )
        # more intuitive result for blank glyphs
        if bounds.left == bounds.right or bounds.top == bounds.bottom:
            return Bounds(0, 0, 0, 0)
        return bounds

    @checked_property
    def bounding_box(self):
        """Dimensions of minimum bounding box encompassing all ink."""
        # pylint: disable=no-member
        return Coord(
            self.ink_bounds.right - self.ink_bounds.left,
            self.ink_bounds.top - self.ink_bounds.bottom
        )

    @checked_property
    def padding(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        return self._pixels.padding

    @checked_property
    def raster(self):
        """Raster bounds, from bottom left."""
        return Bounds(
            left=self.left_bearing,
            bottom=self.shift_up,
            right=self.left_bearing + self.width,
            top=self.shift_up + self.height
        )

    @checked_property
    def raster_size(self):
        """Raster dimensions."""
        return Coord(self.width, self.height)




    ##########################################################################
    # dunder methods

    def __init__(
            self, pixels=(), *,
            labels=(), codepoint=b'', char='', tag='', comment='',
            _0=NOT_SET, _1=NOT_SET, _trustme=False,
            **properties
        ):
        """Create glyph from tuple of tuples."""
        super().__init__()
        if _trustme:
            self._pixels = Raster(pixels, _0=_0, _1=_1)
            self._labels = labels
            self._comment = comment
            self._set_properties(properties)
            return
        # raster data
        self._pixels = Raster(pixels, _0=_0, _1=_1)
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
        self._set_properties(properties)

    def __eq__(self, other):
        """Equality."""
        if not isinstance(other, type(self)):
            return False
        if (self.width, self.height) != (other.width, other.height):
            return False
        for p in (*self._props.keys(), *other._props.keys()):
            if not getattr(self, p) == getattr(other, p):
                return False
        return self.as_matrix() == other.as_matrix()

    def __hash__(self):
        """Needs to exist if __eq__ defined."""
        return super().__hash__()

    def __repr__(self):
        """Text representation."""
        elements = (
            f"labels={repr(self._labels)}" if self._labels else '',
            "comment=({})".format(
                "\n  '" + "\n',\n  '".join(self.comment.splitlines()) + "'"
            ) if self._comment else '',
            ', '.join(f'{_k}={_v}' for _k, _v in self.get_properties().items()),
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
        if labels is NOT_SET:
            labels = self._labels
        else:
            labels = tuple(to_label(_l) for _l in labels)
        if tag is not NOT_SET:
            labels = [_l for _l in labels if not isinstance(_l, Tag)]
            if tag:
                labels.append(Tag(tag))
        if codepoint is not NOT_SET:
            labels = [_l for _l in labels if not isinstance(_l, Codepoint)]
            if codepoint or codepoint == 0:
                labels.append(Codepoint(codepoint))
        if char is not NOT_SET:
            labels = [_l for _l in labels if not isinstance(_l, Char)]
            if char:
                labels.append(Char(char))
        if comment is NOT_SET:
            comment = self._comment
        properties = {**self._props}
        properties.update(kwargs)
        return type(self)(
            pixels,
            labels=labels,
            comment=comment or '',
            **properties,
            _trustme=True,
        )

    def label(
            self, codepoint_from=NOT_SET, char_from=NOT_SET,
            tag_from=NOT_SET, comment_from=NOT_SET,
            overwrite=False, match_whitespace=True, match_graphical=True,
        ):
        """
           Set labels or comment using provided encoder or tagger object.

           char_from: Encoder object used to set char labels
           codepoint_from: Encoder object used to set codepoint labels
           tag_from: Tagger object used to set tag labels
           comment_from: Tagger object used to set comment
           overwrite: overwrite codepoint or char if already given
           match_whitespace: do not give blank glyphs a non-whitespace char label (default: True)
           match_graphical: do not give non-blank glyphs a non-graphical label (default: True)
        """
        if sum(
                _arg is not NOT_SET
                for _arg in (codepoint_from, char_from, tag_from, comment_from)
            ) > 1:
            raise ValueError(
                'Can only set one of character, codepoint, tag or comment with one label() call. '
                'Use separate calls to set more.'
           )
        labels = self.get_labels()
        # use codepage to find codepoint if not set
        if codepoint_from is not NOT_SET:
            if not codepoint_from:
                if overwrite:
                    return self.modify(codepoint=None)
            elif overwrite or not self.codepoint:
                return self.modify(codepoint=codepoint_from.codepoint(*labels))
        # use codepage to find char if not set
        if char_from is not NOT_SET:
            if not char_from:
                if overwrite:
                    return self.modify(char=None)
            elif overwrite or not self.char:
                char = char_from.char(*labels)
                if match_whitespace and self.is_blank() and char and not is_blank(char):
                    return self
                if match_graphical and not self.is_blank() and char and not is_graphical(char):
                    return self
                return self.modify(char=char)
        if tag_from is not NOT_SET:
            if not tag_from:
                if overwrite:
                    return self.modify(tag=None)
            elif overwrite or not self.tag:
                return self.modify(tag=tag_from.tag(*labels))
        if comment_from is not NOT_SET:
            if not comment_from:
                return self.modify(comment=None)
            return self.modify(comment=comment_from.comment(*labels))
        return self

    def append(
            self, *,
            comment=None, **properties
        ):
        """Return a copy of the glyph with changes."""
        if not comment:
            comment = ''
        comment = extend_string(self._comment, comment)
        for key, value in properties.items():
            if self.get_defined(key):
                properties[key] = extend_string(self._props[key], value)
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
            pixels = NOT_SET
        try:
            args.remove('labels')
            labels = ()
        except ValueError:
            labels = NOT_SET
        try:
            args.remove('comment')
            comment = ''
        except ValueError:
            comment = NOT_SET
        none_args = {_k: None for _k in args}
        return self.modify(
            pixels,
            labels=labels,
            comment=comment,
            **none_args
        )


    ##########################################################################
    # property access

    # __getattr__ = HasProps._getattr

    @property
    def comment(self):
        return self._comment

    @cache
    def has_vertical_metrics(self):
        """Check if this glyph has vertical metrics."""
        return any(
            self.get_defined(_p)
            for _p in ('top_bearing', 'bottom_bearing', 'shift_left')
        )

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
    # creation

    @classmethod
    def blank(cls, width=0, height=0, **kwargs):
        """Create whitespace glyph."""
        return cls(((0,) * width,) * height, **kwargs)

    @classmethod
    def from_vector(
            cls, bitseq, *, stride, width=NOT_SET, align='left',
            _0=NOT_SET, _1=NOT_SET, **kwargs
        ):
        """Create glyph from flat immutable sequence representing bits."""
        pixels = Raster.from_vector(
            bitseq, stride=stride, width=width, align=align, _0=_0, _1=_1
        )
        return cls(pixels, **kwargs)

    @classmethod
    def from_bytes(
            cls, byteseq, width, height=NOT_SET,
            *, align='left', order='row-major', stride=NOT_SET,
            byte_swap=0, bit_order='big',
            **kwargs
        ):
        """Create glyph from bytes/bytearray/int sequence."""
        pixels = Raster.from_bytes(
            byteseq, width, height,
            align=align, stride=stride, order=order,
            byte_swap=byte_swap, bit_order=bit_order,
        )
        return cls(pixels, **kwargs)

    @classmethod
    def from_hex(cls, hexstr, width, height=NOT_SET, *, align='left', **kwargs):
        """Create glyph from hex string."""
        pixels = Raster.from_hex(hexstr, width, height, align=align)
        return cls(pixels, **kwargs)

    @classmethod
    def from_path(cls, path, *, advance_width=None, **kwargs):
        """Draw the StrokePath and create a Glyph."""
        strokepath = StrokePath(path)
        raster = Raster(strokepath.draw())
        if advance_width is None:
            advance_width = strokepath.bounds.right
        return cls(
            raster, path=strokepath,
            right_bearing=advance_width-strokepath.bounds.right,
            left_bearing=strokepath.bounds.left,
            shift_up=strokepath.bounds.bottom,
            **kwargs
        )

    ##########################################################################
    # conversion

    @property
    def pixels(self):
        return self._pixels

    def is_blank(self):
        """Glyph has no ink."""
        return self._pixels.is_blank()

    def as_matrix(self, *, ink=1, paper=0):
        """Return matrix of user-specified foreground and background objects."""
        return self._pixels.as_matrix(ink=ink, paper=paper)

    def as_text(self, *, ink='@', paper='.', start='', end='\n'):
        """Convert glyph to text."""
        return self._pixels.as_text(ink=ink, paper=paper, start=start, end=end)

    def as_blocks(self, resolution=(2, 2)):
        """Convert glyph to a string of quadrant block characters."""
        return self._pixels.as_blocks(resolution)

    def as_vector(self, ink=1, paper=0):
        """Return flat tuple of user-specified foreground and background objects."""
        return self._pixels.as_vector(ink=ink, paper=paper)

    def as_bits(self, ink=1, paper=0):
        """Return flat bits as bytes string."""
        return self._pixels.as_bits(ink=ink, paper=paper)

    def as_byterows(self, *, align='left'):
        """Convert glyph to rows of bytes."""
        return self._pixels.as_byterows(align=align)

    def as_bytes(
            self, *, align='left', stride=NOT_SET, byte_swap=0,
            bit_order='big',
        ):
        """
        Convert raster to flat bytes.

        stride: number of pixels per row (default: what's needed for alignment)
        align: 'left' or 'right' for byte-alignment; 'bit' for bit-alignment
        byte_swap: swap byte order in units of n bytes, 0 (default) for no swap
        bit_order: per-byte bit endianness; 'little' for lsb left, 'big' (default) for msb left
        """
        return self._pixels.as_bytes(
            align=align, stride=stride, byte_swap=byte_swap, bit_order=bit_order,
        )

    def as_hex(self, *, align='left'):
        """Convert glyph to hex string."""
        return self._pixels.as_hex(align=align)


    ##########################################################################
    # glyph transformations

    # orthogonal transformations

    @scriptable
    def mirror(
            self, *,
            adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Reverse pixels horizontally.

        adjust_metrics: also reverse metrics (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        pixels = self._pixels.mirror()
        new_metrics = {}
        if adjust_metrics:
            new_metrics |= dict(
                left_bearing=self.right_bearing,
                right_bearing=self.left_bearing,
            )
            if create_vertical_metrics or self.has_vertical_metrics():
                new_metrics |= dict(
                    shift_left=-self.shift_left
                    #shift_left around central axis, so should differ at most 1 pixel
                )
        return self.modify(pixels, **new_metrics)

    @scriptable
    def flip(
            self, *,
            adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Reverse pixels vertically.

        adjust_metrics: also reverse metrics (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        pixels = self._pixels.flip()
        new_metrics = {}
        if adjust_metrics:
            # pylint: disable=invalid-unary-operand-type
            new_metrics |= dict(
                # flip about baseline
                shift_up=-self.height - self.shift_up
            )
            if create_vertical_metrics or self.has_vertical_metrics():
                new_metrics |= dict(
                    top_bearing=self.bottom_bearing,
                    bottom_bearing=self.top_bearing,
                )
        # Font should adjust ascent <-> descent and global bearings
        return self.modify(pixels, **new_metrics)

    @scriptable
    def transpose(self, *, adjust_metrics:bool=True):
        """
        Transpose glyph.

        adjust_metrics: also transpose metrics (default: True)
        """
        pixels = self._pixels.transpose()
        if adjust_metrics:
            return self.modify(
                pixels,
                top_bearing=self.left_bearing,
                left_bearing=self.top_bearing,
                right_bearing=self.bottom_bearing,
                bottom_bearing=self.right_bearing,
                shift_left=self.shift_up+self.height//2,
                shift_up=self.shift_left-self.width//2
            )
        return self.modify(pixels)


    turn = scriptable(turn_method)

    # raster resizing

    @scriptable
    def crop(
            self, left:int=0, bottom:int=0, right:int=0, top:int=0,
            *, adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Crop the raster.

        left: number of columns to remove from left
        bottom: number of rows to remove from bottom
        right: number of columns to remove from right
        top: number of rows to remove from top
        adjust_metrics: make the operation render-invariant (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        if not any((left, bottom, right, top)):
            return self
        # reduce raster
        pixels = self._pixels.crop(left, bottom, right, top)
        new_metrics = {}
        if adjust_metrics:
            # horizontal metrics
            new_metrics |= dict(
                left_bearing=self.left_bearing + left,
                right_bearing=self.right_bearing + right,
                shift_up=self.shift_up + bottom,
            )
            # vertical metrics
            if create_vertical_metrics or self.has_vertical_metrics():
                # shift-left adjustment rounds differently for odd-width than even width
                sign = 1 if (self.width%2) else -1
                new_metrics |= dict(
                    top_bearing=self.top_bearing + top,
                    bottom_bearing=self.bottom_bearing + bottom,
                    shift_left=self.shift_left + sign*((sign*(right-left))//2),
                )
        return self.modify(pixels, **new_metrics)

    @scriptable
    def expand(
            self, left:int=0, bottom:int=0, right:int=0, top:int=0,
            *, adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Add blank space to raster.

        left: number of columns to add on left
        bottom: number of rows to add on bottom
        right: number of columns to add on right
        top: number of rows to add on top
        adjust_metrics: make the operation render-invariant (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        if not any((left, bottom, right, top)):
            return self
        # reduce raster
        pixels = self._pixels.expand(left, bottom, right, top)
        new_metrics = {}
        if adjust_metrics:
            # horizontal metrics
            new_metrics |= dict(
                left_bearing=self.left_bearing - left,
                right_bearing=self.right_bearing - right,
                shift_up=self.shift_up - bottom,
            )
            # vertical metrics
            if create_vertical_metrics or self.has_vertical_metrics():
                # shift-left adjustment rounds differently for odd-width than even width
                sign = 1 if (self.width%2) else -1
                new_metrics |= dict(
                    top_bearing=self.top_bearing - top,
                    bottom_bearing=self.bottom_bearing - bottom,
                    # for shift-left, expand left is like crop right, and v.v.
                    shift_left=self.shift_left + sign*((sign*(left-right))//2),
                )
        return self.modify(pixels, **new_metrics)

    @scriptable
    def reduce(
            self, *,
            adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Return a glyph reduced to the bounding box.

        adjust_metrics: make the operation render-invariant (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        # pylint: disable=not-an-iterable
        return self.crop(
            *self.padding, adjust_metrics=adjust_metrics,
            create_vertical_metrics=create_vertical_metrics,
        )


    # scaling

    @scriptable
    def stretch(
            self, factor_x:int=1, factor_y:int=1,
            *, adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Stretch glyph by repeating rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        adjust_metrics: also stretch metrics (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        if factor_x == factor_y == 1:
            return self
        pixels = self._pixels.stretch(factor_x, factor_y)
        new_metrics = {}
        if adjust_metrics:
            new_metrics |= dict(
                left_bearing=factor_x*self.left_bearing,
                right_bearing=factor_x*self.right_bearing,
                shift_up=factor_y*self.shift_up,
            )
            if create_vertical_metrics or self.has_vertical_metrics():
                new_metrics |= dict(
                    top_bearing=factor_y*self.top_bearing,
                    bottom_bearing=factor_y*self.bottom_bearing,
                    shift_left=factor_x*self.shift_left,
                )
        return self.modify(pixels, **new_metrics)

    @scriptable
    def shrink(
            self, factor_x:int=1, factor_y:int=1,
            *, adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Shrink by removing rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        adjust_metrics: also stretch metrics (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        if factor_x == factor_y == 1:
            return self
        pixels = self._pixels.shrink(factor_x, factor_y)
        new_metrics = {}
        if adjust_metrics:
            new_metrics |= dict(
                left_bearing=self.left_bearing // factor_x,
                right_bearing=self.right_bearing // factor_x,
                shift_up=self.shift_up // factor_y,
            )
            if create_vertical_metrics or self.has_vertical_metrics():
                new_metrics |= dict(
                    top_bearing=self.top_bearing // factor_y,
                    bottom_bearing=self.bottom_bearing // factor_y,
                    shift_left=self.shift_left // factor_x,
                )
        return self.modify(pixels, **new_metrics)

    # shear

    @scriptable
    def shear(
            self, *, direction:str='right', pitch:Coord=(1, 1),
            create_vertical_metrics:bool=False,
        ):
        """
        Create a slant by dislocating diagonally, keeping
        the horizontal baseline fixed.

        direction: direction to move the top of the glyph (default: 'right').
        pitch: angle of the slant, given as (x, y) coordinate (default: 1,1).
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        if not self.height:
            return self
        pitch_x, pitch_y = pitch
        direction = direction[0].lower()
        extra_width = (self.height-1) * pitch_x // pitch_y
        # adjustment to start diagonal at baseline
        modulo = pitch_y - (-self.shift_up*pitch_x) % pitch_y
        # adjust for shift at baseline height, to keep it fixed
        pre = (-self.shift_up * pitch_x + modulo) // pitch_y - (modulo==pitch_y)
        if direction == 'r':
            new_metrics = dict(
                left_bearing=self.left_bearing-pre,
                right_bearing=self.right_bearing+pre,
            )
            if create_vertical_metrics or self.has_vertical_metrics():
                new_metrics |= dict(
                    shift_left=self.shift_left+pre,
                )
            work = self.modify(**new_metrics)
            work = work.expand(right=extra_width)
        elif direction == 'l':
            new_metrics = dict(
                left_bearing=self.left_bearing+pre,
                right_bearing=self.right_bearing-pre,
            )
            if create_vertical_metrics or self.has_vertical_metrics():
                new_metrics |= dict(
                    shift_left=self.shift_left-pre,
                )
            work = self.modify(**new_metrics)
            work = work.expand(left=extra_width)
        else:
            raise ValueError(
                f'Shear direction must be `left` or `right`, not `{direction}`'
            )
        pixels = work._pixels.shear(
            direction=direction, pitch=pitch, modulo=modulo,
        )
        return work.modify(pixels)

    # ink effects

    @scriptable
    def smear(
            self, *, left:int=0, down:int=0, right:int=1, up:int=0,
            adjust_metrics:bool=True, create_vertical_metrics:bool=False,
        ):
        """
        Repeat inked pixels.

        left: number of times to repeat inked pixel leftwards
        right: number of times to repeat inked pixel rightwards
        up: number of times to repeat inked pixel upwards
        down: number of times to repeat inked pixel downwards
        adjust_metrics: ensure advances stay the same (default: True)
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        # pylint: disable=unpacking-non-sequence
        pleft, pdown, pright, pup = self.padding
        work = self.expand(
            max(0, left-pleft), max(0, down-pdown),
            max(0, right-pright), max(0, up-pup),
            adjust_metrics=adjust_metrics,
            create_vertical_metrics=create_vertical_metrics,
        )
        return work.modify(work._pixels.smear(
            left=left, right=right, up=up, down=down,
        ))

    @scriptable
    def outline(self, *, thickness:int=1, create_vertical_metrics:bool=False):
        """
        Outline glyph.

        thickness: number of pixels in outline in each direction
        create_vertical_metrics: create vertical metrics if they don't exist (default: False)
        """
        thicker = self.smear(
            left=thickness, down=thickness, right=thickness, up=thickness,
            create_vertical_metrics=create_vertical_metrics,
        )
        return thicker.overlay(self, operator=lambda x: bool(sum(x) % 2))

    @scriptable
    def underline(self, descent:int=1, thickness:int=1):
        """
        Add a line.

        descent: number of pixels the underline is below the baseline (default: 1)
        thickness: number of pixels the underline extends downward (default: 1)
        """
        height = -self.shift_up - descent
        # extend down if we get to negative rows
        down = max(0, -height+thickness-1)
        # extend up if we get above the ratser height
        up = max(0, height-self.height+1)
        work = self.expand(bottom=down, top=up)
        top_height = height+down
        bottom_height = top_height-thickness+1
        return work.modify(work._pixels.underline(top_height, bottom_height))

    @scriptable
    def invert(self):
        """Reverse video."""
        return self.modify(self._pixels.invert())

    @scriptable
    def roll(self, down:int=0, right:int=0):
        """
        Cycle rows and/or columns in raster.

        down: number of rows to roll (down if positive, up if negative)
        right: number of columns to roll (to right if positive, to left if negative)
        """
        return self.modify(self._pixels.roll(down, right))


    ##########################################################################
    # operations on multiple glyphs

    # pylint: disable=no-method-argument
    def _get_common_raster(*glyphs):
        """
        Minimum box encompassing all glyph matrices overlaid at fixed origin.
        """
        #self = glyphs[0]
        # raster edges
        rasters = tuple(_g.raster for _g in glyphs)
        return Bounds(
            left=min(_r.left for _r in rasters),
            bottom=min(_r.bottom for _r in rasters),
            right=max(_r.right for _r in rasters),
            top=max(_r.top for _r in rasters)
        )

    # pylint: disable=no-method-argument
    def overlay(*glyphs, operator=any):
        """
        Superimpose glyphs, taking into account metrics.

        operator: aggregation function, callable on iterable on bool/int.
                  Use any for additive, all for masking.
        """
        #self = glyphs[0]
        # bring on common raster
        common = Glyph._get_common_raster(*glyphs)
        glyphs = tuple(
            _g.expand(
                left=_g.raster.left-common.left,
                bottom=_g.raster.bottom-common.bottom,
                right=common.right-_g.raster.right,
                top=common.top-_g.raster.top
            )
            for _g in glyphs
        )
        pixels = Raster.overlay(
            *(_g._pixels for _g in glyphs), operator=operator
        )
        return glyphs[0].modify(pixels)
