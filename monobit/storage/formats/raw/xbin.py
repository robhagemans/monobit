"""
monobit.storage.formats.raw.xbin - XBIN font section

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single


###############################################################################
# XBIN font section
# https://web.archive.org/web/20120204063040/http://www.acid.org/info/xbin/x_spec.htm

_XBIN_MAGIC = b'XBIN\x1a'
_XBIN_HEADER = le.Struct(
    magic='5s',
    # Width of the image in character columns.
    width='word',
    # Height of the image in character rows.
    height='word',
    # Number of pixel rows (scanlines) in the font, Default value for VGA is 16.
    # Any value from 1 to 32 is technically possible on VGA. Any other values
    # should be considered illegal.
    fontsize='byte',
    # A set of flags indicating special features in the XBin file.
    # 7 6 5  4        3        2        1    0
    # Unused 512Chars NonBlink Compress Font Palette
    palette=bitfield('byte', 1),
    font=bitfield('byte', 1),
    compress=bitfield('byte', 1),
    nonblink=bitfield('byte', 1),
    has_512_chars=bitfield('byte', 1),
    unused_flags=bitfield('byte', 3)
)

@loaders.register(
    name='xbin',
    magic=(_XBIN_MAGIC,),
    patterns=('*.xb',),
)
def load_xbin(instream):
    """Load a XBIN font."""
    header = _XBIN_HEADER.read_from(instream)
    if header.magic != _XBIN_MAGIC:
        raise FileFormatError(
            f'Not an XBIN file: incorrect signature {header.magic}.'
        )
    if not header.font:
        raise FileFormatError('XBIN file contains no font.')
    height = header.fontsize
    if header.has_512_chars:
        count = 512
    else:
        count = 256
    # skip 48-byte palette, if present
    if header.palette:
        instream.read(48)
    font = load_bitmap(instream, width=8, height=height, count=count)
    font = font.modify(source_format='XBIN')
    return font


@savers.register(linked=load_xbin)
def save_xbin(fonts, outstream):
    """Save an XBIN font."""
    font = ensure_single(fonts)
    codepoints = font.get_codepoints()
    if not codepoints:
        raise ValueError('No storable codepoints found in font.')
    max_cp = max(int(_cp) for _cp in codepoints)
    if max_cp >= 512:
        logging.warning('Glyphs above codepoint 512 will not be stored.')
    blank = Glyph.blank(width=8, height=font.cell_size.y)
    if max_cp >= 256:
        count = 512
    else:
        count = 256
    glyphs = (font.get_glyph(_cp, missing=blank) for _cp in range(count))
    header = _XBIN_HEADER(
        magic=_XBIN_MAGIC,
        # no image stored, so no width and height
        fontsize=font.cell_size.y,
        font=1,
        has_512_glyphs=count==512,
    )
    outstream.write(bytes(header))
    font = Font(glyphs)
    save_bitmap(outstream, font)
