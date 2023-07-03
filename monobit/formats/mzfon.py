"""
monobit.formats.mzfon - Windows and OS/2 FON files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from ..streams import Stream
from ..magic import FileFormatError

from .windows.mz import MZ_HEADER, create_mz_stub
from .windows.ne import create_ne, read_ne, NE_HEADER
from .windows.pe import read_pe
from .windows.fnt import (
    convert_win_fnt_resource,
    FNT_MAGIC_1, FNT_MAGIC_2, FNT_MAGIC_3
)
from .os2.lx import read_lx
from .os2.ne import read_os2_ne
from .os2.gpifont import convert_os2_font_resource, GPI_MAGIC
from .sfnt import load_sfnt, SFNT_MAGIC


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
                bytesio = Stream.from_data(resource, mode='r')
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
        except FileFormatError as e:
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
    stubdata = create_mz_stub()
    outstream.write(
        stubdata +
        create_ne(fonts, len(stubdata), version*0x100, vector)
    )
