"""
monobit.cpi - DOS Codepage Information format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# CPI format documentation
# https://www.seasip.info/DOS/CPI/cpi.html
# https://www.win.tue.nl/~aeb/linux/kbd/font-formats-3.html

import os
import string
import logging

from ..base.binary import ceildiv, friendlystruct
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph

from .raw import parse_aligned


_ID_MS = b'FONT   '
_ID_NT = b'FONT.NT'
_ID_DR = b'DRFONT '

_CPI_HEADER = friendlystruct(
    'le',
    id0='byte',
    id='7s',
    reserved='8s',
    pnum='short',
    ptyp='byte',
    fih_offset='long',
)
_FONT_INFO_HEADER = friendlystruct(
    'le',
    num_codepages='short',
)
_CODEPAGE_ENTRY_HEADER = friendlystruct(
    'le',
    cpeh_size='short',
    next_cpeh_offset='long',
    device_type='short',
    device_name='8s',
    codepage='uint16',
    reserved='6s',
    cpih_offset='long',
)
# device types
_DT_SCREEN = 1
_DT_PRINTER = 2
# early printer devices that may erroneously have a device_type of 1
#_PRINTERS = ('4201', '4208', '5202', '1050')

# version for CP resource
_CP_FONT = 1
_CP_DRFONT = 2

_CODEPAGE_INFO_HEADER = friendlystruct(
    'le',
    version='short',
    num_fonts='short',
    size='short',
)
_PRINTER_FONT_HEADER = friendlystruct(
    'le',
    printer_type='short',
    escape_length='short',
)
_SCREEN_FONT_HEADER = friendlystruct(
    'le',
    height='byte',
    width='byte',
    yaspect='byte',
    xaspect='byte',
    num_chars='short',
)

# DRDOS Extended Font File Header
def drdos_ext_header(num_fonts_per_codepage=0):
    return friendlystruct(
        'le',
        num_fonts_per_codepage='byte',
        font_cellsize=friendlystruct.uint8 * num_fonts_per_codepage,
        dfd_offset=friendlystruct.uint32 * num_fonts_per_codepage,
    )
# DRFONT character index table
_CHARACTER_INDEX_TABLE = friendlystruct(
    'le',
    FontIndex=friendlystruct.int16 * 256,
)

# friendly format name
_FORMAT_NAME = {
    _ID_NT: 'Windows NT',
    _ID_DR: 'DR-DOS',
    _ID_MS: 'MS-DOS',
}


@loaders.register(
    'cpi',
    magic=(b'\xff'+_ID_MS, b'\xff'+_ID_NT, b'\x7f'+_ID_DR),
    name='CPI'
)
def load_cpi(instream, where=None):
    """Load character-cell fonts from DOS Codepage Information (.CPI) file."""
    data = instream.read()
    fonts = _parse_cpi(data)
    return fonts

@loaders.register('cp', name='Codepage')
def load_cp(instream, where=None):
    """Load character-cell fonts from Linux Keyboard Codepage (.CP) file."""
    data = instream.read()
    fonts, _ = _parse_cp(data, 0, standalone=True)
    return fonts



def _parse_cpi(data):
    """Parse CPI data."""
    cpi_header = _CPI_HEADER.from_bytes(data)
    if not (
            (cpi_header.id0 == 0xff and cpi_header.id == _ID_MS)
            or (cpi_header.id0 == 0xff and cpi_header.id == _ID_NT)
            or (cpi_header.id0 == 0x7f and cpi_header.id == _ID_DR)
        ):
        raise ValueError('Unrecognised CPI signature. Not a valid CPI file.')
    if cpi_header.id == _ID_DR:
        # read the extended DRFONT header - determine size first
        drdos_effh = drdos_ext_header().from_bytes(data, _CPI_HEADER.size)
        drdos_effh = drdos_ext_header(drdos_effh.num_fonts_per_codepage).from_bytes(
            data, _CPI_HEADER.size
        )
    else:
        drdos_effh = None
    fih = _FONT_INFO_HEADER.from_bytes(data, cpi_header.fih_offset)
    cpeh_offset = cpi_header.fih_offset + _FONT_INFO_HEADER.size
    # run through the linked list and parse fonts
    fonts = []
    for cp in range(fih.num_codepages):
        try:
            cp_fonts, cpeh_offset = _parse_cp(
                data, cpeh_offset, cpi_header.id, drdos_effh=drdos_effh
            )
        except ValueError as e:
            logging.error('Could not parse font in CPI file: %s', e)
        else:
            fonts += cp_fonts
    if cpeh_offset:
        notice = data[cpeh_offset:].decode('ascii', 'ignore')
        notice = '\n'.join(notice.splitlines())
        notice = ''.join(
            _c for _c in notice if _c in string.printable
        )
        fonts = [
            _font.set_properties(notice=notice.strip())
            for _font in fonts
        ]
    return fonts

def _parse_cp(data, cpeh_offset, header_id=_ID_MS, drdos_effh=None, standalone=False):
    """Parse a .CP codepage."""
    cpeh = _CODEPAGE_ENTRY_HEADER.from_bytes(data, cpeh_offset)
    if header_id == _ID_NT:
        # fix relative offsets in FONT.NT
        cpeh.cpih_offset += cpeh_offset
        cpeh.next_cpeh_offset += cpeh_offset
    if standalone:
        # on a standalone codepage (kbd .cp file), ignore the offset
        # CPIH follows immediately after CPEH
        cpeh.cpih_offset = cpeh_offset + _CODEPAGE_ENTRY_HEADER.size
    cpih = _CODEPAGE_INFO_HEADER.from_bytes(data, cpeh.cpih_offset)
    # offset to the first font header
    fh_offset = cpeh.cpih_offset + _CODEPAGE_INFO_HEADER.size
    # handle Toshiba fonts
    if cpih.version == 0:
        cpih.version = _CP_FONT
    # printer CPs have one font only
    if cpeh.device_type == _DT_PRINTER:
        cpih.num_fonts = 1
        # could we parse printer fonts? are they device specific?
        # if not, what are the dimensions?
        raise ValueError(
            'Printer codepages not supported - codepage {} device `{}`'.format(
                cpeh.codepage, cpeh.device_name
            )
        )
    else:
        fonts = []
        # char table offset for drfont
        if cpih.version == _CP_DRFONT:
            cit_offset = fh_offset + cpih.num_fonts * _SCREEN_FONT_HEADER.size
        for cp_index in range(cpih.num_fonts):
            fh = _SCREEN_FONT_HEADER.from_bytes(data, fh_offset)
            # extract font properties
            device = cpeh.device_name.strip().decode('ascii', 'replace')
            props = {
                'encoding': 'cp{}'.format(cpeh.codepage),
                'device': device,
                'source-format': 'CPI ({})'.format(_FORMAT_NAME[header_id]),
                'family': device,
            }
            # apparently never used
            if fh.xaspect or fh.yaspect:
                # not clear how this would be interpreted...
                props['cpi.xaspect'] = str(fh.xaspect)
                props['cpi.yaspect'] = str(fh.yaspect)
            # get the bitmap
            if cpih.version == _CP_FONT:
                # bitmaps follow font header
                bm_offset = fh_offset + _SCREEN_FONT_HEADER.size
                cells = parse_aligned(data, fh.width, fh.height, fh.num_chars, bm_offset)
                fh_offset = bm_offset + fh.num_chars * fh.height * ceildiv(fh.width, 8)
            else:
                # DRFONT bitmaps
                cells = []
                cit = _CHARACTER_INDEX_TABLE.from_bytes(data, cit_offset)
                for ord, fi in zip(range(fh.num_chars), cit.FontIndex):
                    bm_offs_char = (
                        fi * drdos_effh.font_cellsize[cp_index] + drdos_effh.dfd_offset[cp_index]
                    )
                    cells.append(Glyph.from_bytes(
                        data[bm_offs_char : bm_offs_char+drdos_effh.font_cellsize[cp_index]],
                        fh.width
                    ))
                fh_offset += _SCREEN_FONT_HEADER.size
            fonts.append(Font(cells, properties=props))
    return fonts, cpeh.next_cpeh_offset
