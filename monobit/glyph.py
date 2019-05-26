"""
monobit.glyph - representation of single glyph

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import binascii

from .base import scriptable
from .binary import ceildiv, bytes_to_bits


class Glyph:
    """Single glyph."""

    def __init__(self, pixels=((),), comments=()):
        """Create glyph from tuple of tuples."""
        self._rows = tuple(tuple(bool(_bit) for _bit in _row) for _row in pixels)
        self._comments = comments

    def __repr__(self):
        """Text representation."""
        return "Glyph(\n  '{}'\n)".format(
            "'\n  '".join(self.as_text(foreground='@', background='.'))
        )

    def add_comments(self, comments):
        """Return a copy of the glyph with added comments."""
        return Glyph(self._rows, self._comments + tuple(comments))

    @property
    def comments(self):
        """Extract comments."""
        return self._comments

    @staticmethod
    def empty(width=0, height=0):
        """Create whitespace glyph."""
        return Glyph(((0,) * width,) * height)

    @staticmethod
    def from_text(rows, background):
        """Create glyph from sequence of str."""
        return Glyph(tuple(
            tuple(_char not in background for _char in _row)
            for _row in rows
        ))

    def as_text(self, foreground, background):
        """Convert glyph to tuple of str."""
        return tuple(
            ''.join((foreground if _bit else background) for _bit in _row)
            for _row in self._rows
        )

    def as_bits(self):
        """Return bit matrix."""
        return self._rows

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


    ##########################################################################

    @scriptable
    def mirror(self):
        """Reverse pixels horizontally."""
        return Glyph(tuple(_row[::-1] for _row in self._rows))

    @scriptable
    def flip(self):
        """Reverse pixels vertically."""
        return Glyph(self._rows[::-1])

    @scriptable
    def transpose(self):
        """Transpose glyph."""
        return Glyph(tuple(tuple(_x) for _x in zip(*self._rows)))

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
        return Glyph(tuple(tuple((not _col) for _col in _row) for _row in self._rows))

    @scriptable
    def crop(self, left:int=0, top:int=0, right:int=0, bottom:int=0):
        """Crop glyph, inclusive bounds."""
        return Glyph(tuple(
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
        return Glyph(
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
        return Glyph(glyph)

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
        return Glyph(glyph)
