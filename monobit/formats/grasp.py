"""
monobit.formats.grasp - GRASP GL .SET font files

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from .. import struct
from ..struct import little_endian as le
from .raw import load_binary


###############################################################################
# new format

# http://fileformats.archiveteam.org/wiki/GRASP_font
_GRASP_NEW_HEADER = le.Struct(
    unknown0='uint8',
    name='13s',
    unknown1=struct.uint8*2,
    count='uint8',
    unknown2=struct.uint8*2,
    width='uint8',
    height='uint8',
    bytewidth='uint8',
    unknown3=struct.uint8*3,
    filesize='uint16',
    unknown4=struct.uint8*32,
    # Unknown (not a pointer to the bitmap for the space character, logical as that would be)
    unknown5='uint16',
    offsets=struct.uint16 * 94,
    # Unknown; possibly the width of a space character
    # however one sample file has 0 here so maybe not
    space_width='uint8',
    widths=struct.uint8 * 94,
)

@loaders.register('set', name='grasp')
def load_grasp(instream, where=None):
    """Load a GRASP font (oriiginal format)."""
    header = _GRASP_NEW_HEADER.read_from(instream)
    #` we use the name field to detect the new format
    name, *_ = header.name.split(b'\0')
    logging.debug('Filename field %r', name)
    if any(_c not in range(32, 128) for _c in name):
        #  doesn't look like a filename
        instream.seek(0)
        return _load_grasp_old(instream)
    logging.debug(header)
    instream.seek(0)
    data = instream.read()
    glyphs = [Glyph.blank(
        width=header.space_width, height=header.height, codepoint=0x20,
    )]
    glyphs.extend(
        Glyph.from_bytes(
            data[_off:_off+header.bytewidth*header.height],
            width=_wid, stride=8*header.bytewidth,
            codepoint=_cp,
        )
        for _cp, (_off, _wid) in enumerate(
            zip(header.offsets, header.widths),
            start=0x21
        )
    )
    font = Font(glyphs, source_format='GRASP .set (new)')
    return font


###############################################################################
# original format:
#
# +-- Font Header
# | length	(word)		length of the entire font file
# | size		(byte)		number of glyphs in the font file
# | first		(byte)		byte value represented by the first glyph
# | width		(byte)		width of each glyph in pixels
# | height	(byte)		height of each glyph in pixels
# | glyphsize	(byte)		number of bytes to encode each glyph
# +-- Glyph Data

_GRASP_HEADER = le.Struct(
    filesize='uint16',
    count='uint8',
    first='uint8',
    width='uint8',
    height='uint8',
    glyphsize='uint8',
)

def _load_grasp_old(instream, where=None):
    """Load a GRASP font (original format)."""
    header = _GRASP_HEADER.read_from(instream)
    font = load_binary(
        instream, where,
        cell=(header.width, header.height),
        strike_bytes=header.glyphsize // header.height,
        count=header.count,
        first_codepoint=header.first,
    )
    font = font.modify(source_format='GRASP .set (original)')
    return font
