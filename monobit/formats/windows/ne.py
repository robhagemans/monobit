"""
monobit.formats.windows.ne - Windows 16-bit NE executable header

`monobit.formats.windows` is copyright 2019--2023 Rob Hagemans
`mkwinfont` is copyright 2001 Simon Tatham. All rights reserved.
`dewinfont` is copyright 2001,2017 Simon Tatham. All rights reserved.

See `LICENSE.md` in this package's directory.
"""

import string
import logging

from ...binary import align
from ...struct import little_endian as le
from ...streams import FileFormatError
from .mz import create_mz_stub, ALIGN_SHIFT
from .fnt import create_fnt


##############################################################################
# NE (16-bit) executable structures

# NE format:
#   http://www.csn.ul.ie/~caolan/pub/winresdump/winresdump/doc/winexe.txt
#   http://www.fileformat.info/format/exe/corion-ne.htm
#   https://wiki.osdev.org/NE
#   http://benoit.papillault.free.fr/c/disc2/exefmt.txt
#


# Windows executable (NE) header
_NE_HEADER = le.Struct(
    magic='2s',
    linker_major_version='B',
    linker_minor_version='B',
    entry_table_offset='H',
    entry_table_length='H',
    file_load_crc='L',
    program_flags='B',
    application_flags='B',
    auto_data_seg_index='H', # says 1 byte in table, but offsets make it clear it should be 2 bytes
    initial_heap_size='H',
    initial_stack_size='H',
    entry_point_csip='L',
    initial_stack_pointer_sssp='L',
    segment_count='H',
    module_ref_count='H',
    nonresident_names_table_size='H',
    seg_table_offset='H',
    res_table_offset='H',
    resident_names_table_offset='H',
    module_ref_table_offset='H',
    imp_names_table_offset='H',
    nonresident_names_table_offset='L',
    movable_entry_point_count='H',
    file_alignment_size_shift_count='H',
    number_res_table_entries='H',
    target_os='B',
    other_os2_exe_flags='B',
    return_thunks_offset='H',
    seg_ref_thunks_offset='H',
    min_code_swap_size='H',
    expected_windows_version='H',
)

# TYPEINFO structure and components

_NAMEINFO = le.Struct(
    rnOffset='word',
    rnLength='word',
    rnFlags='word',
    rnID='word',
    rnHandle='word',
    rnUsage='word',
)

def type_info_struct(rtResourceCount=0):
    """TYPEINFO structure."""
    return le.Struct(
        rtTypeID='word',
        rtResourceCount='word',
        rtReserved='dword',
        rtNameInfo=_NAMEINFO * rtResourceCount
    )

# type ID values that matter to us
# https://docs.microsoft.com/en-us/windows/desktop/menurc/resource-types
_RT_FONTDIR = 0x8007
_RT_FONT = 0x8008

# resource table structure (fixed head only)
_RES_TABLE_HEAD = le.Struct(
    rscAlignShift='word',
    #rscTypes=[type_info ...],
    #rscEndTypes='word',
    #rscResourceNames=le.char * len_names,
    #rscEndNames='byte'
)

# https://docs.microsoft.com/en-us/windows/desktop/menurc/direntry
# this is immediately followed by FONTDIRENTRY
# https://docs.microsoft.com/en-us/windows/desktop/menurc/fontdirentry
# which is just a copy of part of the FNT header, plus name and device
_DIRENTRY = le.Struct(
    fontOrdinal='word',
)

# default module name in resident names table
_MODULE_NAME = b'FONTLIB'


##############################################################################
# .FON (NE executable) file reader

def read_ne(instream, all_type_ids):
    """Read font resources from an NE-format FON file."""
    # stream pointer is at the start of the NE header
    # but some offsets in the file are given from the MZ header before that
    ne_offset = instream.tell()
    instream.seek(0)
    data = instream.read()
    header = _NE_HEADER.from_bytes(data, ne_offset)
    logging.debug(header)
    if header.target_os not in (2, 4):
        logging.warning('This is not a Windows NE file.')
    # parse the first elements of the resource table
    res_table = _RES_TABLE_HEAD.from_bytes(data, ne_offset+header.res_table_offset)
    logging.debug(res_table)
    # loop over the rest of the resource table until exhausted
    # we don't know the number of entries
    resources = []
    # skip over rscAlignShift word
    ti_offset = ne_offset + header.res_table_offset + _RES_TABLE_HEAD.size
    while True:
        # parse typeinfo excluding nameinfo array (of as yet unknown size)
        type_info_head = type_info_struct(0)
        type_info = type_info_head.from_bytes(data, ti_offset)
        logging.debug(type_info)
        if type_info.rtTypeID == 0:
            # end of resource table
            break
        # type, count, 4 bytes reserved
        nameinfo_array = _NAMEINFO.array(type_info.rtResourceCount)
        for name_info in nameinfo_array.from_bytes(data, ti_offset + type_info_head.size):
            logging.debug(name_info)
            # the are offsets w.r.t. the file start, not the NE header
            # they could be *before* the NE header for all we know
            start = name_info.rnOffset << res_table.rscAlignShift
            size = name_info.rnLength << res_table.rscAlignShift
            if start < 0 or size < 0 or start + size > len(data):
                logging.warning('Resource overruns file boundaries, skipped')
                continue
            if all_type_ids or type_info.rtTypeID == _RT_FONT:
                logging.debug(
                    'Reading resource of type %d at offset %x [%x]',
                    type_info.rtTypeID, start, name_info.rnOffset
                )
                try:
                    resources.append(data[start : start+size])
                except ValueError as e:
                    # e.g. not a bitmap font
                    # don't raise exception so we can continue with other resources
                    logging.error('Failed to read font resource at {:x}: {}'.format(start, e))
            logging.debug(
                'Skipping resource of type %d at offset %x [%x]',
                type_info.rtTypeID, start, name_info.rnOffset
            )
        # rtResourceCount * 12
        ti_offset += type_info_head.size + nameinfo_array.size
    return resources


##############################################################################
# windows .FON (NE executable) writer


def _create_fontdirentry(ordinal, data, font):
    """Return the DIRENTRY+FONTDIRENTRY, given the data in a .FNT file."""
    direntry = _DIRENTRY(fontOrdinal=ordinal)
    face_name = font.family.encode('latin-1', 'replace') + b'\0'
    device_name = font.device.encode('latin-1', 'replace') + b'\0'
    return (
        bytes(direntry)
        + data[0:0x71]
        + device_name
        + face_name
    )

def _create_resource_table(header_size, post_size, resdata_size, n_fonts, font_start):
    """Build the resource table."""
    res_names = b'\x07FONTDIR'
    # dynamic-size struct types
    typeinfo_fontdir_struct = type_info_struct(1)
    typeinfo_font_struct = type_info_struct(n_fonts)
    res_table_struct = le.Struct(
        rscAlignShift='word',
        # rscTypes is a list of non-equal TYPEINFO entries
        rscTypes_fontdir=typeinfo_fontdir_struct,
        rscTypes_font=typeinfo_font_struct,
        rscEndTypes='word', # 0
        rscResourceNames=le.char * len(res_names),
        rscEndNames='byte', # 0
    )
    # calculate offset to resource data
    res_size_aligned = align(res_table_struct.size, ALIGN_SHIFT)
    resdata_offset = align(header_size + res_size_aligned + post_size, ALIGN_SHIFT)
    # FONTDIR resource table entry
    typeinfo_fontdir = typeinfo_fontdir_struct(
        rtTypeID=_RT_FONTDIR,
        rtResourceCount=1,
        rtNameInfo=(_NAMEINFO*1)(
            _NAMEINFO(
                rnOffset=resdata_offset >> ALIGN_SHIFT,
                rnLength=resdata_size >> ALIGN_SHIFT,
                # PRELOAD=0x0040 | MOVEABLE=0x0010 | 0x0c00 ?
                rnFlags=0x0c50,
                # rnID is set below
            )
        )
    )
    # FONT resource table entry
    typeinfo_font = typeinfo_font_struct(
        rtTypeID=_RT_FONT,
        rtResourceCount=n_fonts,
        rtNameInfo=(_NAMEINFO*n_fonts)(*(
            _NAMEINFO(
                rnOffset=(resdata_offset+font_start[_i]) >> ALIGN_SHIFT,
                rnLength=(font_start[_i+1]-font_start[_i]) >> ALIGN_SHIFT,
                # PURE=0x0020 | MOVEABLE=0x0010 | 0x1c00 ?
                rnFlags=0x1c30,
                rnID=0x8001 + _i,
            )
            for _i in range(n_fonts)
        ))
    )
    # Resource ID. This is an integer type if the high-order
    # bit is set (8000h), otherwise it is the offset to the
    # resource string, the offset is relative to the
    # beginning of the resource table.
    # -- i.e. offset to FONTDIR string
    typeinfo_fontdir.rtNameInfo[0].rnID = res_table_struct.size - len(res_names) - 1
    res_table = res_table_struct(
        rscAlignShift=ALIGN_SHIFT,
        rscTypes_fontdir=typeinfo_fontdir,
        rscTypes_font=typeinfo_font,
        rscResourceNames=res_names,
    )
    return bytes(res_table).ljust(res_size_aligned, b'\0')


def _create_nonresident_name_table(pack):
    """Non-resident name tabe containing the FONTRES line."""
    # get name, dpi of first font
    # FONTRES is probably largely ignored anyway
    families = list(set(font.family for font in pack if font.family))
    if not families:
        names = list(set(font.name for font in pack if font.name))
        if not names:
            name = 'NoName'
        else:
            name, *_ = names[0].split(' ')
    else:
        name = families[0]
        if len(families) > 1:
            logging.warning('More than one font family name in container. Using `%s`.', name)
    resolutions = list(set(font.dpi for font in pack))
    if len(resolutions) > 1:
        logging.warning('More than one resolution in container. Using `%s`.', resolutions[0])
    dpi = resolutions[0]
    xdpi, ydpi = dpi.x, dpi.y
    points = [_font.point_size for _font in pack]
    # FONTRES Aspect, LogPixelsX, LogPixelsY : Name Pts0,Pts1,... (Device res.)
    nonres = ('FONTRES %d,%d,%d : %s %s' % (
        (100 * xdpi) // ydpi, xdpi, ydpi,
        name, ','.join(str(_pt) for _pt in sorted(points))
    )).encode('ascii', 'ignore')
    return bytes([len(nonres)]) + nonres + b'\0\0\0'


def _create_resident_name_table(pack):
    """Resident name table containing the module name."""
    # use font-family name of first font
    families = list(set(font.family.upper() for font in pack if font.family))
    if not families:
        name = _MODULE_NAME.upper()
    else:
        name = families[0]
    # Resident name table should just contain a module name.
    mname = ''.join(
        _c for _c in name
        if _c in set(string.ascii_letters + string.digits)
    )
    return bytes([len(mname)]) + mname.encode('ascii') + b'\0\0\0'


def _create_resource_data(pack, version, vector):
    """Store the actual font resources."""
    # construct the FNT resources
    fonts = [create_fnt(_font, version, vector) for _font in pack]
    # construct the FONTDIR (FONTGROUPHDR)
    # https://docs.microsoft.com/en-us/windows/desktop/menurc/fontgrouphdr
    fontdir_struct = le.Struct(
        NumberOfFonts='word',
        # + array of DIRENTRY/FONTDIRENTRY structs
    )
    fontdir = bytes(fontdir_struct(NumberOfFonts=len(fonts))) + b''.join(
        _create_fontdirentry(_i+1, fonts[_i], _font)
        for _i, _font in enumerate(pack)
    )
    resdata = fontdir.ljust(align(len(fontdir), ALIGN_SHIFT), b'\0')
    font_start = [len(resdata)]
    # append FONT resources
    for i in range(len(fonts)):
        resdata = resdata + fonts[i]
        resdata = resdata.ljust(align(len(resdata), ALIGN_SHIFT), b'\0')
        font_start.append(len(resdata))
    return resdata, font_start


def create_fon(pack, version=0x200, vector=False):
    """Create an NE .FON font library."""
    n_fonts = len(pack)
    # MZ DOS executable stub
    stubdata = create_mz_stub()
    # (non)resident name tables
    nonres = _create_nonresident_name_table(pack)
    res = _create_resident_name_table(pack)
    # entry table / imported names table should contain a zero word.
    entry = b'\0\0'
    # the actual font data
    resdata, font_start = _create_resource_data(pack, version, vector)
    # create resource table and align
    header_size = len(stubdata) + _NE_HEADER.size
    post_size = len(res) + len(entry) + len(nonres)
    restable = _create_resource_table(header_size, post_size, len(resdata), n_fonts, font_start)
    # calculate offsets of stuff after the NE header.
    off_res = _NE_HEADER.size + len(restable)
    off_entry = off_res + len(res)
    off_nonres = off_entry + len(entry)
    size_aligned = align(off_nonres + len(nonres), ALIGN_SHIFT)
    # create the NE header and put everything in place
    ne_header = _NE_HEADER(
        magic=b'NE',
        linker_major_version=5,
        linker_minor_version=10,
        entry_table_offset=off_entry,
        entry_table_length=len(entry),
        # 1<<3: protected mode only
        program_flags=0x08,
        # 0x03: uses windows/p.m. api | 1<<7: dll or driver
        application_flags=0x83,
        nonresident_names_table_size=len(nonres),
        # seg table is empty
        seg_table_offset=_NE_HEADER.size,
        res_table_offset=_NE_HEADER.size,
        resident_names_table_offset=off_res,
        # point to empty table
        module_ref_table_offset=off_entry,
        # point to empty table
        imp_names_table_offset=off_entry,
        # nonresident names table offset is w.r.t. file start
        nonresident_names_table_offset=len(stubdata) + off_nonres,
        file_alignment_size_shift_count=ALIGN_SHIFT,
        # target Windows 3.0
        target_os=2,
        expected_windows_version=0x300
    )
    return (
        stubdata
        + (bytes(ne_header) + restable + res + entry + nonres).ljust(size_aligned, b'\0')
        + resdata
    )
