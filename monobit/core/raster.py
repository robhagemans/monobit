"""
monobit.core.raster - bitmap raster

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from itertools import zip_longest
from collections import deque

from monobit.base.binary import ceildiv, reverse_by_group
from monobit.base import Bounds, Coord, NOT_SET
from monobit.base.blocks import matrix_to_blocks, blockstr


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


# these allow for max 36 shades
_DIGITS = string.digits + string.ascii_lowercase


def base_conv(base):
    """Converter for non-negative number to str in given base."""
    if base == 2:
        return (lambda _v: bin(_v)[2:]), _DIGITS[:base]
    elif base == 8:
        return (lambda _v: oct(_v)[2:]), _DIGITS[:base]
    elif base == 10:
        return str, _DIGITS[:base]
    elif base == 16:
        return (lambda _v: hex(_v)[2:]), _DIGITS[:base]
    else:
        if base <= 36:
            inklevels = _DIGITS
        elif base == 256:
            inklevels = ''.join(chr(_i) for _i in range(base))
        else:
            raise ValueError(f'Unsupported base {base}')
        def _to_base(value):
            """Convert nonnegative integer to string in any base up to 256."""
            if value == 0:
                return inklevels[0]
            elif value < 0:
                raise ValueError('value must be nonegative')
            # notwithstanding best practice, the str concat here is
            # twice as fast for relevant input sizes as list or deque
            # credits to stackoverflow user Gareth
            # https://stackoverflow.com/questions/2063425/python-elegant-inverse-function-of-intstring-base
            digits = inklevels[value % base]
            while value >= base:
                value //= base
                digits = inklevels[value % base] + digits
            return digits
        return _to_base, inklevels


class Raster:
    """Bit matrix."""

    def __init__(self, pixels=(), *, width=NOT_SET, inklevels=NOT_SET):
        """Create raster from tuple of tuples of string."""
        if isinstance(pixels, type(self)):
            width = pixels._width
            inklevels = pixels._inklevels
            pixels = pixels._pixels
        else:
            if pixels:
                width = len(pixels[0])
            elif width is NOT_SET:
                width = 0
            if inklevels is NOT_SET:
                inklevels = _DIGITS[:2]
        self._pixels = pixels
        self._width = width
        self._inklevels = inklevels
        assert set(inklevels) >= set(''.join(pixels)), (
            f"{set(inklevels)} >= {set(''.join(pixels))} fails"
        )
        self._paper = self._inklevels[0]
        self._levels = len(self._inklevels)
        # check pixel matrix types
        if (
                not isinstance(self._pixels, tuple)
                or (self._pixels and (
                    not isinstance(self._pixels[0], str)
            ))):
            raise ValueError(f"Raster must be tuple of str: not {self._pixels}")
        # check pixel matrix geometry
        if len(set(len(_r) for _r in pixels)) > 1:
            raise ValueError(
                f"All rows in raster must be of the same width: {repr(self)}"
            )

    def __bool__(self):
        """Raster is not empty."""
        return bool(self.height and self.width)

    @property
    def levels(self):
        """Number of shades of ink."""
        return self._levels

    # NOTE - these following are shadowed in GlyphProperties

    @property
    def width(self):
        """Raster width."""
        return self._width

    @property
    def height(self):
        """Raster height."""
        return len(self._pixels)

    @property
    def padding(self):
        """Offset from raster sides to bounding box. Left, bottom, right, top."""
        if not self._pixels:
            return Bounds(0, 0, 0, 0)
        row_inked = tuple(
            any(_pix != self._paper for _pix in _row)
            for _row in self._pixels
        )
        if not any(row_inked):
            return Bounds(self.width, self.height, 0, 0)
        bottom = row_inked[::-1].index(True)
        top = row_inked.index(True)
        col_inked = tuple(
            any(_pix != self._paper for _pix in _col)
            for _col in zip(*self._pixels)
        )
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
    def blank(cls, width=0, height=0, levels=2):
        """Create uninked raster."""
        _, inklevels = base_conv(levels)
        if height == 0:
            return cls(width=width, inklevels=inklevels)
        return cls((inklevels[0] * width,) * height, inklevels=inklevels)

    def is_blank(self):
        """Raster has no ink."""
        return all(_pix == self._paper for _row in self._pixels for _pix in _row)

    @classmethod
    def from_vector(
            cls, bitseq, *,
            stride, width=NOT_SET, height=NOT_SET, align='left',
            inklevels=NOT_SET
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
        return cls.from_matrix(rows, inklevels=inklevels)

    def as_vector(self, inklevels=NOT_SET):
        """Return flat tuple of user-specified foreground and background objects."""
        return tuple(
            _c
            for _row in self._as_iter(inklevels=inklevels)
            for _c in _row
        )

    def as_bits(self, inklevels=NOT_SET):
        """Return flat bits as bytes string. Inklevels must be int or bytes."""
        if inklevels is NOT_SET:
            inklevels = bytes(range(self._levels))
        elif isinstance(inklevels, bytes):
            return b''.join(self._as_iter(inklevels=inklevels))
        else:
            # convert inklevels to tuple of bytes
            inklevels = tuple(
                bytes((_l,)) if isinstance(_l, int) else bytes(_l)
                for _l in inklevels
            )
            return b''.join(
                b''.join(_l) for _l in self._as_iter(inklevels=inklevels)
            )

    @classmethod
    def from_bytes(
            cls, byteseq, width=NOT_SET, height=NOT_SET,
            *, align='left', order='row-major', stride=NOT_SET,
            byte_swap=0, bit_order='big', bits_per_pixel=1,
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
        bits_per_pixel: bit depth; must be 1, 2 or 4 (default: 1)
        """
        if all(_arg is NOT_SET for _arg in (width, height, stride)):
            raise ValueError(
                'At least one of width, height or stride must be specified'
            )
        pixels_per_byte = 8 // bits_per_pixel
        levels = 2**bits_per_pixel
        if width == 0 or height == 0:
            if height is NOT_SET:
                height = 0
            return cls.blank(width, height, levels=levels)
        if stride is not NOT_SET:
            if width is NOT_SET:
                width = stride
        elif align != 'bit':
            if width is NOT_SET:
                stride = pixels_per_byte * (len(byteseq) // height)
            else:
                stride = pixels_per_byte * ceildiv(width, pixels_per_byte)
        else:
            if width is NOT_SET:
                stride = (pixels_per_byte * len(byteseq)) // height
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
        # convert bytes to pixels
        if levels == 256:
            inklevels = ''.join(chr(_i) for _i in range(256))
            bitseq = byteseq.decode('latin-1')
        else:
            to_base, inklevels = base_conv(levels)
            if not byteseq:
                bitseq = ''
            else:
                bitseq = (
                    to_base(int.from_bytes(byteseq, 'big'))
                    .zfill(pixels_per_byte*len(byteseq))
                )
        # per-byte bit swap.
        if bit_order == 'little':
            bitseq = reverse_by_group(bitseq)
        return cls.from_vector(
            bitseq, width=width, height=height, stride=stride, align=align,
            inklevels=inklevels,
        )

    def as_byterows(self, *, align='left', bit_order='big'):
        """
        Convert raster to bytes, by row

        align: 'left' or 'right'
        bit_order: per-byte bit endianness; 'little' for lsb left, 'big' (default) for msb left
        """
        if not self.height or not self.width:
            return ()
        _, inklevels = base_conv(self._levels)
        rows = (
            ''.join(_row)
            for _row in self.as_matrix(inklevels=inklevels)
        )
        bits_per_pixel = (self._levels - 1).bit_length()
        base = 2 ** bits_per_pixel
        pixels_per_byte = 8 // bits_per_pixel
        bytewidth = ceildiv(self.width, pixels_per_byte)
        stride = pixels_per_byte * bytewidth
        if align.startswith('l'):
            rows = (_row.ljust(stride, inklevels[0]) for _row in rows)
        else:
            rows = (_row.rjust(stride, inklevels[0]) for _row in rows)
        if bit_order == 'little':
            rows = (reverse_by_group(_row) for _row in rows)
        if base == 256:
            byterows = tuple(
                _row.encode('latin-1') for _row in rows
            )
        else:
            byterows = tuple(
                int(_row, base).to_bytes(bytewidth, 'big') for _row in rows
            )
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
            bits_per_pixel = (self._levels - 1).bit_length()
            base = 2 ** bits_per_pixel
            pixels_per_byte = 8 // bits_per_pixel
            _, inklevels = base_conv(self._levels)
            bits = ''.join(
                ''.join(_row)
                for _row in raster.as_matrix(inklevels=inklevels)
            )
            bytesize = ceildiv(len(bits), pixels_per_byte)
            # left align the bits to byte boundary
            bits = bits.ljust(bytesize * pixels_per_byte, inklevels[0])
            # per-byte bit swap.
            if bit_order == 'little':
                bits = reverse_by_group(bits)
            byterows = (int(bits, base).to_bytes(bytesize, 'big'),)
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
        bits_per_pixel = (self._levels - 1).bit_length()
        pixels_per_byte = 8 // bits_per_pixel
        if align == 'bit':
            return ceildiv(stride * self.height, pixels_per_byte)
        return ceildiv(stride, pixels_per_byte) * self.height

    @classmethod
    def from_hex(cls, hexstr, *args, **kwargs):
        """Create raster from hex string."""
        byteseq = bytes.fromhex(hexstr)
        return cls.from_bytes(byteseq, *args, **kwargs)

    def as_hex(self, **kwargs):
        """Convert raster to hex string."""
        return self.as_bytes(**kwargs).hex()

    @classmethod
    def from_matrix(cls, matrix, *, inklevels=NOT_SET, levels=2):
        """Create raster from iterable of iterables."""
        if inklevels is NOT_SET:
            inklevels = tuple(range(levels))
        if isinstance(inklevels, str):
            pixels = tuple(''.join(_row) for _row in matrix)
            return cls(pixels, inklevels=inklevels)
        else:
            _, str_inklevels = base_conv(len(inklevels))
            translator = {_k: _v for _k, _v in zip(inklevels, str_inklevels)}
            # glyph data
            pixels = tuple(
                ''.join(translator[_bit] for _bit in _row)
                for _row in matrix
            )
            return cls(pixels, inklevels=str_inklevels)

    def as_matrix(self, *, inklevels=NOT_SET):
        """Return matrix of user-specified foreground and background objects."""
        if inklevels is NOT_SET:
            inklevels = tuple(range(self._levels))
        return tuple(self._as_iter(inklevels=inklevels))

    def _as_iter(self, *, inklevels):
        """Return iterable of user-specified foreground and background objects."""
        if inklevels == self._inklevels:
            return self._pixels
        if isinstance(inklevels, str):
            # optimisation if inklevels consists of individual chars or bytes:
            translator = str.maketrans(''.join(self._inklevels), inklevels)
            return (
                _row.translate(translator)
                for _row in self._pixels
            )
        if isinstance(inklevels, bytes):
            # assuming we use one-byte codepoints
            current_inklevels = ''.join(self._inklevels).encode('latin-1')
            translator = bytes.maketrans(current_inklevels, inklevels)
            return (
                _row.encode('latin-1').translate(translator)
                for _row in self._pixels
            )
        # generic logic - allows for any object to be used
        translator = {_k: _v for _k, _v in zip(self._inklevels, inklevels)}
        return (
            tuple(translator[_c] for _c in _row)
            for _row in self._pixels
        )

    def as_text(self, *, inklevels=NOT_SET, start='', end='\n'):
        """Convert raster to text."""
        if not self.height:
            return ''
        if inklevels is NOT_SET:
            # default text representation uses . for paper and @ for full ink
            inklevels = '.' + _DIGITS[1:self._levels-1] + '@'
        rows = self._as_iter(inklevels=inklevels)
        return blockstr(
            start
            + (end+start).join(''.join(_row) for _row in rows)
            + end
        )

    def as_blocks(self, resolution=(2, 2)):
        """Convert raster to a string of block characters."""
        if not self.height:
            return ''
        if self._levels > 2:
            raise ValueError(f'Can not represent more than 2 shades.')
        matrix = self._as_iter()
        return matrix_to_blocks(matrix, *resolution)

    ##########################################################################

    @classmethod
    def concatenate(cls, *row_of_rasters):
        """Concatenate rasters left-to-right."""
        # drop empties
        row_of_rasters = tuple(
            _raster for _raster in row_of_rasters if _raster.width
        )
        if not row_of_rasters:
            return cls()
        heights = set(_raster.height for _raster in row_of_rasters)
        if len(heights) > 1:
            raise ValueError('Rasters must be of same height.')
        _, inklevels = base_conv(max(_r.levels for _r in row_of_rasters))
        matrices = tuple(
            _raster.as_matrix(inklevels=inklevels)
            for _raster in row_of_rasters
        )
        concatenated = cls.from_matrix(
            (''.join(_row) for _row in zip(*matrices)),
            inklevels=inklevels,
        )
        return concatenated

    @classmethod
    def stack(cls, *column_of_rasters):
        """Concatenate rasters top-to-bottom."""
        # drop empties
        column_of_rasters = tuple(
            _raster for _raster in column_of_rasters if _raster.height
        )
        if not column_of_rasters:
            return cls()
        widths = set(_raster.width for _raster in column_of_rasters)
        if len(widths) > 1:
            raise ValueError('Rasters must be of same width.')
        _, inklevels = base_conv(max(_r.levels for _r in column_of_rasters))
        matrices = (
            _raster.as_matrix(inklevels=inklevels)
            for _raster in column_of_rasters
        )
        concatenated = cls.from_matrix(
            (
                _row
                for _matrix in matrices
                for _row in _matrix
            ),
            inklevels=inklevels,
        )
        return concatenated


    ##########################################################################
    # transformations

    # orthogonal transformations

    def mirror(self):
        """Reverse pixels horizontally."""
        return type(self)(
            tuple(_row[::-1] for _row in self._pixels),
            inklevels=self._inklevels,
        )

    def flip(self):
        """Reverse pixels vertically."""
        return type(self)(
            self._pixels[::-1],
            inklevels=self._inklevels,
        )

    def transpose(self):
        """Transpose raster."""
        return type(self)(
            tuple(''.join(_r) for _r in zip(*self._pixels)),
            inklevels=self._inklevels,
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
            rolled = tuple(
                _row[-columns:] + _row[:-columns]
                for _row in rolled._pixels
            )
        return type(self)(rolled, inklevels=self._inklevels)

    def shift(self, *, left:int=0, down:int=0, right:int=0, up:int=0):
        """
        Shift rows and/or columns in raster, replacing with paper

        left: number of columns to move to left
        down: number of rows to move down
        right: number of columns to move to right
        up: number of rows to move up
        """
        if min(left, down, right, up) < 0:
            raise ValueError('Can only shift raster by a positive amount.')
        rows = down - up
        columns = right - left
        empty_row = self._paper * self.width
        if rows > 0:
            shifted = (empty_row,) * rows + self._pixels[:-rows]
        else:
            shifted = self._pixels[-rows:] + (empty_row,) * -rows
        if columns > 0:
            return type(self)(
                tuple(
                    self._paper * columns + _row[:-columns]
                    for _row in shifted
                ),
                inklevels=self._inklevels,
            )
        else:
            return type(self)(
                tuple(
                    _row[-columns:] + self._paper * -columns
                    for _row in shifted
                ),
                inklevels=self._inklevels,
            )

    # raster size changes

    def crop(self, left:int=0, bottom:int=0, right:int=0, top:int=0):
        """
        Crop raster.

        left: number of columns to remove from left
        bottom: number of rows to remove from bottom
        right: number of columns to remove from right
        top: number of rows to remove from top
        """
        if min(left, bottom, right, top) < 0:
            raise ValueError('Can only crop raster by a positive amount.')
        if self.height - top - bottom <= 0:
            return type(self).blank(width=max(0, self.width-right-left))
        return type(self)(
            tuple(
                _row[left : (-right if right else None)]
                for _row in self._pixels[top : (-bottom if bottom else None)]
            ),
            inklevels=self._inklevels,
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
            raise ValueError('Can only expand raster by a positive amount.')
        if not top+self.height+bottom:
            return type(self).blank(width=right+self.width+left)
        new_width = left + self.width + right
        empty_row = self._paper * new_width
        pixels = (
            (empty_row,) * top
            + tuple(
                self._paper * left + _row + self._paper * right
                for _row in self._pixels
            )
            + (empty_row,) * bottom
        )
        return type(self)(pixels, inklevels=self._inklevels)

    def stretch(self, factor_x:int=1, factor_y:int=1):
        """
        Repeat rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        """
        # vertical stretch
        pixels = (_row for _row in self._pixels for _ in range(factor_y))
        # horizontal stretch
        pixels = tuple(
            ''.join(_col for _col in _row for _ in range(factor_x))
            for _row in pixels
        )
        return type(self)(pixels, inklevels=self._inklevels)

    def shrink(self, factor_x:int=1, factor_y:int=1):
        """
        Remove rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        """
        # vertical shrink
        shrunk = self._pixels[::factor_y]
        # horizontal shrink
        shrunk = tuple(_row[::factor_x] for _row in shrunk)
        return type(self)(shrunk, inklevels=self._inklevels)

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
        ink = self._inklevels[-1]
        combined = tuple(
            ''.join(ink if operator(_item) else self._paper for _item in _row)
            for _row in rows
        )
        return type(self)(combined, inklevels=self._inklevels)

    def invert(self):
        """Reverse video."""
        return type(self)(self._pixels, inklevels=self._inklevels[::-1])

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
        empty = self._paper * self.width
        if direction == 'l':
            return type(self)(
                tuple(
                    _row[_y:] + empty[:_y]
                    for _row, _y in zip(self._pixels, shiftrange)
                ),
                inklevels=self._inklevels,
            )
        elif direction == 'r':
            return type(self)(
                tuple(
                    empty[:_y] + _row[:self.width-_y]
                    for _row, _y in zip(self._pixels, shiftrange)
                ),
                inklevels=self._inklevels,
            )
        raise ValueError(
            f'Shear direction must be `left` or `right`, not `{direction}`'
        )

    def underline(self, top_height:int=0, bottom_height:int=0):
        """Return a raster with a line added."""
        if bottom_height > top_height:
            return self
        top_height = min(self.height, max(0, top_height))
        bottom_height = min(self.height, max(0, bottom_height))
        ink = self._inklevels[-1]
        pixels = tuple(
            ink * self.width
            if top_height >= self.height-_line-1 >= bottom_height
            else _row
            for _line, _row in enumerate(self._pixels)
        )
        return type(self)(pixels, inklevels=self._inklevels)
