"""
monobit.storage.formats.raw.sixtyfourc - .64C files

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single


###############################################################################
# 64C - two unknown bytes plus 8x8 raw in c64 order (upper- or lowercase)
# I haven't found a sepcification
# large collection of sample files at https://home-2002.code-cop.org/c64/index.html#char

@loaders.register(
    name='64c',
    patterns=('*.64c',),
    # maybe-magic b'\0\x38', b'\0\x20' most comon, but many others occur
)
def load_64c(instream, charset:str='upper'):
    """
    Load a 64C font.

    charset: 'upper' for c64 uppercase & graphical, 'lower' for lowercase & uppercase, '' for not specified
    """
    # the second byte is likely a flag, the first is almost always null
    null = instream.read(1)
    unknown_flags = instream.read(1)
    if null != b'\0':
        logging.warning(f'Non-null first byte %s.', null)
    font = load_bitmap(
        instream,
        width=8, height=8,
    )
    if charset == 'upper':
        font = font.label(char_from='c64')
    elif charset == 'lower':
        font = font.label(char_from='c64-alternate')
    font = font.modify(source_format='64c')
    return font


@savers.register(linked=load_64c)
def save_64c(fonts, outstream):
    """Save a 64C font."""
    font = ensure_single(fonts)
    # not an actual magic sequence. we also see \0\x20 \0\x30 \0\x48 \0\xc8
    outstream.write(b'\x00\x38')
    save_bitmap(outstream, font)
