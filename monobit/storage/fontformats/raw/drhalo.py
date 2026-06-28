"""
monobit.storage.fontformats.raw.drhalo - Dr. Halo / Dr. Genius font files

(c) 2023--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield
from monobit.storage.utils.limitations import ensure_single, ensure_charcell, make_contiguous

from .raw import load_bitmap, save_bitmap


###############################################################################
# Dr. Halo / Dr. Genius F*X*.FON
# this covers the bitmap fonts only
# most fonts included with Dr Halo are vector fonts
# for which I have not yet deciphered the encoding

# header structure (guess)
#
# field     contents    values
# --------- ----------- ------------------------------------------------
# le.u16    signature   AH
# le.u16                c8 00 (starts at 0) or df 00 (starts at 32)
# u8        bit flags?  0a or 8a
# u8        point size?
# le.u16                00 01 (starts at 0) or 00 03 (starts at 32)
# le.u16    font id?    all different small numbers
# le.u16                7f 00
# le.u16    bytes per glyph
# le.u16    version?    01 00 - starts at 0  02 00 03 00 - starts at 32
# le.u16    cell width
# le.u16    cell height


_DRHALO_SIG = b'AH'

@loaders.register(
    name='drhalo',
    magic=(_DRHALO_SIG,),
    patterns=('*.fon',),
)
def load_drhalo(instream, first_codepoint:int=None):
    """Load a Dr Halo / Dr Genius .FON bitmap font."""
    start = instream.read(16)
    if not start.startswith(_DRHALO_SIG):
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: incorrect signature '
            f'{start[:len(_DRHALO_SIG)]}.'
        )
    if first_codepoint is None:
        if start[2] == 0xc8:
            first_codepoint = 0
        else:
            first_codepoint = 0x20
    width = int(le.int16.read_from(instream))
    height = int(le.int16.read_from(instream))
    if not height or not width:
        raise UnsupportedError(
            'Not a Dr. Halo bitmap .FON: may be stroked format.'
        )
    font = load_bitmap(
        instream, width=width, height=height, first_codepoint=first_codepoint,
    )
    font = font.modify(source_format='Dr. Halo')
    font = font.label(char_from='ascii')
    return font
