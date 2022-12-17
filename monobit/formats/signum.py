"""
monobit.formats.signum - Signum! 2 editor and printer font formats

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..struct import big_endian as be
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..streams import FileFormatError
from ..binary import ceildiv, bytes_to_bits


# editor font
_E24_MAGIC = b'eset0001'
# printer fonts
_L30_MAGIC = b'ls300001'

# p24, p09, l30

_SIGNUM_RANGE = range(128)


@loaders.register('e24', name='signum', magic=(_E24_MAGIC,))
def load_signum(instream, where=None):
    """Load font from signum file."""
    glyphs = _read_editor(instream)
    return Font(glyphs)

@loaders.register('l30', name='signum-printer', magic=(_L30_MAGIC,))
def load_signum(instream, where=None):
    """Load font from signum file."""
    glyphs = _read_printer(instream)
    return Font(glyphs)


################################################################################
# signum binary formats

# file format reverse-engineered and documented by Xiphoseer
# https://sdo.dseiler.eu/formats/eset

_E24_HEADER = be.Struct(
    magic='8s',
    # font type, or number of chars? should be 128
    font_type='uint32',
    # mysterious 128 bytes.
    # usually the first 64 are fairly dense and more or less random
    # but sometimes they are text or null
    # followed by 6 bytes that are almost always 0x2710 (10000), 0x000d, 0x23bc
    # followed by 58 nulls
    something='128s',
    buffer_size='uint32',
    # offset table, which we'll ignore
    offsets=(be.uint32 * 127)
)

_GLYPH_HEADER = be.Struct(
    top='uint8',
    height='uint8',
    width='uint8',
    reserved='uint8',
)

def _read_editor(instream):
    """Read Signum! editor binary file and return glyphs."""
    return _read_signum(instream, fixed_byte_width=2, top=24)

def _read_printer(instream):
    # top line relative to baseline
    return _read_signum(instream, fixed_byte_width=None, top=48)

def _read_signum(instream, fixed_byte_width=None, top=24):
    """Read Signum! printer binary file and return glyphs."""
    data = instream.read()
    header = _E24_HEADER.from_bytes(data)
    ofs = header.size
    glyphs = []
    for cp in range(127):
        glyph_header = _GLYPH_HEADER.from_bytes(data, ofs)
        ofs += glyph_header.size
        # printer fonts provide byte width in width field
        # whereas editor files provide advance width
        if fixed_byte_width:
            bytewidth = fixed_byte_width
            advance = glyph_header.width
        else:
            bytewidth = glyph_header.width
            # we'll adjust this later based on actual padding
            advance = bytewidth * 8
        bytesize = glyph_header.height * bytewidth
        glyph_bytes = data[ofs:ofs+bytesize]
        ofs += bytesize
        notes = ''
        if glyph_header.reserved:
            notes = f'header_padding=0x{glyph_header.reserved:02x}'
        if (bytesize % 2):
            pad = data[ofs]
            logging.debug(f'glyph {cp:02x} padding byte {pad:02x}')
            ofs += 1
            if pad:
                notes += (' ' if notes else '') + f'padding=0x{pad:02x}'
        glyph = Glyph.from_bytes(
            glyph_bytes,
            width=8*bytewidth,
            codepoint=cp,
            shift_up=top-glyph_header.top-glyph_header.height,
            right_bearing=advance-8*bytewidth,
            signum=notes if notes else None,
        )
        # as the width in printer fonts is given in bytes, not pixels,
        # these seem to have no information about advance width.
        # from actual files it looks reasonable to preserve only left bearing
        # it is unclear how the advance width of whitespace is determined
        # perhaps this is encoded in the unknown parts of the file header
        glyph = glyph.crop(
            right=glyph.padding.right,
            adjust_metrics=bool(fixed_byte_width)
        ).drop('shift-left')
        glyphs.append(glyph)
    return glyphs
