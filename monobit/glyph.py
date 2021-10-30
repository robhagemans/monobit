"""
monobit.glyph - representation of single glyph

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import binascii
import logging
from typing import NamedTuple
import numbers

try:
    # python 3.9
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache()

from .scripting import scriptable
from .binary import ceildiv, bytes_to_bits
from .matrix import to_text
from .encoding import is_graphical
from .label import Char, Codepoint, Tag, label


NOT_SET = object()


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
        super().__init__({
            label(_k): int(_v)
            for _k, _v in table.items()
        })

    def __str__(self):
        """Convert kerning table to multiline string."""
        return '\n'.join(
            f'{_k} {_v}'
            for _k, _v in self.items()
        )

    def get_for_glyph(self, second):
        """Get kerning amount for given second glyph."""
        try:
            return self[Char(second.char)]
        except KeyError:
            pass
        try:
            return self[Codepoint(second.codepoint)]
        except KeyError:
            pass
        for tag in second.tags:
            try:
                return self[Tag(tag)]
            except KeyError:
                pass
        # no kerning is zero kerning
        return 0



class Glyph:
    """Single glyph."""

    def __init__(
            self, pixels=(), *,
            codepoint=(), char='', tags=(), comments=(),
            offset=None, tracking=0, kern_to=(),
            **kwargs
        ):
        """Create glyph from tuple of tuples."""
        # glyph data
        self._rows = tuple(tuple(bool(_bit) for _bit in _row) for _row in pixels)
        # annotations
        self._comments = tuple(comments)
        self._codepoint = Codepoint(codepoint).value
        self._char = char
        self._tags = tuple(tags)
        self._offset = Coord.create(offset)
        self._tracking = int(tracking)
        self._kern_to = KernTable(kern_to)
        # custom properties - not used but kept
        self._props = {_k.replace('_', '-'): _v for _k, _v in kwargs.items() if _v is not None}
        if len(set(len(_r) for _r in self._rows)) > 1:
            raise ValueError(
                f'All rows in a glyph must be of the same width: {repr(self)}'
            )

    def __getattr__(self, attr):
        """Take property from property table."""
        dict_attr = attr.replace('_', '-')
        if '_props' in vars(self):
            try:
                return self._props[dict_attr]
            except KeyError as e:
                pass
        raise AttributeError(attr)

    def drop_properties(self, *args):
        """Remove custom properties."""
        args = [_arg.replace('_', '-') for _arg in args]
        return self.modify(**{_k: None for _k in args})

    @property
    def tags(self):
        return self._tags

    @property
    def char(self):
        return self._char

    @property
    def codepoint(self):
        return self._codepoint

    @property
    def comments(self):
        return self._comments

    @property
    def offset(self):
        """Internal ffset vector for this glyph, adds to font offsett."""
        return self._offset

    @property
    def tracking(self):
        """Internal tracking for this glyph, adds to font tracking."""
        return self._tracking

    @property
    def kern_to(self):
        return self._kern_to

    @property
    def properties(self):
        return self._props

    def __repr__(self):
        """Text representation."""
        return (
            f"Glyph(char={repr(self._char)}, "
            f"codepoint={repr(self._codepoint)}, "
            f"tags={repr(self._tags)}, "
            + "comments=({}), ".format(
                '' if not self._comments else
                "\n  '" + "',\n  '".join(self.comments) + "'"
            )
            + ', '.join(f'{_k}={_v}' for _k, _v in self._props.items())
            + (', ' if self._props else '')
            + ('' if not self._offset else f"offset={repr(self._offset)}, ")
            + ('' if not self._tracking else f"tracking={repr(self._tracking)}, ")
            + "pixels=({})".format(
                '' if not self._rows else
                "\n  '{}'\n".format(
                    to_text(self.as_matrix(), ink='@', paper='.', line_break="',\n  '")
                )
            )
            + ")"
        )

    def add_annotations(self, *, tags=(), comments=()):
        """Return a copy of the glyph with added tags or comments."""
        return self.modify(
            tags=self._tags + tuple(tags),
            comments=self._comments + tuple(comments)
        )

    # TODO remove this
    def set_annotations(self, *, tags=NOT_SET, char=NOT_SET, codepoint=NOT_SET, comments=NOT_SET):
        """Return a copy of the glyph with different annotations."""
        return self.modify(tags=tags, char=char, codepoint=codepoint, comments=comments)

    def set_encoding_annotations(self, encoder):
        """Set annotations using provided encoder object."""
        # use codepage to find char if not set
        if not self.char:
            return self.set_annotations(char=encoder.char(self.codepoint))
        # use codepage to find codepoint if not set
        if not self.codepoint:
            return self.set_annotations(codepoint=encoder.codepoint(self.char))
        # both are set, check if consistent with codepage
        enc_char = encoder.char(self.codepoint)
        if (self.char != enc_char) and is_graphical(self.char) and is_graphical(enc_char):
            logging.info(
                f'Inconsistent encoding at {Codepoint(self.codepoint)}: '
                f'mapped to {Char(self.char)} '
                f'instead of {Char(enc_char)} per stated encoding.'
            )
        return self

    def add_history(self, history):
        """No-op - not recording glyph history."""
        return self

    @scriptable
    def drop_comments(self):
        """Return a copy of the glyph without comments."""
        return self.modify(comments=())

    def modify(
            self, pixels=NOT_SET, *,
            tags=NOT_SET, char=NOT_SET, codepoint=NOT_SET, comments=NOT_SET,
            offset=NOT_SET, tracking=NOT_SET, kern_to=NOT_SET,
            **kwargs
        ):
        """Return a copy of the glyph with changes."""
        if pixels is NOT_SET:
            pixels = self._rows
        if tags is NOT_SET:
            tags = self._tags
        if codepoint is NOT_SET:
            codepoint = self._codepoint
        if char is NOT_SET:
            char = self._char
        if comments is NOT_SET:
            comments = self._comments
        if offset is NOT_SET:
            offset = self._offset
        if tracking is NOT_SET:
            tracking = self._tracking
        if kern_to is NOT_SET:
            kern_to = self._kern_to
        return Glyph(
            tuple(pixels),
            codepoint=codepoint,
            char=char,
            tags=tuple(tags),
            comments=tuple(comments),
            offset=offset,
            tracking=tracking,
            kern_to=kern_to,
            **{**self._props, **kwargs}
        )

    @classmethod
    def blank(cls, width=0, height=0):
        """Create whitespace glyph."""
        return cls(((0,) * width,) * height)

    @classmethod
    def from_matrix(cls, rows, paper):
        """Create glyph from sequence of sequence of objects."""
        return cls(tuple(
            tuple(_char not in paper for _char in _row)
            for _row in rows
        ))

    def as_matrix(self, ink=1, paper=0):
        """Return matrix of user-specified foreground and background objects."""
        return tuple(
            tuple(ink if _c else paper for _c in _row)
            for _row in self._rows
        )

    def as_tuple(self, ink=1, paper=0):
        """Return flat tuple of user-specified foreground and background objects."""
        return tuple(
            ink if _c else paper
            for _row in self._rows
            for _c in _row
        )

    @classmethod
    def from_bytes(cls, byteseq, width, height=NOT_SET):
        """Create glyph from bytes/bytearray/int sequence."""
        if not width or height == 0:
            return cls()
        if height is not NOT_SET:
            bytewidth = len(byteseq) // height
        else:
            bytewidth = ceildiv(width, 8)
        byteseq = list(byteseq)
        rows = [byteseq[_offs:_offs+bytewidth] for _offs in range(0, len(byteseq), bytewidth)]
        return cls(tuple(bytes_to_bits(_row, width) for _row in rows))

    def as_bytes(self):
        """Convert glyph to flat bytes."""
        if not self._rows:
            return b''
        width = len(self._rows[0])
        bytewidth = ceildiv(width, 8)
        # byte-align rows
        rows = [
            _row + (False,) * (bytewidth*8 - width)
            for _row in self._rows
        ]
        # chunk by byte and flatten
        glyph_bytes = [
            _row[_offs:_offs+8]
            for _row in rows
            for _offs in range(0, len(_row), 8)
        ]
        # convert to binary strings
        glyph_bytes = [
            ''.join(str(int(_bit)) for _bit in _byte)
            for _byte in glyph_bytes
        ]
        return bytes(int(_bitstr, 2) for _bitstr in glyph_bytes)

    @classmethod
    def from_hex(cls, hexstr, width, height):
        """Create glyph from hex string."""
        if not width or not height:
            if hexstr:
                raise ValueError('Hex string must be empty for zero-sized glyph')
            return cls.blank(width, height)
        return cls.from_bytes(binascii.unhexlify(hexstr.encode('ascii')), width, height)

    def as_hex(self):
        """Convert glyph to hex string."""
        return binascii.hexlify(self.as_bytes()).decode('ascii')

    ###############################################################################################
    # properties

    @property
    def width(self):
        """Raster width of glyph."""
        if not self._rows:
            return 0
        return len(self._rows[0])

    @property
    def height(self):
        """Raster height of glyph."""
        return len(self._rows)

    @property
    def advance(self):
        """Internal advance width of glyph, including internal bearings."""
        return self._offset.x + self.width + self._tracking

    @property
    @cache
    # rename to margins ?
    def ink_offsets(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        if not self._rows:
            return Bounds(0, 0, 0, 0)
        row_inked = [True in _row for _row in self._rows]
        if True not in row_inked:
            return Bounds(self.width, self.height, 0, 0)
        bottom = list(reversed(row_inked)).index(True)
        top = row_inked.index(True)
        col_inked = [bool(sum(_row[_i] for _row in self._rows)) for _i in range(self.width)]
        left = col_inked.index(True)
        right = list(reversed(col_inked)).index(True)
        return Bounds(left, bottom, right, top)

    @property
    @cache
    def ink_bounds(self):
        """Minimum box encompassing all ink, in glyph origin coordinates."""
        row_inked = [True in _row for _row in self._rows]
        return Bounds(
            left=self._offset.x + self.ink_offsets.left,
            bottom=self.offset.y + self.ink_offsets.bottom,
            right=self.offset.x + self.width - self.ink_offsets.right,
            top=self.offset.y + self.height - self.ink_offsets.top,
        )

    @property
    @cache
    def bounding_box(self):
        """Dimensions of minimum bounding box encompassing all ink."""
        return Coord(
            self.ink_bounds.right - self.ink_bounds.left,
            self.ink_bounds.top - self.ink_bounds.bottom
        )

    ###############################################################################################
    # operations

    def reduce(self):
        """Return a glyph reduced to the bounding box."""
        return self.crop(*self.ink_offsets)

    def superimposed(self, other):
        """Superimpose another glyph of the same size."""
        return self.modify(
            tuple(
                _pix or _pix1
                for _pix, _pix1 in zip(_row, _row1)
            )
            for _row, _row1 in zip(self._rows, other._rows)
        )

    @classmethod
    def superimpose(cls, glyphs):
        glyph_iter = iter(glyphs)
        try:
            combined = next(glyph_iter)
        except StopIteration:
            return cls()
        for glyph in glyph_iter:
            combined = combined.superimposed(glyph)
        return combined


    ###############################################################################################

    @scriptable
    def mirror(self):
        """Reverse pixels horizontally."""
        return self.modify(tuple(_row[::-1] for _row in self._rows))

    @scriptable
    def flip(self):
        """Reverse pixels vertically."""
        return self.modify(self._rows[::-1])

    @scriptable
    def roll(self, rows:int=0, columns:int=0):
        """
        Cycle rows and/or columns in glyph.

        rows: number of rows to roll (down if positive)
        columns: number of columns to roll (to right if positive)
        """
        rolled = self
        if self.height > 1 and rows:
            rolled = rolled.modify(rolled._rows[-rows:] + rolled._rows[:-rows])
        if self.width > 1 and columns:
            rolled = rolled.modify(tuple(_row[-columns:] + _row[:-columns] for _row in rolled._rows))
        return rolled

    @scriptable
    def transpose(self):
        """Transpose glyph."""
        return self.modify(tuple(tuple(_x) for _x in zip(*self._rows)))

    @scriptable
    def rotate(self, turns:int=1):
        """
        Rotate by 90-degree turns.

        turns: number of turns to rotate (clockwise if positive)
        """
        turns %= 4
        if turns == 3:
            return self.transpose().flip()
        elif turns == 2:
            return self.mirror().flip()
        elif turns == 1:
            return self.transpose().mirror()
        return self

    @scriptable
    def invert(self):
        """Reverse video."""
        return self.modify(tuple(tuple((not _col) for _col in _row) for _row in self._rows))

    @scriptable
    def crop(self, left:int=0, bottom:int=0, right:int=0, top:int=0):
        """
        Crop glyph.

        left: number of columns to remove from left
        bottom: number of rows to remove from bottom
        right: number of columns to remove from right
        top: number of rows to remove from top
        """
        return self.modify(tuple(
            _row[left : (-right if right else None)]
            for _row in self._rows[top : (-bottom if bottom else None)]
        ))

    @scriptable
    def expand(self, left:int=0, bottom:int=0, right:int=0, top:int=0):
        """
        Add blank space.

        left: number of columns to add on left
        bottom: number of rows to add on bottom
        right: number of columns to add on right
        top: number of rows to add on top
        """
        if min(left, bottom, right, top) < 0:
            raise ValueError('Can only expand glyph by a positive amount.')
        if right+left and not top+self.height+bottom:
            # expanding empty glyph - make at least one high or it will stay empty
            raise ValueError("Can't expand width of zero-height glyph.")
        new_width = left + self.width + right
        pixels = (
            ((False,) * new_width,) * top
            + tuple((False,)*left + _row + (False,)*right for _row in self._rows)
            + ((False,) * new_width,) * bottom
        )
        return self.modify(pixels)

    @scriptable
    def stretch(self, factor_x:int=1, factor_y:int=1):
        """
        Repeat rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        """
        # vertical stretch
        glyph = tuple(_row for _row in self._rows for _ in range(factor_y))
        # horizontal stretch
        glyph = tuple(
            tuple(_col for _col in _row for _ in range(factor_x))
            for _row in glyph
        )
        return self.modify(glyph)

    @scriptable
    def shrink(self, factor_x:int=1, factor_y:int=1, force:bool=False):
        """
        Remove rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        force: remove rows/columns even if not repeated
        """
        # vertical shrink
        shrunk_glyph = self._rows[::factor_y]
        if not force:
            # check we're not throwing away stuff
            for offs in range(1, factor_y):
                alt = self._rows[offs::factor_y]
                if shrunk_glyph != alt:
                    raise ValueError("can't shrink glyph without loss")
        # horizontal stretch
        glyph = tuple(_row[::factor_x] for _row in self._rows)
        return self.modify(glyph)
