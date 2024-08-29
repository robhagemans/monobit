"""
monobit.storage.fontformats.softfont.bbc - Acorn BBC vfont format

(c) 2022--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base import Props, FileFormatError
from monobit.storage import loaders, savers
from monobit.core import Font, Glyph

from monobit.storage.utils.limitations import ensure_single, ensure_charcell


_BBC_VDU = b'\x17'

# storable code points
_BBC_RANGE = range(32, 256)


@loaders.register(name='bbc', magic=(_BBC_VDU,))
def load_bbc(instream):
    """Load font from bbc file."""
    glyphs = _read_bbc(instream)
    return Font(glyphs)


@savers.register(linked=load_bbc)
def save_bbc(fonts, outstream):
    """Save font to bbc file."""
    font = ensure_single(fonts)
    _write_bbc(outstream, font)


################################################################################
# see John Elliott's PSFTools, bbc2psf.c

def _read_bbc(instream):
    """Read bbc binary file and return glyphs."""
    glyphs = []
    while True:
        # scan file until a VDU 0x17 is found
        c = instream.read(1)
        if not c:
            break
        if c != _BBC_VDU:
            continue
        # next byte is codepoint
        cp = instream.read(1)
        # the next 8 bytes represent an 8x8 glyph
        glyphbytes = instream.read(8)
        glyphs.append(Glyph.from_bytes(glyphbytes, width=8, codepoint=cp))
    if not glyphs:
        raise FileFormatError(
            'Not a BBC soft font: VDU 0x17 sequence not found.'
        )
    return glyphs


###############################################################################
# writer

def _write_bbc(outstream, font):
    """Write bbc glyphs to binary file."""
    font = font.label(codepoint_from=font.encoding)
    font = font.subset(_BBC_RANGE)
    font = ensure_charcell(font, cell_size=(8, 8))
    glyph_bytes = tuple(
        b''.join((_BBC_VDU, bytes(_g.codepoint), _g.as_bytes()))
        for _g in font.glyphs
    )
    bitmap = b''.join(glyph_bytes)
    outstream.write(bitmap)
