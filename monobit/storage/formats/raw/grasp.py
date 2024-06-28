"""
monobit.storage.formats.raw.grasp - GRASP / PCPaint character-cell "old format"

(c) 2022--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph, Raster
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv
from .raw import load_bitmap


###############################################################################
# PCPaint / GRASP original format. Not used by FONTRIX or ChiWriter.
# suffix .SET or .FNT
#
# http://fileformats.archiveteam.org/wiki/GRASP_font
# http://www.textfiles.com/programming/FORMATS/glformat.txt
#
# +-- Font Header
# | length    (word)    length of the entire font file
# | size      (byte)    number of glyphs in the font file
# | first     (byte)    byte value represented by the first glyph
# | width     (byte)    width of each glyph in pixels
# | height    (byte)    height of each glyph in pixels
# | glyphsize (byte)    number of bytes to encode each glyph
# +-- Glyph Data

_GRASP_HEADER = le.Struct(
    filesize='uint16',
    count='uint8',
    first='uint8',
    width='uint8',
    height='uint8',
    glyphsize='uint8',
)


@loaders.register(
    name='grasp',
    patterns=(
        '*.set', '*.fnt',
    ),
)
def load_grasp_old(instream):
    """
    Load a GRASP/PCPaint character-cell "old format" font.
    This is not the FONTRIX-based proportional "new format".
    """
    header = _GRASP_HEADER.read_from(instream)
    logging.debug('GRASP old-format header: %s', header)
    if header.filesize & 0xF in (0x10, 0x11):
        # 7-byte header, usually binary-rounded character cells & counts
        # so first byte for old format is usualy 0x07 or 0x87
        logging.warning(
            'First byte consistent with new-format GRASP font.'
        )
    if (0 in (header.count, header.glyphsize, header.width, header.height)):
        raise FileFormatError('Bad geometry for old-format GRASP font.')
    font = load_bitmap(
        instream,
        width=header.width, height=header.height,
        # note that often glyphsize != ceildiv(height*width, 8)
        strike_bytes=header.glyphsize // header.height,
        count=header.count,
        first_codepoint=header.first,
    )
    font = font.modify(source_format='Old-format GRASP font')
    return font
