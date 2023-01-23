"""
monobit.formats.windows.mz - DOS MZ executable header

`monobit.formats.windows` is copyright 2019--2023 Rob Hagemans
`mkwinfont` is copyright 2001 Simon Tatham. All rights reserved.
`dewinfont` is copyright 2001,2017 Simon Tatham. All rights reserved.

See `LICENSE.md` in this package's directory.
"""

from ...struct import little_endian as le
from ...binary import ceildiv, align


# MZ header:
#   http://www.delorie.com/djgpp/doc/exe/
#   https://wiki.osdev.org/MZ

_STUB_MSG = b'This is a Windows font file.\r\n'

# stub 16-bit DOS executable
_STUB_CODE = bytes((
    0xBA, 0x0E, 0x00, # mov dx,0xe
    0x0E,             # push cs
    0x1F,             # pop ds
    0xB4, 0x09,       # mov ah,0x9
    0xCD, 0x21,       # int 0x21
    0xB8, 0x01, 0x4C, # mov ax,0x4c01
    0xCD, 0x21        # int 0x21
))

# align on 16-byte (1<<4) boundaries
_ALIGN_SHIFT = 4

# DOS executable (MZ) header
_MZ_HEADER = le.Struct(
    # EXE signature, 'MZ' or 'ZM'
    magic='2s',
    # number of bytes in last 512-byte page of executable
    last_page_length='H',
    # total number of 512-byte pages in executable
    num_pages='H',
    num_relocations='H',
    header_size='H',
    min_allocation='H',
    max_allocation='H',
    initial_ss='H',
    initial_sp='H',
    checksum='H',
    initial_csip='L',
    relocation_table_offset='H',
    overlay_number='H',
    reserved_0='4s',
    behavior_bits='H',
    reserved_1='26s',
    # NE offset is at 0x3c
    ne_offset='L',
)

def _create_mz_stub():
    """Create a small MZ executable."""
    dos_stub_size = _MZ_HEADER.size + len(_STUB_CODE) + len(_STUB_MSG) + 1
    ne_offset = align(dos_stub_size, _ALIGN_SHIFT)
    mz_header = _MZ_HEADER(
        magic=b'MZ',
        last_page_length=dos_stub_size % 512,
        num_pages=ceildiv(dos_stub_size, 512),
        # 4-para header, where a paragraph == 16 bytes
        header_size=ceildiv(_MZ_HEADER.size, 16),
        # 16 extra para for stack
        min_allocation=0x10,
        # maximum extra paras: LOTS
        max_allocation=0xffff,
        initial_ss=0,
        initial_sp=0x100,
        # CS:IP = 0:0, start at beginning
        initial_csip=0,
        # we have no relocations, but if we did, they'd be right after this header
        relocation_table_offset=_MZ_HEADER.size,
        ne_offset=ne_offset,
    )
    return (bytes(mz_header) + _STUB_CODE + _STUB_MSG + b'$').ljust(ne_offset, b'\0')
