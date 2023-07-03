"""
monobit.raster - bitmap raster

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import zip_longest

from .binary import ceildiv, reverse_by_group, bytes_to_bits
from .basetypes import Bounds, Coord
from .blocks import matrix_to_blocks, blockstr


# sentinel object
NOT_SET = object()


# turn function for Raster, Glyph and Font

def _calc_turns(clockwise, anti):
    if clockwise is NOT_SET:
        if anti is NOT_SET:
            clockwise, anti = 1, 0
        else:
            clockwise = 0
    elif anti is NOT_SET:
        anti = 0
    turns = (clockwise - anti) % 4
    return turns

def turn(self, clockwise:int=NOT_SET, *, anti:int=NOT_SET):
    """
    Rotate by 90-degree turns.

    clockwise: number of turns to rotate clockwise (default: 1)
    anti: number of turns to rotate anti-clockwise
    """
    turns = _calc_turns(clockwise, anti)
    if turns == 3:
        return self.transpose().flip()
    elif turns == 2:
        return self.mirror().flip()
    elif turns == 1:
        return self.transpose().mirror()
    return self

turn_method = turn


# immutable bit matrix

class Raster:
    """Bit matrix."""

    _0 = '0'
    _1 = '1'
    _inner = ''.join
    _outer = tuple
    _itemtype = str

    def __init__(self, pixels=(), *, width=NOT_SET, _0=NOT_SET, _1=NOT_SET):
        """Create glyph from tuple of tuples."""
        if isinstance(pixels, type(self)):
            if _0 is NOT_SET:
                _0 = pixels._0
            if _1 is NOT_SET:
                _1 = pixels._1
            if width is NOT_SET:
                width = pixels.width
            pixels = pixels._pixels
        if (
                _0 is NOT_SET or _1 is NOT_SET
                or not isinstance(_0, self._itemtype)
                or not isinstance(_1, self._itemtype)
            ):
            if _1 is NOT_SET:
                _1 = True
            # glyph data
            self._pixels = self._outer(
                self._inner(self._1 if _bit == _1 else self._0 for _bit in _row)
                for _row in pixels
            )
            # check pixel matrix geometry
            if len(set(len(_r) for _r in self._pixels)) > 1:
                raise ValueError(
                    f"All rows in raster must be of the same width: {repr(self)}"
                )
        else:
            # if _0 and _1 provided, we don't check the pixel matrix
            self._pixels = pixels
            self._0 = _0
            self._1 = _1
        if not self._pixels:
            if width is not NOT_SET:
                self._width = width
            else:
                self._width = 0
        else:
            self._width = len(self._pixels[0])


    def __bool__(self):
        return bool(self.height and self.width)

    # NOTE - these following are shadowed in GlyphProperties

    @property
    def width(self):
        """Raster width of glyph."""
        return self._width

    @property
    def height(self):
        """Raster height of glyph."""
        return len(self._pixels)

    @property
    def padding(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        if not self._pixels:
            return Bounds(0, 0, 0, 0)
        row_inked = tuple(self._1 in _row for _row in self._pixels)
        if not any(row_inked):
            return Bounds(self.width, self.height, 0, 0)
        bottom = row_inked[::-1].index(True)
        top = row_inked.index(True)
        col_inked = tuple(self._1 in _col for _col in zip(*self._pixels))
        left = col_inked.index(True)
        right = col_inked[::-1].index(True)
        return Bounds(left, bottom, right, top)


    ##########################################################################
    # representation

    def __repr__(self):
        """Text representation."""
        if self.height or not self.width:
            return '{}(({}))'.format(
                type(self).__name__,
                self.as_text(start="\n  '", end="',")
            )
        return '{}(width={})'.format(
            type(self).__name__,
            self.width,
        )


    ##########################################################################
    # creation and conversion

    @classmethod
    def blank(cls, width=0, height=0):
        """Create uninked raster."""
        if height == 0:
            return cls(width=width)
        return cls(((0,) * width,) * height)

    def is_blank(self):
        """Glyph has no ink."""
        return not any(self._1 in _row for _row in self._pixels)

    def as_matrix(self, *, ink=1, paper=0):
        """Return matrix of user-specified foreground and background objects."""
        return tuple(
            tuple(ink if _c == self._1 else paper for _c in _row)
            for _row in self._pixels
        )

    def as_text(self, *, ink='@', paper='.', start='', end='\n'):
        """Convert raster to text."""
        def _get_unused(startval):
            charset = (self._0, self._1, start, end, ink, paper)
            for _i in range(startval, startval+len(charset)+1):
                unused = chr(_i)
                if unused not in charset:
                    return unused

        if not self.height:
            return ''
        delim = _get_unused(0)
        contents = delim.join(self._pixels)
        if paper in (self._1, start, end):
            swap = _get_unused(7)
        else:
            swap = paper
        contents = (
            contents.replace(self._0, swap).replace(self._1, ink)
            .replace(swap, paper).replace(delim, end+start)
        )
        return blockstr(''.join((start, contents, end)))

    def as_blocks(self, resolution=(2, 2)):
        """Convert glyph to a string of block characters."""
        if not self.height:
            return ''
        matrix = self.as_matrix()
        return matrix_to_blocks(matrix, *resolution)

    @classmethod
    def from_vector(
            cls, bitseq, *,
            stride, width=NOT_SET, height=NOT_SET, align='left',
            _0=NOT_SET, _1=NOT_SET
        ):
        """Create raster from flat immutable sequence representing bits."""
        if not bitseq or width == 0 or stride == 0:
            return cls()
        if width is NOT_SET:
            width = stride
        if align.startswith('r'):
            offset = stride - width
        else:
            offset = 0
        excess = len(bitseq) % stride
        rows = tuple(
            bitseq[_offs:_offs+width]
            for _offs in range(offset, len(bitseq) - excess, stride)
        )
        if height is not NOT_SET:
            if len(rows) < height:
                raise ValueError('Bit string too short')
            rows = rows[:height]
        return cls(rows, _0=_0, _1=_1)

    def as_vector(self, ink=1, paper=0):
        """Return flat tuple of user-specified foreground and background objects."""
        return tuple(
            ink if _c == self._1 else paper
            for _c in ''.join(self._pixels)
        )

    def as_bits(self, ink=1, paper=0):
        """Return flat bits as bytes string."""
        return (
            ''.join(self._pixels).encode('latin-1')
            .replace(self._1.encode('latin-1'), bytes((ink,)))
            .replace(self._0.encode('latin-1'), bytes((paper,)))
        )


    @classmethod
    def from_bytes(
            cls, byteseq, width=NOT_SET, height=NOT_SET,
            *, align='left', order='row-major', stride=NOT_SET,
            byte_swap=0, bit_order='big',
            **kwargs
        ):
        """
        Create raster from bytes/bytearray/int sequence.

        width: raster width in pixels
        height: raster height in pixels
        stride: number of pixels per row (default: what's needed for alignment)
        align: 'left' or 'right' for byte-alignment; 'bit' for bit-alignment
        order: 'row-major' (default) or 'column-major' order of the byte array (no effect if align == 'bit')
        byte_swap: swap byte order in units of n bytes, 0 (default) for no swap
        bit_order: per-byte bit endianness; 'little' for lsb left, 'big' (default) for msb left
        """
        if all(_arg is NOT_SET for _arg in (width, height, stride)):
            raise ValueError(
                'At least one of width, height or stride must be speecified'
            )
        if width == 0 or height == 0:
            if height is NOT_SET:
                height = 0
            return cls.blank(width, height)
        if stride is not NOT_SET:
            if width is NOT_SET:
                width = stride
        elif align != 'bit':
            if width is NOT_SET:
                stride = 8 * (len(byteseq) // height)
            else:
                stride = 8 * ceildiv(width, 8)
        else:
            if width is NOT_SET:
                stride = (8 * len(byteseq)) // height
            else:
                stride = width
        if byte_swap:
            orig_length = len(byteseq)
            byteseq = byteseq.ljust(ceildiv(len(byteseq), byte_swap)*byte_swap, b'\0')
            # grouper
            args = [iter(byteseq)] * byte_swap
            byteseq = b''.join(bytes(_chunk[::-1]) for _chunk in zip(*args))
            byteseq = byteseq[:orig_length]
        # byte matrix order. no effect for bit alignment
        if order == 'column-major' and align != 'bit':
            byteseq = b''.join(
                byteseq[_offs::height]
                for _offs in range(height)
            )
        if not byteseq:
            bitseq = ''
        else:
            bitseq = bin(
                int.from_bytes(byteseq, 'big'))[2:].zfill(8*len(byteseq)
            )
        # per-byte bit swap.
        if bit_order == 'little':
            bitseq = reverse_by_group(bitseq)
        return cls.from_vector(
            bitseq, width=width, height=height, stride=stride, align=align,
            _0='0', _1='1',
        )

    def as_byterows(self, *, align='left', bit_order='big'):
        """
        Convert raster to bytes, by row

        align: 'left' or 'right'
        bit_order: per-byte bit endianness; 'little' for lsb left, 'big' (default) for msb left
        """
        if not self.height or not self.width:
            return ()
        rows = (
            ''.join(_row)
            for _row in self.as_matrix(paper='0', ink='1')
        )
        bytewidth = ceildiv(self.width, 8)
        if align.startswith('l'):
            rows = (_row.ljust(8*bytewidth, '0') for _row in rows)
        else:
            rows = (_row.rjust(8*bytewidth, '0') for _row in rows)
        if bit_order == 'little':
            rows = (reverse_by_group(_row) for _row in rows)
        byterows = (int(_row, 2).to_bytes(bytewidth, 'big') for _row in rows)
        return byterows

    def as_bytes(
            self, *,
            align='left', stride=NOT_SET, byte_swap=0, bit_order='big',
        ):
        """
        Convert raster to flat bytes.

        stride: number of pixels per row (default: what's needed for alignment)
        align: 'left' or 'right' for byte-alignment; 'bit' for bit-alignment
        byte_swap: swap byte order in units of n bytes, 0 (default) for no swap
        bit_order: per-byte bit endianness; 'little' for lsb left, 'big' (default) for msb left
        """
        if not self.height or not self.width:
            return b''
        if stride is not NOT_SET:
            if align == 'right':
                raster = self.expand(left=stride-self.width)
            else:
                # left or bit-aligned
                raster = self.expand(right=stride-self.width)
        else:
            raster = self
        if align == 'bit':
            bits = ''.join(
                ''.join(_row)
                for _row in raster.as_matrix(paper='0', ink='1')
            )
            # per-byte bit swap.
            if bit_order == 'little':
                bits = reverse_by_group(bits)
            bytesize = ceildiv(len(bits), 8)
            byterows = (int(bits, 2).to_bytes(bytesize, 'big'),)
        else:
            byterows = raster.as_byterows(align=align, bit_order=bit_order)
        byteseq = b''.join(byterows)
        if byte_swap:
            # grouper
            byteseq = byteseq.ljust(ceildiv(len(byteseq), byte_swap)*byte_swap, b'\0')
            args = [iter(byteseq)] * byte_swap
            byteseq = b''.join(bytes(_chunk[::-1]) for _chunk in zip(*args))
        return byteseq

    def get_byte_size(self, *, align='left', stride=NOT_SET):
        """
        Calculate size of bytes representation

        stride: number of pixels per row (default: what's needed for alignment)
        align: 'left' or 'right' for byte-alignment; 'bit' for bit-alignment
        """
        if not self.height or not self.width:
            return 0
        if stride is NOT_SET:
            stride = self.width
        if align == 'bit':
            return ceildiv(stride * self.height, 8)
        return ceildiv(stride, 8) * self.height

    @classmethod
    def from_hex(cls, hexstr, width, height=NOT_SET, *, align='left'):
        """Create raster from hex string."""
        byteseq = bytes.fromhex(hexstr)
        return cls.from_bytes(byteseq, width, height, align=align)

    def as_hex(self, *, align='left'):
        """Convert raster to hex string."""
        return self.as_bytes(align=align).hex()


    ##########################################################################

    @classmethod
    def concatenate(cls, *row_of_rasters):
        """Concatenate rasters left-to-right."""
        if not row_of_rasters:
            return cls()
        # drop empties
        row_of_rasters = tuple(
            _raster for _raster in row_of_rasters if _raster.width
        )
        heights = set(_raster.height for _raster in row_of_rasters)
        if len(heights) > 1:
            raise ValueError('Rasters must be of same height.')
        matrices = (_raster.as_matrix() for _raster in row_of_rasters)
        concatenated = cls(
            sum(_row, ())
            for _row in zip(*matrices)
        )
        return concatenated


    ##########################################################################
    # transformations

    # orthogonal transformations

    def mirror(self):
        """Reverse pixels horizontally."""
        return type(self)(
            self._outer(_row[::-1] for _row in self._pixels),
            _0=self._0, _1=self._1
        )

    def flip(self):
        """Reverse pixels vertically."""
        return type(self)(
            self._pixels[::-1],
            _0=self._0, _1=self._1
        )

    def transpose(self):
        """Transpose glyph."""
        return type(self)(
            self._outer(self._inner(_r) for _r in zip(*self._pixels)),
            _0=self._0, _1=self._1
        )

    turn = turn_method

    # ink shifts on constant raster size

    def roll(self, down:int=0, right:int=0):
        """
        Cycle rows and/or columns in raster.

        down: number of rows to roll (down if positive, up if negative)
        right: number of columns to roll (to right if positive, to left if negative)
        """
        rolled = self
        rows, columns = down, right
        if self.height > 1 and rows:
            rolled = rolled._pixels[-rows:] + rolled._pixels[:-rows]
        if self.width > 1 and columns:
            rolled = self._outer(
                _row[-columns:] + _row[:-columns]
                for _row in rolled._pixels
            )
        return type(self)(rolled, _0=self._0, _1=self._1)

    def shift(self, *, left:int=0, down:int=0, right:int=0, up:int=0):
        """
        Shift rows and/or columns in raster, replacing with paper

        left: number of columns to move to left
        down: number of rows to move down
        right: number of columns to move to right
        up: number of rows to move up
        """
        if min(left, down, right, up) < 0:
            raise ValueError('Can only shift glyph by a positive amount.')
        rows = down - up
        columns = right - left
        _0, _1 = '0', '1'
        pixels = tuple(
            ''.join(_row)
            for _row in self.as_matrix(paper=_0, ink=_1)
        )
        empty_row = _0 * self.width
        if rows > 0:
            shifted = (empty_row,) * rows + pixels[:-rows]
        else:
            shifted = pixels[-rows:] + (empty_row,) * -rows
        if columns > 0:
            return type(self)(
                self._outer(_0 * columns + _row[:-columns] for _row in shifted),
                _0=_0, _1=_1
            )
        else:
            return type(self)(
                self._outer(_row[-columns:] + _0 * -columns for _row in shifted),
                _0=_0, _1=_1
            )

    # raster size changes

    def crop(self, left:int=0, bottom:int=0, right:int=0, top:int=0):
        """
        Crop glyph.

        left: number of columns to remove from left
        bottom: number of rows to remove from bottom
        right: number of columns to remove from right
        top: number of rows to remove from top
        """
        if min(left, bottom, right, top) < 0:
            raise ValueError('Can only crop glyph by a positive amount.')
        if self.height-top-bottom <= 0:
            return type(self).blank(width=max(0, self.width-right-left))
        return type(self)(self._outer(
                _row[left : (-right if right else None)]
                for _row in self._pixels[top : (-bottom if bottom else None)]
            ),
            _0=self._0, _1=self._1
        )

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
        if not top+self.height+bottom:
            return type(self).blank(width=right+self.width+left)
        new_width = left + self.width + right
        empty_row = self._0 * new_width
        pixels = (
            self._outer((empty_row,)) * top
            + self._outer(
                self._0 * left + _row + self._0 * right
                for _row in self._pixels
            )
            + self._outer((empty_row,)) * bottom
        )
        return type(self)(pixels, _0=self._0, _1=self._1)

    def stretch(self, factor_x:int=1, factor_y:int=1):
        """
        Repeat rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        """
        # vertical stretch
        pixels = (_row for _row in self._pixels for _ in range(factor_y))
        # horizontal stretch
        pixels = (
            self._inner(_col for _col in _row for _ in range(factor_x))
            for _row in pixels
        )
        return type(self)(self._outer(pixels), _0=self._0, _1=self._1)

    def shrink(self, factor_x:int=1, factor_y:int=1):
        """
        Remove rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        """
        # vertical shrink
        shrunk = self._pixels[::factor_y]
        # horizontal shrink
        shrunk = self._outer(_row[::factor_x] for _row in shrunk)
        return type(self)(shrunk, _0=self._0, _1=self._1)

    # effects

    # pylint: disable=no-method-argument
    def overlay(*others, operator=any):
        """
        Overlay equal-sized rasters.

        operator: aggregation function, callable on iterable on bool/int.
                  Use any for additive, all for masking.
        """
        self = others[0]
        # use as instance method or class method
        matrices = tuple(_r.as_matrix() for _r in others)
        rows = tuple(zip(*_row) for _row in zip(*matrices))
        combined = self._outer(
            self._inner(self._1 if operator(_item) else self._0 for _item in _row)
            for _row in rows
        )
        return type(self)(combined, _0=self._0, _1=self._1)

    def invert(self):
        """Reverse video."""
        return type(self)(self._pixels, _0=self._1, _1=self._0)

    def smear(self, *, left:int=0, right:int=0, up:int=0, down:int=0):
        """
        Repeat inked pixels.

        left: number of times to repeat inked pixel leftwards
        right: number of times to repeat inked pixel rightwards
        up: number of times to repeat inked pixel upwards
        down: number of times to repeat inked pixel downwards
        """
        work = self
        work = work.overlay(*(work.shift(left=_i+1) for _i in range(left)))
        work = work.overlay(*(work.shift(right=_i+1) for _i in range(right)))
        work = work.overlay(*(work.shift(up=_i+1) for _i in range(up)))
        work = work.overlay(*(work.shift(down=_i+1) for _i in range(down)))
        return work

    def shear(
            self, direction:str='right',
            pitch:Coord=(1, 1), modulo:int=0,
        ):
        """Transform raster by shearing diagonally."""
        direction = direction[0].lower()
        xpitch, ypitch = pitch
        shiftrange = range(self.height)[::-1]
        shiftrange = (
            (_y*xpitch + modulo)//ypitch - (modulo==ypitch)
            for _y in shiftrange
        )
        empty = self._0 * self.width
        if direction == 'l':
            return type(self)(
                self._outer(
                    _row[_y:] + empty[:_y]
                    for _row, _y in zip(self._pixels, shiftrange)
                ),
                _0=self._0, _1=self._1
            )
        elif direction == 'r':
            return type(self)(
                self._outer(
                    empty[:_y] + _row[:self.width-_y]
                    for _row, _y in zip(self._pixels, shiftrange)
                ),
                _0=self._0, _1=self._1
            )
        raise ValueError(
            f'Shear direction must be `left` or `right`, not `{direction}`'
        )

    def underline(self, top_height:int=0, bottom_height:int=0):
        """Return a raster with a line added."""
        _0, _1 = '0', '1'
        if bottom_height > top_height:
            return self
        top_height = min(self.height, max(0, top_height))
        bottom_height = min(self.height, max(0, bottom_height))
        pixels = self._outer(
            _1 * self.width
            if top_height >= self.height-_line-1 >= bottom_height
            else ''.join(_row)
            for _line, _row in enumerate(self.as_matrix(paper=_0, ink=_1))
        )
        return type(self)(pixels, _0=_0, _1=_1)
