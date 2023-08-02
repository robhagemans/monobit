"""
monobit.containers.mac - Classic Mac OS resource & data fork containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools

from ..streams import Stream
from ..storage import loaders, load_stream
from ..magic import FileFormatError, Magic


@loaders.register(
    name='binhex',
    magic=(
        b'(This file must be converted',
        b'\r(This file must be converted',
    ),
    patterns=('*.hqx',),
    wrapper=True,
)
def load_binhex(instream, format='', **kwargs):
    """BinHex 4.0 loader."""
    return _load_macforks(_parse_binhex, instream, format, **kwargs)


@loaders.register(
    name='macbin',
    magic=(
        # FFILDMOV is a maybe
        Magic.offset(65) + b'FFILDMOV',
    ),
    wrapper=True,
)
def load_macbin(instream, format='', **kwargs):
    """MacBinary loader."""
    return _load_macforks(_parse_macbinary, instream, format, **kwargs)


_APPLESINGLE_MAGIC = 0x00051600
_APPLEDOUBLE_MAGIC = 0x00051607


@loaders.register(
    name='apple1',
    magic=(
        _APPLESINGLE_MAGIC.to_bytes(4, 'big'),
    ),
    patterns=('*.as',),
    wrapper=True,
)
def load_single(instream, format='', **kwargs):
    """AppleSingle loader."""
    return _load_macforks(_parse_apple_container, instream, format, **kwargs)


@loaders.register(
    name='apple2',
    magic=(
        _APPLEDOUBLE_MAGIC.to_bytes(4, 'big'),
    ),
    # .adf, .rsrc - per http://fileformats.archiveteam.org/wiki/AppleDouble
    # ._<name> is OS X representation
    patterns=('*.adf', '*.rsrc', '._*'),
    wrapper=True,
)
def load_double(instream, format='', **kwargs):
    """AppleDouble loader."""
    return _load_macforks(_parse_apple_container, instream, format, **kwargs)


def _load_macforks(parser, instream, format, **kwargs):
    """Resource and data fork loader."""
    name, data, rsrc = parser(instream)
    fonts = []
    for fork in rsrc, data:
        if fork:
            stream = Stream.from_data(fork, mode='r', name=f'{name}')
            try:
                forkfonts = load_stream(stream, format=format, **kwargs)
                fonts.extend(forkfonts)
            except FileFormatError as e:
                logging.debug(e)
                pass
    return fonts


###############################################################################
# BinHex 4.0 container
# https://files.stairways.com/other/binhex-40-specs-info.txt

from binascii import crc_hqx
from itertools import zip_longest

from ..struct import big_endian as be


_BINHEX_CODES = (
    '''!"#$%&'()*+,-012345689@ABCDEFGHIJKLMNPQRSTUVXYZ[`abcdefhijklmpqr'''
)
_BINHEX_CODEDICT = {_BINHEX_CODES[_i]: _i for _i in range(64)}

_BINHEX_HEADER = be.Struct(
    type='4s',
    auth='4s',
    flag='uint16',
    dlen='uint32',
    rlen='uint32',
)
_CRC = be.Struct(
    crc='uint16',
)

def _parse_binhex(stream):
    """Parse a BinHex 4.0 file."""
    front, binhex, *back = stream.text.read().split(':')
    if 'BinHex 4.0' not in front:
        logging.warning('No BinHex 4.0 signature found.')
    back = ''.join(back).strip()
    if back:
        logging.warning('Additional data found after BinHex section: %r', back)
    binhex = ''.join(binhex.split('\n'))
    # decode into 6-bit ints
    data = (_BINHEX_CODEDICT[_c] for _c in binhex)
    # convert to bit sequence
    bits = ''.join(bin(_d)[2:].zfill(6) for _d in data)
    # group into chunks of 8
    args = [iter(bits)] * 8
    octets = (''.join(_t) for _t in zip_longest(*args, fillvalue='0'))
    # convert to bytes
    bytestr = bytes(int(_s, 2) for _s in octets)
    # find run-length encoding marker
    chunks = bytestr.split(b'\x90')
    out = bytearray(chunks[0])
    for c in chunks[1:]:
        if c:
            # run-length byte
            repeat = c[0]
        else:
            # ...\x90\x90... -> ...', '', '...
            repeat = 0x90
        if not repeat:
            # zero-byte is placeholder for just 0x90
            out += b'\x90'
        else:
            # apply RLE. the last byte counts as the first of the run
            out += out[-1:] * (repeat-1)
        out += c[1:]
    # decode header
    length = out[0]
    name = bytes(out[1:1+length]).decode('mac-roman')
    if out[1+length] != 0:
        logging.warning('No null byte after name')
    header = _BINHEX_HEADER.from_bytes(out, 2+length)
    logging.debug(header)
    offset = 2 + length + _BINHEX_HEADER.size
    crc_header = out[:offset]
    hc = _CRC.from_bytes(out, offset)
    offset += _CRC.size
    if crc_hqx(crc_header, 0) != hc.crc:
        logging.error('CRC fault in header')
    data = out[offset:offset+header.dlen]
    offset += header.dlen
    dc = _CRC.from_bytes(out, offset)
    offset += _CRC.size
    rsrc = out[offset:offset+header.rlen]
    offset += header.rlen
    rc = _CRC.from_bytes(out, offset)
    if crc_hqx(data, 0) != dc.crc:
        logging.error('CRC fault in data fork')
    if crc_hqx(rsrc, 0) != rc.crc:
        logging.error('CRC fault in resource fork')
    return name, data, rsrc


##############################################################################
# MacBinary container
# v1: https://www.cryer.co.uk/file-types/b/bin_/original_mac_binary_format_proposal.htm
# v2: https://files.stairways.com/other/macbinaryii-standard-info.txt
# v2 defines additional fields inside an area zeroed in v1. we can ignore them.

from ..binary import align


_MACBINARY_HEADER = be.Struct(
    # Offset 000-Byte, old version number, must be kept at zero for compatibility
    old_version='byte',
    # Offset 001-Byte, Length of filename (must be in the range 1-63)
    filename_length='byte',
    # Offset 002-1 to 63 chars, filename (only "length" bytes are significant).
    filename='63s',
    # Offset 065-Long Word, file type (normally expressed as four characters)
    file_type='4s',
    # Offset 069-Long Word, file creator (normally expressed as four characters)
    file_creator='4s',
    # Offset 073-Byte, original Finder flags
    original_finder_flags='byte',
    # Offset 074-Byte, zero fill, must be zero for compatibility
    zero_0='byte',
    # Offset 075-Word, file's vertical position within its window.
    window_vert='word',
    # Offset 077-Word, file's horizontal position within its window.
    window_horiz='word',
    # Offset 079-Word, file's window or folder ID.
    window_id='word',
    # Offset 081-Byte, "Protected" flag (in low order bit).
    protected='byte',
    # Offset 082-Byte, zero fill, must be zero for compatibility
    zero_1='byte',
    # Offset 083-Long Word, Data Fork length (bytes, zero if no Data Fork).
    data_length='dword',
    # Offset 087-Long Word, Resource Fork length (bytes, zero if no R.F.).
    rsrc_length='dword',
    # Offset 091-Long Word, File's creation date
    creation_date='dword',
    # Offset 095-Long Word, File's "last modified" date.
    last_modified_date='dword',
    # Offset 099-Word, length of Get Info comment to be sent after the resource
    # fork (if implemented, see below).
    get_info_length='word',
    # *Offset 101-Byte, Finder Flags, bits 0-7. (Bits 8-15 are already in byte 73)
    finder_flags='byte',
    # *Offset 116-Long Word, Length of total files when packed files are unpacked.
    packed_length='dword',
    # *Offset 120-Word, Length of a secondary header.  If this is non-zero,
    #              Skip this many bytes (rounded up to the next multiple of 128)
    #              This is for future expansion only, when sending files with
    #              MacBinary, this word should be zero.
    second_header_length='dword',
    # *Offset 122-Byte, Version number of Macbinary II that the uploading program
    # is written for (the version begins at 129)
    writer_version='byte',
    # *Offset 123-Byte, Minimum MacBinary II version needed to read this file
    # (start this value at 129 129)
    reader_version='byte',
    # *Offset 124-Word, CRC of previous 124 bytes
    crc='word',
    # from v1 desc:
    # > 126 2 Reserved for computer type and OS ID
    # > (this field will be zero for the current Macintosh).
    reserved='word',
    # *This is newly defined for MacBinary II.
)

def _parse_macbinary(stream):
    """Parse a MacBinary file."""
    data = stream.read()
    header = _MACBINARY_HEADER.from_bytes(data)
    ofs = 128
    if header.old_version != 0:
        raise FileFormatError(
            'Not a MacBinary file: incorrect version field'
            f' ({header.old_version}).'
        )
    if header.writer_version > 128:
        ofs += align(header.second_header_length, 7)
    data_fork = data[ofs:ofs+header.data_length]
    ofs += align(header.data_length, 7)
    rsrc_fork = data[ofs:ofs+header.rsrc_length]
    name = header.filename.decode('mac-roman').strip()
    return name, data_fork, rsrc_fork


##############################################################################
# AppleSingle/AppleDouble container
# v1: see https://web.archive.org/web/20160304101440/http://kaiser-edv.de/documents/Applesingle_AppleDouble_v1.html
# v2: https://web.archive.org/web/20160303215152/http://kaiser-edv.de/documents/AppleSingle_AppleDouble.pdf
# the difference between v1 and v2 affects the file info sections
# not the resource fork which is what we care about


_APPLE_HEADER = be.Struct(
    magic='uint32',
    version='uint32',
    home_fs='16s',
    number_entities='uint16',
)
_APPLE_ENTRY = be.Struct(
    entry_id='uint32',
    offset='uint32',
    length='uint32',
)

# Entry IDs
_ID_DATA = 1
_ID_RESOURCE = 2
_ID_NAME = 3

_APPLE_ENTRY_TYPES = {
    1: 'data fork',
    2: 'resource fork',
    3: 'real name',
    4: 'comment',
    5: 'icon, b&w',
    6: 'icon, color',
    7: 'file info', # v1 only
    8: 'file dates info', # v2
    9: 'finder info',
    # the following are all v2
    10: 'macintosh file info',
    11: 'prodos file info',
    12: 'ms-dos file info',
    13: 'short name',
    14: 'afp file info',
    15: 'directory id',
}


def _parse_apple_container(stream):
    """Parse an AppleSingle or AppleDouble file."""
    data = stream.read()
    header = _APPLE_HEADER.from_bytes(data)
    if header.magic == _APPLESINGLE_MAGIC:
        container = 'AppleSingle'
    elif header.magic == _APPLEDOUBLE_MAGIC:
        container = 'AppleDouble'
    else:
        raise FileFormatError('Not an AppleSingle or AppleDouble file.')
    entry_array = _APPLE_ENTRY.array(header.number_entities)
    entries = entry_array.from_bytes(data, _APPLE_HEADER.size)
    name, data_fork, rsrc_fork = '', b'', b''
    for i, entry in enumerate(entries):
        entry_type = _APPLE_ENTRY_TYPES.get(entry.entry_id, 'unknown')
        logging.debug(
            '%s container: entry #%d, %s [%d]',
            container, i, entry_type, entry.entry_id
        )
        if entry.entry_id == _ID_RESOURCE:
            rsrc_fork = data[entry.offset:entry.offset+entry.length]
        if entry.entry_id == _ID_DATA:
            data_fork = data[entry.offset:entry.offset+entry.length]
        if entry.entry_id == _ID_NAME:
            name = data[entry.offset:entry.offset+entry.length]
            name = name.decode('mac-roman')
    return name, data_fork, rsrc_fork
