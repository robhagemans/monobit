"""
monobit.fzx - FZX format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import ctypes

from ..binary import ceildiv
from ..struct import Props, bitfield, little_endian as le
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph


# https://faqwiki.zxnet.co.uk/wiki/FZX_format

# > height - vertical gap between baselines in pixels
# > This is the number of pixels to move down after a carriage return.
# >
# > tracking - horizontal gap between characters in pixels
# > Character definitions should not include any white space and this value should normally
# > be a positive number. It may be zero for script style fonts where characters run together.
# >
# > lastchar - the ASCII code of the last definition in the font
# > All characters up to and including this character must have an entry in the list of
# > definitions although the entry can be blank.

_FZX_HEADER = le.Struct(
    height='uint8',
    tracking='int8',
    lastchar='uint8',
)

# > offset - word containing the offset to the character definition
# > (plus any kern in the high two bits) This is calculated from the start of the table and
# > stored as an offset rather than an absolute address to make the font relocatable.
# > The kern is the left shift towards the previous character and can be between 1 and 3 pixels.
# > The byte containing the offset can be calculated as follows:
# >   offset + 16384 × kern
# >
# > shift - nibble containing the amount of leading for the character (0-15)
# > This is the number of vertical pixels to skip before drawing the character. When more than
# > 15 pixels of white space are required the additional white space must be added to the character
# > definition.
# >
# > width - nibble containing the width of the character (1-16)
# > The width of the character definition in pixels. The value stores is one less than the required
# > value.
# > The byte containing the leading and width can be calculated as follows:
# >   16 × shift + width - 1

_CHAR_ENTRY = le.Struct(
    # kern, shift are the high byte
    # but in ctypes, little endian ordering also seems to hold for bit fields
    offset=bitfield('uint16', 14),
    kern=bitfield('uint16', 2),
    # this is actually width-1
    width=bitfield('uint8', 4),
    shift=bitfield('uint8', 4),
)


@loaders.register('fzx', name='FZX')
def load_fzx(instream, where=None):
    """Load font from ZX Spectrum .FZX file."""
    data = instream.read()
    header = _FZX_HEADER.from_bytes(data)
    logging.info('FZX properties:')
    for name, value in vars(header).items():
        logging.info('    %s: %s', name, value)
    n_chars = header.lastchar - 32 + 1
    # read glyph table
    char_table = _CHAR_ENTRY.array(n_chars).from_bytes(data, _FZX_HEADER.size)
    # offsets seem to be given relative to the entry in the char table; convert to absolute offsets
    offsets = [
        _FZX_HEADER.size + _CHAR_ENTRY.size * _i + _entry.offset
        for _i, _entry in enumerate(char_table)
    ] + [None]
    glyph_bytes = [
        data[_offs:_next]
        for _offs, _next in zip(offsets[:-1], offsets[1:])
    ]
    # construct glyphs
    glyphs = [
        Glyph.from_bytes(_glyph, _entry.width+1)
        for _glyph, _entry in zip(glyph_bytes, char_table)
    ]
    # set glyph properties
    glyphs = [
        _glyph.modify(
            offset=(-_entry.kern, header.height-_glyph.height-_entry.shift),
            # +1 because _entry.width is actually width-1
            tracking=(_entry.width+1)-_glyph.width
        )
        for _glyph, _entry in zip(glyphs, char_table)
    ]
    # set font properties
    leading = min(_entry.shift for _entry in char_table)
    properties = Props(
        leading=leading,
        # we don't know ascent & descent but we can't set line-height directly
        ascent=header.height-leading,
        descent=0,
        tracking=header.tracking,
        # TODO check this - memory-mapped or chr-mapped?
        encoding='zx-spectrum',
    )
    glyphs = [
        _glyph.set_annotations(codepoint=(_index+32,))
        for _index, _glyph in enumerate(glyphs)
    ]
    logging.info('yaff properties:')
    for line in str(properties).splitlines():
        logging.info('    ' + line)
    return Font(glyphs, properties=vars(properties))
