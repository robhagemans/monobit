"""
monobit.formats.cpi - DOS Codepage Information format

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import string
import logging
from io import BytesIO

from ..binary import ceildiv
from ..struct import little_endian as le
from .. import struct
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..properties import Props

from .raw import load_bitmap
from .gdos import _subset_storable
from .windows import _make_contiguous, _normalise_metrics


_ID_MS = b'FONT   '
_ID_NT = b'FONT.NT'
_ID_DR = b'DRFONT '


@loaders.register(
    'cpi',
    magic=(b'\xff'+_ID_MS, b'\xff'+_ID_NT, b'\x7f'+_ID_DR),
    name='cpi'
)
def load_cpi(instream, where=None):
    """Load character-cell fonts from DOS Codepage Information (.CPI) file."""
    data = instream.read()
    fonts = _parse_cpi(data)
    return fonts

@loaders.register('cp', name='kbd-cp')
def load_cp(instream, where=None):
    """Load character-cell fonts from Linux Keyboard Codepage (.CP) file."""
    data = instream.read()
    fonts, _ = _parse_cp(data, 0, standalone=True)
    return fonts


@savers.register(linked=load_cp)
def save_cp(fonts, outstream, where=None):
    """Save character-cell fonts to Linux Keyboard Codepage (.CP) file."""
    fonts = _make_fit(fonts)
    cpdata = _convert_to_cp(fonts)
    _write_cp(outstream, cpdata)


###############################################################################
# CPI reader
# https://www.seasip.info/DOS/CPI/cpi.html
# https://www.win.tue.nl/~aeb/linux/kbd/font-formats-3.html


_CPI_HEADER = le.Struct(
    id0='byte',
    id='7s',
    reserved='8s',
    pnum='short',
    ptyp='byte',
    fih_offset='long',
)
_FONT_INFO_HEADER = le.Struct(
    num_codepages='short',
)

# DRDOS Extended Font File Header
def drdos_ext_header(num_fonts_per_codepage=0):
    return le.Struct(
        num_fonts_per_codepage='byte',
        font_cellsize=struct.uint8 * num_fonts_per_codepage,
        dfd_offset=struct.uint32 * num_fonts_per_codepage,
    )

# friendly format name
_FORMAT_NAME = {
    _ID_NT: 'Windows NT',
    _ID_DR: 'DR-DOS',
    _ID_MS: 'MS-DOS',
}


def _parse_cpi(data):
    """Parse CPI data."""
    cpi_header = _CPI_HEADER.from_bytes(data)
    if not (
            (cpi_header.id0 == 0xff and cpi_header.id == _ID_MS)
            or (cpi_header.id0 == 0xff and cpi_header.id == _ID_NT)
            or (cpi_header.id0 == 0x7f and cpi_header.id == _ID_DR)
        ):
        raise FileFormatError(
            f'Not a valid CPI file: unrecognised CPI signature 0x{cpi_header.id0:02X} "{cpi_header.id}".'
        )
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
        except FileFormatError as e:
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
            _font.modify(notice=notice.strip())
            for _font in fonts
        ]
    return fonts


###############################################################################
# CP reader

_CODEPAGE_ENTRY_HEADER = le.Struct(
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

_CODEPAGE_INFO_HEADER = le.Struct(
    version='short',
    num_fonts='short',
    size='short',
)
_PRINTER_FONT_HEADER = le.Struct(
    printer_type='short',
    escape_length='short',
)
_SCREEN_FONT_HEADER = le.Struct(
    height='byte',
    width='byte',
    yaspect='byte',
    xaspect='byte',
    num_chars='short',
)
# DRFONT character index table
_CHARACTER_INDEX_TABLE = le.Struct(
    FontIndex=struct.int16 * 256,
)

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
    # https://www.seasip.info/DOS/CPI/cpi.html
    # > LCD.CPI from Toshiba MS-DOS 3.30 sets this field to 0, which should be treated as 1.
    if cpih.version == 0:
        cpih.version = _CP_FONT
    # printer CPs have one font only
    if cpeh.device_type == _DT_PRINTER:
        cpih.num_fonts = 1
        # could we parse printer fonts? are they device specific?
        # if not, what are the dimensions?
        raise FileFormatError(
            'Printer CPI codepages not supported: '
            f'codepage {cpeh.codepage}, device `{cpeh.device_name}`'
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
            props = dict(
                encoding=f'cp{cpeh.codepage}',
                device=device,
                source_format=f'CPI ({_FORMAT_NAME[header_id]})',
            )
            logging.debug(
                f'Reading {fh.width}x{fh.height} font '
                f'for codepage {cpeh.codepage} '
                f'in {_FORMAT_NAME[header_id]} format.'
            )
            # apparently never used
            if fh.xaspect or fh.yaspect:
                # not clear how this would be interpreted...
                props['cpi'] = f'xaspect={fh.xaspect} yaspect={fh.yaspect}'
            # get the bitmap
            if cpih.version == _CP_FONT:
                # bitmaps follow font header
                bm_offset = fh_offset + _SCREEN_FONT_HEADER.size
                bytesz = fh.height * ceildiv(fh.width, 8)
                fh_offset = bm_offset + fh.num_chars * bytesz
                cells = tuple(
                    Glyph.from_bytes(data[_offs : _offs+bytesz], fh.width)
                    for _offs in range(bm_offset, fh_offset, bytesz)
                )
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
            # add codepoints and character labels
            cells = tuple(
                _g.modify(codepoint=_cp)
                for _cp, _g in enumerate(cells)
            )
            font = Font(cells, **props)
            font = font.label()
            fonts.append(font)
    return fonts, cpeh.next_cpeh_offset


###############################################################################
# CP writer

# storable code points
_RANGE = range(256)

def _make_fit(fonts):
    """Select only the fonts that fit."""
    fonts = (_make_one_fit(_font) for _font in fonts)
    fonts = tuple(_font for _font in fonts if _font)
    if not fonts:
        raise FileFormatError('No storable fonts provided')
    return fonts

def _make_one_fit(font):
    """Check if font fits in format and reshape as necessary."""
    if font.cell_size.x != 8:
        logging.warning(
            'CP format can only store 8xN character-cell fonts.'
        )
        return None
    if not font.encoding.startswith('cp'):
        logging.warning(
            'CP fonts must have encoding set to a numbered codepage'
        )
        return None
    # ensure codepoint values are set, if possible
    font = font.label(codepoint_from=font.encoding)
    # take only the glyphs that will fit
    font = _subset_storable(font, _RANGE)
    font, _ = _normalise_metrics(font)
    font = _fill_contiguous(font, _RANGE, Glyph.blank(*font.cell_size))
    return font


def _fill_contiguous(font, full_range, filler):
    """Get contiguous range, fill gaps with empties."""
    glyphs = tuple(
        font.get_glyph(codepoint=_cp, missing=filler).modify(codepoint=_cp)
        for _cp in full_range
    )
    font = font.modify(glyphs)
    return font

def _convert_to_cp(fonts):
    codepages = sorted(set(_font.encoding for _font in fonts))
    output = []
    for codepage in codepages:
        cp_output = Props()
        output.append(cp_output)
        cp_fonts = tuple(_font for _font in fonts if _font.encoding == codepage)
        cp_number = int(codepage[2:])
        cp_output.cpeh = _CODEPAGE_ENTRY_HEADER(
            cpeh_size=_CODEPAGE_ENTRY_HEADER.size,
            #next_cpeh_offset='long',
            device_type=_DT_SCREEN,
            device_name=b'EGA'.ljust(8),
            #(font.device[:8].encode('ascii', 'replace') or b'EGA').ljust(8),
            codepage=cp_number,
            # cpih should follow immediately
            #cpih_offset=0 if format == _ID_NT else _CODEPAGE_ENTRY_HEADER.size,
        )
        cp_output.cpih = _CODEPAGE_INFO_HEADER(
            #version=_CP_DRFONT if format==_ID_DR else _CP_FONT,
            num_fonts=len(cp_fonts),
            #size='short',
        )
        cp_output.fhs = []
        cp_output.bitmaps = []
        for font in cp_fonts:
            # apparently never used
            if 'cpi' in font.properties:
                propsplit = (item.partition('=') for item in font.cpi.split())
                cpiprops = {_k: _v for _k, _, _v in propsplit}
            else:
                cpiprops = {}
            cp_output.fhs.append(_SCREEN_FONT_HEADER(
                height=font.cell_size.y,
                width=font.cell_size.x,
                yaspect=cpiprops.get('yaspect', 0),
                xaspect=cpiprops.get('xaspect', 0),
                num_chars=len(font.glyphs),
            ))
            # generate bitmaps
            bitmap = b''.join(_g.as_bytes() for _g in font.glyphs)
            cp_output.bitmaps.append(bitmap)
    return output

def _write_cp(outstream, cpdata, format=_ID_MS):
    """Write the representation of a FONT codepage to file."""
    for cpo in cpdata:
        # format params
        cpo.cpih.version = _CP_FONT
        # set pointers
        if format == _ID_MS:
            # cpih follows immediately
            # for _ID_NT, we keep this 0
            cpo.cpeh.cpih_offset = cpo.cpeh.size
        cpo.cpeh.next_cpeh_offset = (
            cpo.cpeh.cpih_offset + cpo.cpih.size
            + sum(
                _SCREEN_FONT_HEADER.size + len(_bmp)
                for _bmp in cpo.bitmaps
            )
        )
        outstream.write(bytes(cpo.cpeh) + bytes(cpo.cpih))
        for _fh, _bmp in zip(cpo.fhs, cpo.bitmaps):
            outstream.write(bytes(_fh))
            outstream.write(_bmp)

def _write_drcp_header(outstream, cpdata):
    """Write the representation of a DRFONT codepage header to file."""
    for cpo in cpdata:
        # format params
        cpo.cpih.version = CP_DRFONT
        # set pointers

        cpo.cpeh.next_cpeh_offset = (
            cpo.cpih.size
            + _SCREEN_FONT_HEADER.size * len(cpo.fhs)
            + _CHARACTER_INDEX_TABLE.size
        )
        # we define all chars in order
        cit = _CHARACTER_INDEX_TABLE(range(256))
        outstream.write(bytes(cpo.cpeh) + bytes(cpo.cpih))
        outstream.write(b''.join(bytes(_fh) for _fh in cpo.fs))
        outstream.write(bytes(cit))
        # in DRFONT, bitmaps follow after all headers
