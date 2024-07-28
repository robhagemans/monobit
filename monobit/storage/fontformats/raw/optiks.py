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
from monobit.storage.utils.limitations import ensure_single, ensure_charcell, make_contiguous


###############################################################################
# OPTIKS PCR - near-raw format
# http://fileformats.archiveteam.org/wiki/PCR_font
# http://cd.textfiles.com/simtel/simtel20/MSDOS/GRAPHICS/OKF220.ZIP
# OKF220.ZIP → OKFONTS.ZIP → FONTS.DOC - Has an overview of the format.
# > I have added 11 bytes to the head of the file
# > so that OPTIKS can identify it as a font file. The header has
# > a recognition pattern, OPTIKS version number and the size of
# > the font file.


_PCR_MAGIC_1 = b'KPG\1\1\x20\1'
_PCR_MAGIC_2 = b'KPG\1\2\x20\1'
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
    magic=(_PCR_MAGIC_2, _PCR_MAGIC_1),
    patterns=('*.pcr',),
)
def load_pcr(instream):
    """Load an OPTIKS .PCR font."""
    header = _PCR_HEADER.read_from(instream)
    font = load_bitmap(instream, width=8, height=header.height, count=256)
    font = font.modify(source_format='Optiks PCR')
    return font


@savers.register(linked=load_pcr)
def save_pcr(fonts, outstream):
    """Save an OPTIKS .PCR font."""
    font = ensure_single(fonts)
    font = ensure_charcell(font)
    if font.cell_size.x != 8:
        raise FileFormatError(
            'This format only supports 8xN character-cell fonts.'
        )
    font = make_contiguous(font, full_range=range(256), missing='space')
    header = _PCR_HEADER(
        magic=_PCR_MAGIC_2,
        height=font.cell_size.y,
        bytesize=font.cell_size.y * 0x100,
    )
    outstream.write(bytes(header))
    save_bitmap(outstream, font)
