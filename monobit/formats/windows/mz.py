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
ALIGN_SHIFT = 4

# DOS executable (MZ) header
# 40h size of structure
MZ_HEADER = le.Struct(
    # 00 Magic number
    # EXE signature, 'MZ' or 'ZM'
    e_magic='2s',
    # 02 Bytes on last page of file
    # number of bytes in last 512-byte page of executable
    e_cblp='uint16',
    # 04 Pages in file
    # total number of 512-byte pages in executable
    e_cp='uint16',
    # 06 Relocations
    e_crclc='uint16',
    # 08 Size of header in paragraphs
    e_cparhdr='uint16',
    # 0A Minimum extra paragraphs needed
    e_minalloc='uint16',
    # 0C Maximum extra paragraphs needed
    e_maxalloc='uint16',
    # 0E Initial (relative) SS value
    e_ss='uint16',
    # 10 Initial SP value
    e_sp='uint16',
    # 12 Checksum
    e_csum='uint16',
    # 14 Initial IP value
    e_ip='uint16',
    # 16 Initial (relative) CS value
    e_cs='uint16',
    # 18 File address of relocation table
    e_lfarlc='uint16',
    # 1A Overlay number
    e_ovno='uint16',
    # 1C Reserved words
    e_res=le.uint16 * 0x0004,
    # 24 OEM identifier (for e_oeminfo)
    e_oemid='uint16',
    # 26 OEM information; e_oemid specific
    e_oeminfo='uint16',
    # 28 Reserved words
    e_res2=le.uint16 * 0x000A,
    # 3C File address of new exe header
    e_lfanew='uint32',
)

def create_mz_stub():
    """Create a small MZ executable."""
    dos_stub_size = MZ_HEADER.size + len(_STUB_CODE) + len(_STUB_MSG) + 1
    ne_offset = align(dos_stub_size, ALIGN_SHIFT)
    mz_header = MZ_HEADER(
        e_magic=b'MZ',
        e_cblp=dos_stub_size % 512,
        e_cp=ceildiv(dos_stub_size, 512),
        # 4-para header, where a paragraph == 16 bytes
        e_cparhdr=ceildiv(MZ_HEADER.size, 16),
        # 16 extra para for stack
        e_minalloc=0x10,
        # maximum extra paras: LOTS
        e_maxalloc=0xffff,
        e_ss=0,
        e_sp=0x100,
        # CS:IP = 0:0, start at beginning
        e_ip=0,
        e_cs=0,
        # we have no relocations
        # but if we did, they'd be right after this header
        e_lfarlc=MZ_HEADER.size,
        e_lfanew=ne_offset,
    )
    return (
        bytes(mz_header) + _STUB_CODE + _STUB_MSG + b'$'
    ).ljust(ne_offset, b'\0')
