"""
monobit.storage.formats.raw.optiks - OPTIKS PCR fonts

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap


###############################################################################
# OPTIKS PCR - near-raw format
# http://fileformats.archiveteam.org/wiki/PCR_font
# http://cd.textfiles.com/simtel/simtel20/MSDOS/GRAPHICS/OKF220.ZIP
# OKF220.ZIP → OKFONTS.ZIP → FONTS.DOC - Has an overview of the format.
# > I have added 11 bytes to the head of the file
# > so that OPTIKS can identify it as a font file. The header has
# > a recognition pattern, OPTIKS version number and the size of
# > the font file.


_PCR_HEADER = le.Struct(
    magic='7s',
    # maybe it's a be uint16 of the file size, followed by the same size as le
    # anyway same difference
    height='uint8',
    zero='uint8',
    bytesize='uint16',
)

@loaders.register(
    name='pcr',
    magic=(b'KPG\1\2\x20\1', b'KPG\1\1\x20\1'),
    patterns=('*.pcr',),
)
def load_pcr(instream):
    """Load an OPTIKS .PCR font."""
    header = _PCR_HEADER.read_from(instream)
    font = load_bitmap(instream, width=8, height=header.height, count=256)
    font = font.modify(source_format='Optiks PCR')
    return font
