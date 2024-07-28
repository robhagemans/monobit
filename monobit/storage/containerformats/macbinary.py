"""
monobit.storage.containers.macbinary - MacBinary containers

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be
from monobit.base.binary import align

from ..streams import Stream
from ..magic import FileFormatError, Magic
from ..base import containers
from ..containers import FlatFilterContainer


##############################################################################
# MacBinary container
# v1: https://www.cryer.co.uk/file-types/b/bin_/original_mac_binary_format_proposal.htm
# v2: https://files.stairways.com/other/macbinaryii-standard-info.txt
# v2 defines additional fields inside an area zeroed in v1. we can ignore them.

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


@containers.register(
    name='macbin',
    magic=(
        # FFILDMOV is a maybe
        Magic.offset(65) + b'FFILDMOV',
    ),
)
class MacBinary(FlatFilterContainer):
    """MacBinary container."""

    def decode(self, name):
        """
        Decode data and resource fork from MacBinary container.
        """
        return super().decode(name)

    def encode(self, name):
        """
        Writing to MacBinary is not supported.
        """
        raise ValueError(
            'Writing to MacBinary is not supported.'
        )

    def decode_all(self, stream):
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
        if name:
            return {
                f'data/{name}': data_fork,
                f'rsrc/{name}': rsrc_fork,
            }
        else:
            return {
                f'data': data_fork,
                f'rsrc': rsrc_fork,
            }
