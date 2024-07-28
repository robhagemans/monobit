"""
monobit.storage.formats.raw.drhalo - Dr. Halo / Dr. Genius font files

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap


###############################################################################
# Dr. Halo / Dr. Genius F*X*.FON
# this covers the bitmap fonts only
# most fonts included with Dr Halo are vector fonts
# for which I have not yet deciphered the encoding


_DRHALO_SIG = b'AH'

@loaders.register(
    name='drhalo',
    magic=(_DRHALO_SIG,),
    patterns=('*.fon',),
)
def load_drhalo(instream, first_codepoint:int=0):
    """Load a Dr Halo / Dr Genius .FON bitmap font."""
    start = instream.read(16)
    if not start.startswith(_DRHALO_SIG):
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: incorrect signature '
            f'{start[:len(_DRHALO_SIG)]}.'
        )
    width = int(le.int16.read_from(instream))
    height = int(le.int16.read_from(instream))
    if not height or not width:
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: may be stroked format.'
        )
    font = load_bitmap(
        instream, width=width, height=height, first_codepoint=first_codepoint,
    )
    font = font.modify(source_format='Dr. Halo')
    return font
