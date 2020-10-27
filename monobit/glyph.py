"""
monobit.glyph - representation of single glyph

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import binascii

from .base import scriptable
from .binary import ceildiv, bytes_to_bits
from .text import to_text

NOT_SET = object()

class Glyph:
    """Single glyph."""

    def __init__(self, pixels=((),), codepoint=None, char='', labels=(), comments=()):
        """Create glyph from tuple of tuples."""
        # glyph data
        self._rows = tuple(tuple(bool(_bit) for _bit in _row) for _row in pixels)
        if len(set(len(_r) for _r in self._rows)) > 1:
            raise ValueError(
                f'All rows in a glyph must be of the same width: {repr(self)}'
            )
        # annotations
        self._comments = tuple(comments)
        self._codepoint = codepoint
        self._char = char
        self._labels = tuple(labels)

    @property
    def labels(self):
        return self._labels

    @property
    def char(self):
        return self._char

    @property
    def codepoint(self):
        return self._codepoint

    @property
    def comments(self):
        return self._comments

    def __repr__(self):
        """Text representation."""
        return "Glyph(\n  '{}'\n)".format(
            to_text(self.as_matrix(fore='@', back='.'), line_break="'\n  '")
        )

    def add_annotations(self, *, labels=(), comments=()):
        """Return a copy of the glyph with added labels or comments."""
        return self.modify(
            labels=self._labels + tuple(labels),
            comments=self._comments + tuple(comments)
        )

    def set_annotations(self, *, labels=NOT_SET, char=NOT_SET, codepoint=NOT_SET, comments=NOT_SET):
        """Return a copy of the glyph with different annotations."""
        return self.modify(labels=labels, char=char, codepoint=codepoint, comments=comments)

    @scriptable
    def drop_comments(self):
        """Return a copy of the glyph without comments."""
        return self.modify(comments=())

    def modify(
            self, pixels=NOT_SET, *, labels=NOT_SET, char=NOT_SET, codepoint=NOT_SET, comments=NOT_SET
        ):
        """Return a copy of the glyph with changes."""
        if pixels is NOT_SET:
            pixels = self._rows
        if labels is NOT_SET:
            labels = self._labels
        if codepoint is NOT_SET:
            codepoint = self._codepoint
        if char is NOT_SET:
            char = self._char
        if comments is NOT_SET:
            comments = self._comments
        return Glyph(
            tuple(pixels),
            codepoint=codepoint,
            char=char,
            labels=tuple(labels),
            comments=tuple(comments)
        )

    @property
    def comments(self):
        """Extract comments."""
        return self._comments

    @classmethod
    def empty(cls, width=0, height=0):
        """Create whitespace glyph."""
        return cls(((0,) * width,) * height)

    @classmethod
    def from_matrix(cls, rows, background):
        """Create glyph from sequence of sequence of objects."""
        return cls(tuple(
            tuple(_char not in background for _char in _row)
            for _row in rows
        ))

    def as_matrix(self, fore=1, back=0):
        """Return matrix of user-specified forground and background objects."""
        return tuple(
            tuple(fore if _c else back for _c in _row)
            for _row in self._rows
        )

    def as_tuple(self, fore=1, back=0):
        """Return flat tuple of user-specified forground and background objects."""
        return tuple(
            fore if _c else back
            for _row in self._rows
            for _c in _row
        )

    @staticmethod
    def from_bytes(byteseq, width, height=None):
        """Create glyph from bytes/bytearray/int sequence."""
        if not width:
            return Glyph()
        if height is not None:
            bytewidth = len(byteseq) // height
        else:
            bytewidth = ceildiv(width, 8)
        byteseq = list(byteseq)
        rows = [byteseq[_offs:_offs+bytewidth] for _offs in range(0, len(byteseq), bytewidth)]
        return Glyph(tuple(bytes_to_bits(_row, width) for _row in rows))

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

    @staticmethod
    def from_hex(hexstr, width, height):
        """Create glyph from hex string."""
        return Glyph.from_bytes(binascii.unhexlify(hexstr.encode('ascii')), width, height)

    def as_hex(self):
        """Convert glyph to hex string."""
        return binascii.hexlify(self.as_bytes()).decode('ascii')

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
    def ink_width(self):
        """Ink width of glyph."""
        if not self._rows:
            return 0
        # maximum row inkwidth
        return max(
            (len(_row) - _row.index(True) - list(reversed(_row)).index(True)) if True in _row else 0
            for _row in self._rows
        )

    @property
    def ink_height(self):
        """Ink height of glyph."""
        if not self._rows:
            return 0
        inked = [True in _row for _row in self._rows]
        return len(inked) - inked.index(True) - list(reversed(inked)).index(True)

    @property
    def bounding_box(self):
        """Dimensions of tightest box to fit glyph."""
        return self.ink_width, self.ink_height

    @property
    def ink_offsets(self):
        """Offset from sides to bounding box. Left, bottom, right, top."""
        if not self._rows:
            return 0, 0, 0, 0
        row_inked = [True in _row for _row in self._rows]
        if True not in row_inked:
            return self.width, self.height, 0, 0
        bottom = list(reversed(row_inked)).index(True)
        top = row_inked.index(True)
        col_inked = [bool(sum(_row[_i] for _row in self._rows)) for _i in range(self.width)]
        left = col_inked.index(True)
        right = list(reversed(col_inked)).index(True)
        return left, bottom, right, top

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
            return cls.empty()
        for glyph in glyph_iter:
            combined = combined.superimposed(glyph)
        return combined


    ##########################################################################

    @scriptable
    def mirror(self):
        """Reverse pixels horizontally."""
        return self.modify(tuple(_row[::-1] for _row in self._rows))

    @scriptable
    def flip(self):
        """Reverse pixels vertically."""
        return self.modify(self._rows[::-1])

    @scriptable
    def transpose(self):
        """Transpose glyph."""
        return self.modify(tuple(tuple(_x) for _x in zip(*self._rows)))

    @scriptable
    def rotate(self, turns:int=1):
        """Rotate by 90-degree turns; positive is clockwise."""
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
        """Crop glyph, inclusive bounds."""
        return self.modify(tuple(
            _row[left : (-right if right else None)]
            for _row in self._rows[top : (-bottom if bottom else None)]
        ))

    @scriptable
    def expand(self, left:int=0, top:int=0, right:int=0, bottom:int=0):
        """Add empty space."""
        if self._rows:
            old_width = len(self._rows[0])
        else:
            old_width = 0
        new_width = left + old_width + right
        return self.modify(
            ((False,) * new_width,) * top
            + tuple((False,)*left + _row + (False,)*right for _row in self._rows)
            + ((False,) * new_width,) * bottom
        )

    @scriptable
    def stretch(self, factor_x:int=1, factor_y:int=1):
        """Repeat rows and/or columns."""
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
        """Remove rows and/or columns."""
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
