"""
monobit.storage.formats.raw.writeon - Hercules Write On!

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single, ensure_charcell, make_contiguous


###############################################################################
# Hercules Write On! printing utility
# supplied with Hercules InColor utilities disk
# quotes are from the Write On! README section on the CVF.EXE conversion utility
# see also https://www.seasip.info/Unix/PSF/index.html

_WOF_MAGIC = b'\x45\x53\x01\x00'
_WOF_HEADER = le.Struct(
    magic=le.uint8 * 4,
    # header size
    size='uint16',
    # > Char Width is the width of the characters in the font,
    # > expressed in pixels.  This value must be a multiple of 8.
    char_width='uint16',
    # > Char Height is the height of the characters in the font,
    # > expressed in pixels.  This value must be a multiple of 14.
    char_height='uint16',
    # > Tile Height must always be 14 for Write On!  (When Write On!
    # > displays characters that are taller than 14 dots or wider than
    # > 8 dots, it assembles them from two or more 8 x 14 tiles, mosaic
    # > fashion.)
    tile_height='uint16',
    # > Dest Min Char is the ASCII code of the first character in the
    # > destination font (.WOF) file
    min_char='uint16',
    # > Dest Max Char is the ASCII code of the last character in the
    # > destination font (.WOF)
    max_char='uint16',
    unknown_0='uint16',
    maybe_width_too='uint16',
    unknown_1='uint16',
)

@loaders.register(
    name='writeon',
    magic=(_WOF_MAGIC,),
    patterns=('*.wof',),
)
def load_writeon(instream):
    """Load a Write On! font."""
    header = _WOF_HEADER.read_from(instream)
    if bytes(header.magic) != _WOF_MAGIC:
        raise FileFormatError(
            'Not a Hercules Write On! file: '
            f'incorrect signature {bytes(header.magic)}.'
        )
    font = load_bitmap(
        instream,
        width=header.char_width, height=header.char_height,
        first_codepoint=header.min_char,
        count=header.max_char-header.min_char+1,
    )
    font = font.modify(source_format='Hercules Write On!')
    font = font.label(char_from='ascii')
    return font


@savers.register(linked=load_writeon)
def save_writeon(fonts, outstream):
    """Save a Write On! font."""
    font = ensure_single(fonts)
    font = ensure_charcell(font)
    font = make_contiguous(font, supported_range=range(128), missing='space')
    header = _WOF_HEADER(
        magic=le.uint8.array(4)(*_WOF_MAGIC),
        size=_WOF_HEADER.size,
        char_width=font.cell_size.x,
        char_height=font.cell_size.y,
        # > Tile Height must always be 14 for Write On!
        tile_height=14,
        min_char=int(min(font.get_codepoints())),
        max_char=int(max(font.get_codepoints())),
        maybe_width_too=font.cell_size.x,
    )
    outstream.write(bytes(header))
    save_bitmap(outstream, font)
