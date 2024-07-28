"""
monobit.storage.formats.raw.plus3dos - +3DOS header

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single, ensure_charcell


###############################################################################
# raw file with +3DOS header
# https://area51.dev/sinclair/spectrum/3dos/fileheader/
# see also https://github.com/oldherl/psftools/blob/master/tools/zxflib.c


_PLUS3DOS_MAGIC = b'PLUS3DOS\x1a'
_PLUS3DOS_HEADER = le.Struct(
    signature='9s',
    # absorb \x1a in signature
    #eof='byte',
    issue='byte',
    version='byte',
    file_size='uint32',
    # +3 BASIC header
    file_type='byte',
    data_length='uint16',
    # > For File Type 3 - CODE, Param 1 is the load address. Param 2 is unused
    param_1='uint16',
    param_2='uint16',
    unused='byte',
    # end of BASIC header
    reserved=le.uint8 * 104,
    checksum='byte',
)


@loaders.register(
    name='plus3dos',
    magic=(_PLUS3DOS_MAGIC,),
)
def load_plus3dos(instream):
    """Load a 768-byte raw font with +3DOS header."""
    header = _PLUS3DOS_HEADER.read_from(instream)
    logging.debug(header)
    if header.signature != _PLUS3DOS_MAGIC:
        raise FileFormatError(
            f'Not a +3DOS file: incorrect signature {header.signature}.'
        )
    if header.file_type != 3 or header.data_length != 768:
        # file type 3 is CODE
        logging.warning(
            '+3DOS file may not be a font file: '
            'file type %d != 3, data length %d != 768',
            header.file_type, header.data_length
    )
    if sum(bytes(header)[:-1]) & 0xff != header.checksum:
        logging.warning('+3DOS checksum failed.')
    font = load_bitmap(instream, width=8, height=8, count=96, first_codepoint=32)
    font = font.modify(source_format='+3DOS')
    font = font.label(char_from='ascii')
    return font


@savers.register(linked=load_plus3dos)
def save_plus3dos(fonts, outstream):
    """Save a 768-byte raw font with +3DOS header."""
    font = ensure_single(fonts)
    header = _PLUS3DOS_HEADER(
        signature=_PLUS3DOS_MAGIC,
        issue=1,
        version=0,
        file_size=768 + _PLUS3DOS_HEADER.size,
        file_type=3,
        data_length=768,
        # following psftools in the choice for these:
        # load address
        param_1=0x3d00,
        unused=ord('f'),
    )
    header.checksum = sum(bytes(header)) & 0xff
    font = font.resample(
        # need explicit Char as to_label does surprising (in this context) things
        # with numeric strings like '1'
        chars=(Char(chr(_c)) for _c in range(32, 128)),
        missing=font.get_glyph(' '),
    )
    outstream.write(bytes(header))
    save_bitmap(outstream, font)
