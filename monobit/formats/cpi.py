"""
monobit.formats.cpi - DOS Codepage Information format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import string
import logging
from itertools import accumulate

from ..binary import ceildiv
from ..struct import little_endian as le, sizeof
from ..storage import loaders, savers
from ..magic import FileFormatError, Magic
from ..font import Font
from ..glyph import Glyph
from ..properties import Props

from .raw import load_bitmap


_ID_MS = b'FONT   '
_ID_NT = b'FONT.NT'
_ID_DR = b'DRFONT '


@loaders.register(
    name='cpi',
    magic=(
        b'\xff'+_ID_MS,
        b'\xff'+_ID_NT,
        b'\x7f'+_ID_DR,
    ),
    patterns=('*.cpi',),
)
def load_cpi(instream):
    """Load character-cell fonts from DOS Codepage Information (.CPI) file."""
    data = instream.read()
    fonts = _parse_cpi(data)
    return fonts


@loaders.register(
    name='kbd',
    patterns=('*.cp',),
    magic=(
        # FONT
        Magic.offset(6) + b'\1\0' + Magic.offset(20) + b'\1\0',
        # DRFONT
        Magic.offset(6) + b'\1\0' + Magic.offset(20) + b'\2\0',
    ),
)
def load_cp(instream):
    """Load character-cell fonts from Linux Keyboard Codepage (.CP) file."""
    data = instream.read()
    fonts, _ = _parse_cp(data, 0, standalone=True)
    return fonts


@savers.register(linked=load_cp)
def save_cp(
        fonts, outstream,
        version:str=_ID_MS, codepage_prefix:str='cp'
    ):
    """
    Save character-cell fonts to Linux Keyboard Codepage (.CP) file.

    version: CPI format version. One of 'DRFONT', 'FONT.NT', or 'FONT' (default)
    codepage_prefix: prefix to use to find numbered codepage in encodings. Default: 'cp'.
    """
    format = version[:7].upper().ljust(7)
    if isinstance(format, str):
        format = format.encode('ascii', 'replace')
    fonts = _make_fit(fonts, codepage_prefix)
    cpdata, _ = _convert_to_cp(fonts)
    if len(cpdata) > 1:
        raise FileFormatError(
            'All fonts in a single .cp file must have the same encoding.'
        )
    _write_cp(outstream, cpdata[0], format=format)


@savers.register(linked=load_cpi)
def save_cpi(
        fonts, outstream,
        version:str=_ID_MS, codepage_prefix:str='cp'
    ):
    """
    Save character-cell fonts to Linux Keyboard Codepage (.CP) file.

    version: CPI format version. One of 'DRFONT', 'FONT.NT', or 'FONT' (default)
    codepage_prefix: prefix to use to find numbered codepage in encodings. Default: 'cp'.
    """
    format = version[:7].upper().ljust(7)
    if isinstance(format, str):
        format = format.encode('ascii', 'replace')
    if format in (_ID_MS, _ID_NT):
        return _save_ms_cpi(fonts, outstream, format, codepage_prefix)
    elif format == _ID_DR:
        return _save_dr_cpi(fonts, outstream, format, codepage_prefix)
    accepted = b"', '".join((_ID_MS, _ID_NT, _ID_DR)).decode('ascii')
    raise ValueError(
        f"CPI format must be one of '{accepted}', not '{format.decode('latin-1')}'"
    )


###############################################################################
# CPI reader
# https://www.seasip.info/DOS/CPI/cpi.html
# https://www.win.tue.nl/~aeb/linux/kbd/font-formats-3.html


_CPI_HEADER = le.Struct(
    # The first byte of the file is 0xFF for FONT and FONT.NT files,
    # and 0x7F for DRFONT files.
    id0='byte',
    # This is the file format, space padded: "FONT   ", "FONT.NT" or "DRFONT ".
    id='7s',
    # The eight reserved bytes are always zero.
    reserved='8s',
    # This is the number of pointers in this header. In all known CPI files
    # this is 1; the MS-DOS 5 Programmer's Reference says that "for current
    # versions of MS-DOS" it should be 1.
    pnum='short',
    # The type of the pointer in the header. In all known CPI files this is 1;
    # the MS-DOS reference says that "for current versions of MS-DOS" it
    # should be 1.
    ptyp='byte',
    # The offset in the file of the FontInfoHeader. In FONT and FONT.NT files,
    # this is usually 0x17, pointing to immediately after the FontFileHeader -
    # though files with other values are known to exist [10]. In DRFONT files,
    # it should # point to immediately after the DRDOSExtendedFontFileHeader [2],
    # which for a # four-font CPI file puts it at 0x2C.
    fih_offset='long',
)
_FONT_INFO_HEADER = le.Struct(
    num_codepages='short',
)

# DRDOS Extended Font File Header
def drdos_ext_header(num_fonts_per_codepage=0):
    return le.Struct(
        num_fonts_per_codepage='byte',
        font_cellsize=le.uint8 * num_fonts_per_codepage,
        dfd_offset=le.uint32 * num_fonts_per_codepage,
    )


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
    # > This is the size of the CodePageEntryHeader structure, i.e. 0x1C bytes.
    # > Some CPI files have other values here, most often 0x1A. Some utilities
    # > ignore this field and always load 0x1C bytes; others believe it.
    cpeh_size='short',
    # > This is the offset of the next CodePageEntryHeader in the file. In FONT
    # > and DRFONT files, the address is relative to the start of the file; in
    # > FONT.NT files, it is relative to the start of this CodePageEntryHeader.
    # > In the last CodePageEntryHeader, the value of this field has no meaning.
    # > Some files set it to 0, some to -1, and some to point at where the next
    # > CodePageEntryHeader would be.
    # > The MS-DOS 5 Programmer's Reference says it should be 0.
    next_cpeh_offset='long',
    # > 1 for screen, 2 for printer. [...] Printer codepages should only be
    # > present in FONT files, not FONT.NT or DRFONT.
    device_type='short',
    # > The ASCII device name. For screens, it refers to the display hardware
    # > ("EGA     " for EGA/VGA and "LCD     " for the IBM Convertible LCD)
    device_name='8s',
    # > This is the number of the codepage this header describes. Traditionally,
    # > DOS codepages had 3-digit IDs (1-999) but the number can range from
    # > 1-65533. IDs 65280-65533 are 'reserved for customer use'
    codepage='uint16',
    reserved='6s',
    # > The offset of the CodePageInfoHeader for this codepage. In FONT and
    # > DRFONT files, it is relative to the start of the file; in FONT.NT files
    # > it is relative to the start of this CodePageEntryHeader.
    # > As with next_cpeh_offset, the field is normally treated as a 32-bit
    # > pointer but some programs may instead populate it with segment:offset values.
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
    # > This is 1 if the following codepage is in FONT format, 2 if it is in
    # > DRFONT format. Putting a DRFONT codepage in a FONT-format file will not
    # > work. You shouldn't put a FONT codepage in a DRFONT-format file either.
    version='short',
    # > If this is a screen font, it gives the number of font records that follow.
    num_fonts='short',
    # > This is the number of bytes that follow up to the end of this codepage
    # > (if version is 1) or up to the character index table (if version is 2).
    size_to_end='short',
)
_PRINTER_FONT_HEADER = le.Struct(
    printer_type='short',
    escape_length='short',
)
_SCREEN_FONT_HEADER = le.Struct(
    # > This is the character height in pixels.
    height='byte',
    # > This is the character width in pixels; in all known CPI files it is 8.
    width='byte',
    # > Vertical aspect ratio. In all known CPI files this is unused and set to zero.
    yaspect='byte',
    # > Horizontal aspect ratio. In all known CPI files this is unused and set to zero.
    xaspect='byte',
    # > Number of characters in the font. In known CPI files this is always 256.
    num_chars='short',
)
# DRFONT character index table
_CHARACTER_INDEX_TABLE = le.Struct(
    FontIndex=le.int16 * 256,
)

def _read_cp_header(data, start_offset, format, standalone):
    cpeh = _CODEPAGE_ENTRY_HEADER.from_bytes(data, start_offset)
    if cpeh.device_type == _DT_PRINTER:
        # printer fonts apparently hold printer-specific escape sequences
        raise FileFormatError(
            'Printer CPI codepages not supported: '
            f'codepage {cpeh.codepage}, device `{cpeh.device_name}`'
        )
    # fix offsets to headers
    if format == _ID_NT:
        # > in FONT.NT files, it is relative to the start of this CodePageEntryHeader.
        cpeh.cpih_offset += start_offset
        cpeh.next_cpeh_offset += start_offset
    if standalone:
        # on a standalone codepage (kbd .cp file), ignore the offset
        # CPIH follows immediately after CPEH
        cpeh.cpih_offset = start_offset + _CODEPAGE_ENTRY_HEADER.size
    cpih = _CODEPAGE_INFO_HEADER.from_bytes(data, cpeh.cpih_offset)
    if cpih.version == 0:
        # https://www.seasip.info/DOS/CPI/cpi.html
        # > LCD.CPI from Toshiba MS-DOS 3.30 sets this field to 0, which should be treated as 1.
        cpih.version = _CP_FONT
    if cpih.version not in (_CP_DRFONT, _CP_FONT):
        raise FileFormatError(
            f'Incorrect CP format version number {cpih.version}.'
        )
    return cpeh, cpih


def _parse_cp(data, cpeh_offset, header_id=_ID_MS, drdos_effh=None, standalone=False):
    """Parse a .CP codepage."""
    cpeh, cpih = _read_cp_header(data, cpeh_offset, header_id, standalone)
    # offset to the first font header
    fh_offset = cpeh.cpih_offset + _CODEPAGE_INFO_HEADER.size
    # glyph index table for drfont
    # for ms formats, the glyphs are in simple order
    if cpih.version == _CP_DRFONT:
        cit_offset = fh_offset + cpih.num_fonts * _SCREEN_FONT_HEADER.size
        cit = _CHARACTER_INDEX_TABLE.from_bytes(data, cit_offset)
        glyph_index = cit.FontIndex
    else:
        glyph_index = range(256)
    fonts = []
    for cp_index in range(cpih.num_fonts):
        fh = _SCREEN_FONT_HEADER.from_bytes(data, fh_offset)
        fh_offset += _SCREEN_FONT_HEADER.size
        # get the bitmap
        if cpih.version == _CP_FONT:
            bytesize = fh.height * ceildiv(fh.width, 8)
            # bitmaps are in between headers for FONT and FONT.NT
            bm_offset = fh_offset
            fh_offset += fh.num_chars * bytesize
        else:
            # this is also the height, as width must be 8
            bytesize = drdos_effh.font_cellsize[cp_index]
            # bitmaps are at end of file
            bm_offset = drdos_effh.dfd_offset[cp_index]
        cells = _read_glyphs(
            data, bm_offset, bytesize, fh.width, glyph_index[:fh.num_chars]
        )
        font = _convert_from_cp(cells, cpeh, fh, header_id)
        fonts.append(font)
    # if this was the last entry and no pointer provided,
    # set the pointer to the bitmap end
    if cpeh.next_cpeh_offset in (0, 0xffffffff):
        cpeh.next_cpeh_offset = bm_offset + (max(glyph_index[:fh.num_chars])+1) * bytesize
    return fonts, cpeh.next_cpeh_offset

def _read_glyphs(data, bm_offset, bytesize, width, glyph_index):
    """Read bitmaps."""
    offsets = (
        bm_offset + _index * bytesize
        for _index in glyph_index
    )
    cells = tuple(
        Glyph.from_bytes(data[_offs : _offs+bytesize], width)
        for _offs in offsets
    )
    return cells

def _convert_from_cp(cells, cpeh, fh, header_id):
    """Convert to monobit font."""
    # extract font properties
    device = cpeh.device_name.strip().decode('ascii', 'replace')
    format = header_id.strip().decode("latin-1")
    props = dict(
        encoding=f'cp{cpeh.codepage}',
        device=device,
        source_format=f'CPI ({format})',
    )
    # apparently never used
    if fh.xaspect or fh.yaspect:
        # not clear how this would be interpreted...
        props['cpi'] = f'xaspect={fh.xaspect} yaspect={fh.yaspect}'
    logging.debug(
        f'Reading {fh.width}x{fh.height} font '
        f'for codepage {cpeh.codepage} '
        f'in {format} format.'
    )
    # add codepoints and character labels
    cells = tuple(
        _g.modify(codepoint=_cp)
        for _cp, _g in enumerate(cells)
    )
    font = Font(cells, **props)
    font = font.label()
    return font


###############################################################################
# CP writer

# storable code points
_RANGE = range(256)

def _make_fit(fonts, codepage_prefix):
    """Select only the fonts that fit."""
    fonts = (_make_one_fit(_font, codepage_prefix) for _font in fonts)
    fonts = tuple(_font for _font in fonts if _font)
    if not fonts:
        raise FileFormatError(
            'CPI format can only store 8xN character-cell fonts'
            ' encoded with a numbered codepage.'
        )
    sizes = set(_f.cell_size for _f in fonts)
    codepages = sorted(set(_f.encoding for _f in fonts))
    # ensure all sizes exist for all codepages
    for cp in codepages:
        cp_fonts = tuple(_f for _f in fonts if _f.encoding == cp)
        cp_sizes = set(_f.cell_size for _f in cp_fonts)
        # drop all fonts of sizes that aren't available in this codepage
        sizes &= cp_sizes
    fonts = tuple(_font for _font in fonts if _font.cell_size in sizes)
    return fonts

def _make_one_fit(font, codepage_prefix):
    """Check if font fits in format and reshape as necessary."""
    if font.cell_size.x != 8:
        logging.warning(
            'CP format can only store 8xN character-cell fonts.'
        )
        return None
    if not font.encoding.startswith(codepage_prefix):
        logging.warning(
            'CP fonts must have encoding set to a numbered codepage'
        )
        return None
    # ensure codepoint values are set, if possible
    font = font.label(codepoint_from=font.encoding)
    # take only the glyphs that will fit
    font = font.subset(_RANGE)
    font = font.equalise_horizontal()
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

def _get_consistent(fonts, property):
    """Get value for a property across fonts, or None if inconsistent."""
    values = tuple(set(
        _font.get_property(property)
        for _font in fonts
        if property in _font.get_properties()
    ))
    if len(values) == 1:
        return values[0]
    return None


def _convert_to_cp(fonts):
    codepages = sorted(set(_font.encoding for _font in fonts))
    # preserve notice, if it is consistent
    notice = _get_consistent(fonts, 'notice') or ''
    output = []
    for codepage in codepages:
        cp_output = Props()
        output.append(cp_output)
        cp_fonts = (_font for _font in fonts if _font.encoding == codepage)
        # sort fonts by increasing cell size
        # so that the same font number has the same size
        cp_fonts = sorted(cp_fonts, key=lambda _f: _f.cell_size)
        cp_number = int(codepage[2:])
        # preserve device name, if it is consistent
        device = _get_consistent(cp_fonts, 'device') or 'EGA'
        device = device[:8].encode('ascii', 'replace').ljust(8)
        # set header fields
        cp_output.cpeh = _CODEPAGE_ENTRY_HEADER(
            cpeh_size=_CODEPAGE_ENTRY_HEADER.size,
            next_cpeh_offset=0,
            device_type=_DT_SCREEN,
            device_name=device,
            codepage=cp_number,
            #cpih_offset=0,
        )
        cp_output.cpih = _CODEPAGE_INFO_HEADER(
            #version=_CP_DRFONT if format==_ID_DR else _CP_FONT,
            num_fonts=len(cp_fonts),
            #size_to_end='short',
        )
        cp_output.fhs = []
        cp_output.bitmaps = []
        for font in cp_fonts:
            # apparently never used
            if 'cpi' in font.get_properties():
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
    return output, notice

def _write_cp(outstream, cpo, format=_ID_MS, start_offset=0):
    """Write the representation of a FONT codepage to file."""
    # format params
    cpo.cpih.version = _CP_FONT
    # set pointers
    # cpih follows immediately
    cpo.cpeh.cpih_offset = sizeof(cpo.cpeh)
    if format == _ID_MS:
        cpo.cpeh.cpih_offset += start_offset
    cpo.cpih.size_to_end = sum(
        _SCREEN_FONT_HEADER.size + len(_bmp)
        for _bmp in cpo.bitmaps
    )
    cpo.cpeh.next_cpeh_offset = (
        cpo.cpeh.cpih_offset + sizeof(cpo.cpih)
        + cpo.cpih.size_to_end
    )
    outstream.write(bytes(cpo.cpeh) + bytes(cpo.cpih))
    for _fh, _bmp in zip(cpo.fhs, cpo.bitmaps):
        outstream.write(bytes(_fh))
        outstream.write(_bmp)
    return cpo.cpeh.next_cpeh_offset

def _write_dr_cp_header(outstream, cpo, start_offset, last):
    """Write the representation of a DRFONT codepage header to file."""
    # format params
    cpo.cpih.version = _CP_DRFONT
    # set pointers
    cpo.cpeh.cpih_offset = start_offset + sizeof(cpo.cpeh)
    # (For DRFONT) This is the number of bytes up to the character index table.
    cpo.cpih.size_to_end = _SCREEN_FONT_HEADER.size * len(cpo.fhs)
    if not last:
        cpo.cpeh.next_cpeh_offset = (
            start_offset + sizeof(cpo.cpih)
            + cpo.cpih.size_to_end
            + _CHARACTER_INDEX_TABLE.size
        )
    # we define all chars in order
    cit = _CHARACTER_INDEX_TABLE(FontIndex=tuple(range(256)))
    outstream.write(bytes(cpo.cpeh) + bytes(cpo.cpih))
    outstream.write(b''.join(bytes(_fh) for _fh in cpo.fhs))
    outstream.write(bytes(cit))
    # in DRFONT, bitmaps follow after all headers
    return cpo.cpeh.next_cpeh_offset

def _save_ms_cpi(fonts, outstream, format, codepage_prefix):
    """Save to FONT or FONT.NT CPI file"""
    fonts = _make_fit(fonts, codepage_prefix)
    cpdata, notice = _convert_to_cp(fonts)
    ffh = _CPI_HEADER(
        id0=0xff,
        id=format.ljust(7),
        pnum=1,
        ptyp=1,
        fih_offset=_CPI_HEADER.size,
    )
    fih = _FONT_INFO_HEADER(
        num_codepages=len(cpdata),
    )
    outstream.write(bytes(ffh) + bytes(fih))
    offset = _CPI_HEADER.size + _FONT_INFO_HEADER.size
    for cpo in cpdata:
        offset = _write_cp(outstream, cpo, format, offset)
    outstream.write(notice.encode('ascii', 'replace'))


def _save_dr_cpi(fonts, outstream, format, codepage_prefix):
    """Save to DRFONT CPI file"""
    fonts = _make_fit(fonts, codepage_prefix)
    cpdata, notice = _convert_to_cp(fonts)
    # drdos codepages must have equal number of fonts for each page,
    # in the same set of cell sizes
    # since we've ensured that in _make_fit, we can just do this
    num_fonts_per_codepage = len(fonts) // len(cpdata)
    cell_sizes = tuple(_fh.height for _fh in cpdata[0].fhs)
    # bitmap offsets
    ddeff_type = drdos_ext_header(num_fonts_per_codepage)
    offset = _CPI_HEADER.size + _FONT_INFO_HEADER.size + ddeff_type.size
    drcp_size = (
        _CODEPAGE_ENTRY_HEADER.size + _CODEPAGE_INFO_HEADER.size
        + _SCREEN_FONT_HEADER.size * num_fonts_per_codepage
        + _CHARACTER_INDEX_TABLE.size
    )
    bitmap_start = offset + drcp_size*len(cpdata)
    lengths = (sum(len(_bmp) for _bmp in _cpo.bitmaps) for _cpo in cpdata)
    dfd_offsets = tuple(accumulate(lengths, initial=bitmap_start))
    ddeff = ddeff_type(
        num_fonts_per_codepage=num_fonts_per_codepage,
        font_cellsize=(le.uint8 * num_fonts_per_codepage)(*cell_sizes),
        dfd_offset=(le.uint32 * num_fonts_per_codepage)(*dfd_offsets[:-1]),
    )
    ffh = _CPI_HEADER(
        id0=0x7f,
        id=format.ljust(7),
        pnum=1,
        ptyp=1,
        fih_offset=_CPI_HEADER.size + ddeff_type.size,
    )
    fih = _FONT_INFO_HEADER(num_codepages=len(cpdata))
    outstream.write(bytes(ffh) + bytes(ddeff) + bytes(fih))
    for i, cpo in enumerate(cpdata):
        offset = _write_dr_cp_header(outstream, cpo, offset, i==len(cpdata)-1)
    for cpo in cpdata:
        for bitmap in cpo.bitmaps:
            outstream.write(bitmap)
    outstream.write(notice.encode('ascii', 'replace'))
