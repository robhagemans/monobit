"""
monobit.glyph - representation of single glyph

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .scripting import scriptable
from .binary import ceildiv
from .basetypes import Bounds

# sentinel object
NOT_SET = object()


class Raster:
    """Bit matrix."""

    _0 = False
    _1 = True

    def __init__(self, pixels=(), *, _0=NOT_SET, _1=NOT_SET):
        """Create glyph from tuple of tuples."""
        if _0 is NOT_SET or _1 is NOT_SET:
            # glyph data
            self._pixels = tuple(
                tuple(bool(_bit) for _bit in _row)
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

    # NOTE - these following are shadowed in GlyphProperties

    @property
    def width(self):
        """Raster width of glyph."""
        if not self._pixels:
            return 0
        return len(self._pixels[0])

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
    # creation and conversion

    @classmethod
    def blank(cls, width=0, height=0):
        """Create whitespace glyph."""
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

    # TODO - need method that outputs tuple of str, this one shld be as_string
    def as_text(self, *, ink='@', paper='.', start='', end='\n'):
        """Convert glyph to text."""
        contents = (end + start).join(
            ''.join(_row)
            for _row in self.as_matrix(ink=ink, paper=paper)
        )
        if not contents:
            return ''
        return ''.join((start, contents, end))

    @classmethod
    def from_vector(cls, bitseq, *, stride, width=NOT_SET, align='left', _0=NOT_SET, _1=NOT_SET, **kwargs):
        """Create glyph from flat immutable sequence representing bits."""
        if not bitseq or width == 0 or stride == 0:
            return cls()
        if width is NOT_SET:
            width = stride
        if align.startswith('r'):
            offset = stride - width
        else:
            offset = 0
        rows = tuple(
            bitseq[_offs:_offs+width]
            for _offs in range(offset, len(bitseq), stride)
        )
        return cls(rows, _0=_0, _1=_1, **kwargs)

    def as_vector(self, ink=1, paper=0):
        """Return flat tuple of user-specified foreground and background objects."""
        return tuple(
            _c
            for _row in self.as_matrix(ink=ink, paper=paper)
            for _c in _row
        )

    @classmethod
    def from_bytes(cls, byteseq, width, height=NOT_SET, *, align='left', **kwargs):
        """Create glyph from bytes/bytearray/int sequence."""
        if width == 0 or height == 0:
            return cls.blank(width, height)
        if height is not NOT_SET:
            stride = 8 * (len(byteseq) // height)
        else:
            stride = 8 * ceildiv(width, 8)
        bitseq = bin(int.from_bytes(byteseq, 'big'))[2:].zfill(8*len(byteseq))
        return cls.from_vector(
            bitseq, width=width, stride=stride, align=align,
            _0='0', _1='1',
            **kwargs
        )

    def as_bytes(self, *, align='left'):
        """Convert glyph to flat bytes."""
        if not self.height or not self.width:
            return b''
        bytewidth = ceildiv(self.width, 8)
        rows = (
            ''.join(_row)
            for _row in self.as_matrix(paper='0', ink='1')
        )
        if align.startswith('l'):
            rows = (_row.ljust(8*bytewidth, '0') for _row in rows)
        rows = (int(_row, 2).to_bytes(bytewidth, 'big') for _row in rows)
        return b''.join(rows)

    @classmethod
    def from_hex(cls, hexstr, width, height=NOT_SET, *, align='left', **kwargs):
        """Create glyph from hex string."""
        byteseq = bytes.fromhex(hexstr)
        return cls.from_bytes(byteseq, width, height, align=align, **kwargs)

    def as_hex(self, *, align='left'):
        """Convert glyph to hex string."""
        return self.as_bytes(align=align).hex()

    ###############################################################################################
    # operations

    def reduce(self):
        """Return a glyph reduced to the bounding box."""
        return self.crop(*self.padding)

    def superimposed(self, other):
        """Superimpose another glyph of the same size."""
        return self.modify(
            tuple(
                _pix or _pix1
                for _pix, _pix1 in zip(_row, _row1)
            )
            for _row, _row1 in zip(self._pixels, other._pixels)
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


    @scriptable
    def mirror(self):
        """Reverse pixels horizontally."""
        return self.modify(tuple(_row[::-1] for _row in self._pixels))

    @scriptable
    def flip(self):
        """Reverse pixels vertically."""
        return self.modify(self._pixels[::-1])

    @scriptable
    def roll(self, rows:int=0, columns:int=0):
        """
        Cycle rows and/or columns in glyph.

        rows: number of rows to roll (down if positive)
        columns: number of columns to roll (to right if positive)
        """
        rolled = self
        if self.height > 1 and rows:
            rolled = rolled.modify(rolled._pixels[-rows:] + rolled._pixels[:-rows])
        if self.width > 1 and columns:
            rolled = rolled.modify(tuple(_row[-columns:] + _row[:-columns] for _row in rolled._pixels))
        return rolled

    @scriptable
    def transpose(self):
        """Transpose glyph."""
        return self.modify(tuple(tuple(_x) for _x in zip(*self._pixels)))

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
        return self.modify(tuple(tuple((not _col) for _col in _row) for _row in self._pixels))

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
            for _row in self._pixels[top : (-bottom if bottom else None)]
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
        _0, _1 = '0', '1'
        pixels = (
            ''.join(_row)
            for _row in self.as_matrix(paper=_0, ink=_1)
        )
        empty_row = _0 * new_width
        pixels = (
            (empty_row,) * top
            + tuple(_0 * left + _row + _0 * right for _row in self._pixels)
            + (empty_row,) * bottom
        )
        return type(self)(pixels, _0=_0, _1=_1)

    @scriptable
    def stretch(self, factor_x:int=1, factor_y:int=1):
        """
        Repeat rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        """
        # vertical stretch
        glyph = tuple(_row for _row in self._pixels for _ in range(factor_y))
        # horizontal stretch
        glyph = tuple(
            tuple(_col for _col in _row for _ in range(factor_x))
            for _row in glyph
        )
        return self.modify(glyph)


    @scriptable
    def smear(self, *, left:int=0, right:int=0, up:int=0, down:int=0):
        """
        Repeat ink on unchanged canvas size

        left: number of times to repeat inked pixel leftwards
        right: number of times to repeat inked pixel rightwards
        up: number of times to repeat inked pixel upwards
        down: number of times to repeat inked pixel downwards
        """
        work = self.modify()
        for _ in range(left):
            work = work.superimposed(work.crop(left=1).expand(right=1))
        for _ in range(right):
            work = work.superimposed(work.crop(right=1).expand(left=1))
        for _ in range(up):
            work = work.superimposed(work.crop(top=1).expand(bottom=1))
        for _ in range(down):
            work = work.superimposed(work.crop(bottom=1).expand(top=1))
        return work


    @scriptable
    def shrink(self, factor_x:int=1, factor_y:int=1, force:bool=False):
        """
        Remove rows and/or columns.

        factor_x: factor to shrink horizontally
        factor_y: factor to shrink vertically
        force: remove rows/columns even if not repeated
        """
        # vertical shrink
        shrunk_glyph = self._pixels[::factor_y]
        if not force:
            # check we're not throwing away stuff
            for offs in range(1, factor_y):
                alt = self._pixels[offs::factor_y]
                if shrunk_glyph != alt:
                    raise ValueError("can't shrink glyph without loss")
        # horizontal stretch
        shrunk_glyph = tuple(_row[::factor_x] for _row in shrunk_glyph)
        return self.modify(shrunk_glyph)
