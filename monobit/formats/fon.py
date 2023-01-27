"""
monobit.formats.fon - Windows and OS/2 FON files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import io

from ..storage import loaders, savers
from ..streams import FileFormatError

from .windows.mz import MZ_HEADER
from .windows.ne import create_fon, read_ne, _NE_HEADER
from .windows.pe import read_pe
from .windows.fnt import (
    convert_win_fnt_resource, FNT_MAGIC_1, FNT_MAGIC_2, FNT_MAGIC_3
)
from .os2.lx import read_lx
from .os2.ne import read_os2_ne
from .os2.gpifont import convert_os2_font_resource, GPI_MAGIC
from .sfnt import load_sfnt, SFNT_MAGIC


@loaders.register(
    'fon', 'exe', 'dll',
    magic=(b'MZ', b'ZM', b'LX', b'NE', b'PE'),
    name='fon',
)
def load_fon(instream, where=None, all_type_ids:bool=False):
    """
    Load fonts from a Windows or OS/2 .FON container.

    all_type_ids: try to extract font from any resource, regardless of type id
    """
    mz_header = MZ_HEADER.read_from(instream)
    if mz_header.magic not in (b'MZ', b'ZM'):
        # apparently LX files don't always have an MZ stub
        # we allow stubless NE and PE too, in case they exist
        instream.seek(0)
        format = mz_header.magic
    else:
        header = _NE_HEADER.read_from(instream, mz_header.ne_offset)
        instream.seek(mz_header.ne_offset)
        format = header.magic
    if format == b'NE' and header.target_os == 1:
        logging.debug('File is in NE (16-bit OS/2) format')
        resources = read_os2_ne(instream, all_type_ids)
        format_name = 'OS/2 NE'
    elif format == b'LX':
        logging.debug('File is in LX (32-bit OS/2) format')
        resources = read_lx(instream, all_type_ids)
        format_name = 'OS/2 LX'
    elif format == b'NE':
        logging.debug('File is in NE (16-bit Windows) format')
        resources = read_ne(instream)
        format_name = 'Windows NE'
    elif format == b'PE':
        # PE magic should be padded by \0\0 but I'll believe it at this stage
        logging.debug('File is in PE (32-bit Windows) format')
        resources = read_pe(instream)
        format_name = 'Windows PE'
    else:
        raise FileFormatError(
            'Not a FON file: expected signature `NE`, `PE` or `LX`, '
            f'found `{format.decode("latin-1")}`'
        )
    fonts = []
    for resource in resources:
        try:
            magic = resource[:4]
            # PE files may have bitmap SFNTs embedded in them
            # be restrictive as FNT_MAGIC_1 and SFNT_MAGIC clash
            if magic == SFNT_MAGIC and header.magic == b'PE':
                bytesio = io.BytesIO(resource)
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


@savers.register('fon', name='fon')
def save_win_fon(fonts, outstream, where=None, version:int=2, vector:bool=False):
    """
    Save fonts to a Windows .FON container.

    version: Windows font format version (default 2)
    vector: output a vector font (if the input font has stroke paths defined; default False)
    """
    outstream.write(create_fon(fonts, version*0x100, vector))
