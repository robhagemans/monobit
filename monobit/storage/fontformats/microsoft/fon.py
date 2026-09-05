"""
monobit.storage.fontformats.fon.fon - Windows and OS/2 FON files

(c) 2019--2026 Rob Hagemans
with code from `mkwinfont`, copyright 2001 Simon Tatham. All rights reserved.
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers
from monobit.storage import Stream
from monobit.base import FileFormatError, UnsupportedError

from monobit.storage.fontformats.sfnt import load_sfnt, SFNT_MAGIC
from monobit.storage.utils.limitations import ensure_levels

from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv, align

from .windows.ne import create_ne, read_ne, NE_HEADER
from .windows.pe import read_pe
from .windows.fnt import (
    convert_win_fnt_resource,
    FNT_MAGIC_1, FNT_MAGIC_2, FNT_MAGIC_3
)
from .os2.lx import read_lx
from .os2.ne import read_os2_ne
from .os2.gpifont import convert_os2_font_resource, GPI_MAGIC


@loaders.register(
    name='mzfon',
    magic=(b'MZ', b'LX', b'LE', b'NE', b'PE'),
    patterns=('*.fon', '*.exe', '*.dll'),
)
def load_mzfon(instream, all_type_ids:bool=False):
    """
    Load fonts from a Windows or OS/2 .FON container.

    all_type_ids: try to extract font from any resource, regardless of type id
    """
    mz_header = MZ_HEADER.read_from(instream)
    if mz_header.e_magic == b'MZ':
        header = NE_HEADER.read_from(instream, mz_header.e_lfanew)
        instream.seek(mz_header.e_lfanew)
        format = header.ne_magic
    elif mz_header.e_magic == b'ZM':
        raise FileFormatError('Big-endian MZ executables not supported')
    else:
        # apparently LX files don't always have an MZ stub
        # we allow stubless NE and PE too, in case they exist
        instream.seek(0)
        format = mz_header.e_magic
    if format == b'NE' and header.ne_exetyp == 1:
        logging.debug('File is in NE (16-bit OS/2) format')
        resources = read_os2_ne(instream, all_type_ids)
        format_name = 'OS/2 NE'
    elif format == b'LX':
        logging.debug('File is in LX (32-bit OS/2) format')
        resources = read_lx(instream, all_type_ids)
        format_name = 'OS/2 LX'
    elif format == b'LE':
        logging.debug('File is in LE (32-bit DOS/Windows) format')
        # apparently LE has the same structure as LX, at least for our tables.
        # there may not exist any with font resources in them...
        resources = read_lx(instream, all_type_ids)
        format_name = 'Windows LE'
    elif format == b'NE':
        logging.debug('File is in NE (16-bit DOS/Windows) format')
        resources = read_ne(instream, all_type_ids)
        format_name = 'Windows NE'
    elif format == b'PE':
        # PE magic should be padded by \0\0 but I'll believe it at this stage
        logging.debug('File is in PE (32-bit Windows) format')
        resources = read_pe(instream, all_type_ids)
        format_name = 'Windows PE'
    else:
        raise FileFormatError(
            'Not a FON file: expected signature `NE`, `PE`, `LE`, or `LX`, '
            f'found `{format.decode("latin-1")}`'
        )
    fonts = []
    for resource in resources:
        try:
            magic = resource[:4]
            # PE files may have bitmap SFNTs embedded in them
            # be restrictive as FNT_MAGIC_1 and SFNT_MAGIC clash
            if magic == SFNT_MAGIC and format == b'PE':
                with Stream.from_data(resource, mode='r') as bytesio:
                    fonts = load_sfnt(bytesio)
                fonts.extend(fonts)
            elif magic == GPI_MAGIC:
                font = convert_os2_font_resource(resource)
                fonts.append(font)
            elif magic[:2] in (FNT_MAGIC_1, FNT_MAGIC_2, FNT_MAGIC_3):
                font = convert_win_fnt_resource(resource)
                fonts.append(font)
            else:
                logging.warning(
                    'Resource format not recognised: signature `%s`', magic
                )
        except (FileFormatError, UnsupportedError) as e:
            logging.warning('Failed to convert font resource: %s', e)
    fonts = tuple(
        font.modify(source_format=f'[{format_name}] {font.source_format}')
        for font in fonts
    )
    return fonts


@savers.register(name='mzfon', patterns=('*.fon',))
def save_win_fon(fonts, outstream, version:int=2, vector:bool=False):
    """
    Save fonts to a Windows .FON container.

    version: Windows font format version (default 2)
    vector: output a vector font (if the input font has stroke paths defined; default False)
    """
    fonts = ensure_levels(fonts, 2)
    stubdata = create_mz_stub()
    outstream.write(
        stubdata +
        create_ne(fonts, len(stubdata), version*0x100, vector)
    )


###############################################################################
# DOS MZ executable header

_STUB_MSG = b'This is a Windows font file.\r\n'

# stub 16-bit DOS executable from `mkwinfont`
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
#   http://www.delorie.com/djgpp/doc/exe/
#   https://wiki.osdev.org/MZ
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
