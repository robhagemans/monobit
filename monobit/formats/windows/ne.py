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
from ...magic import FileFormatError
from .mz import ALIGN_SHIFT
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
NE_HEADER = le.Struct(
    # 00 Magic number NE_MAGIC
    ne_magic='2s',
    # 02 Linker Version number
    ne_ver='uint8',
    # 03 Linker Revision number
    ne_rev='uint8',
    # Offset of Entry Table
    ne_enttab='uint16',
    # 06 Number of bytes in Entry Table
    ne_cbenttab='uint16',
    # 08 Checksum of whole file
    ne_crc='uint32',
    # 0C Flag word
    ne_flags='uint16',
    # 0E Automatic data segment number
    ne_autodata='uint16',
    # 10 Initial heap allocation
    ne_heap='uint16',
    # 12 Initial stack allocation
    ne_stack='uint16',
    # 14 Initial CS:IP setting
    ne_csip='uint32',
    # /18 Initial SS:SP setting
    ne_sssp='uint32',
    # 1C Count of file segments
    ne_cseg='uint16',
    # 1E Entries in Module Reference Table
    ne_cmod='uint16',
    # 20 Size of non-resident name table
    ne_cbnrestab='uint16',
    # 22 Offset of Segment Table
    ne_segtab='uint16',
    # 24 Offset of Resource Table
    ne_rsrctab='uint16',
    # 26 Offset of resident name table
    ne_restab='uint16',
    # 28 Offset of Module Reference Table
    ne_modtab='uint16',
    # 2A Offset of Imported Names Table
    ne_imptab='uint16',
    # 2C Offset of Non-resident Names Table
    ne_nrestab='uint32',
    # 30 Count of movable entries
    ne_cmovent='uint16',
    # 32 Segment alignment shift count
    ne_align='uint16',
    # 34 Count of resource entries
    ne_cres='uint16',
    # 36 Target operating system
    ne_exetyp='uint8',
    # 37 Additional flags
    ne_addflags='uint8',
    # 38 3 reserved words
    ne_res=le.uint16 * 3,
    # 3E Windows SDK revison number
    ne_sdkrev='uint8',
    # 3F Windows SDK version number
    ne_sdkver='uint8',
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
    """Read font resources from a Windows NE-format FON file."""
    # stream pointer is at the start of the NE header
    # but some offsets in the file are given from the MZ header before that
    ne_offset = instream.tell()
    instream.seek(0)
    data = instream.read()
    header = NE_HEADER.from_bytes(data, ne_offset)
    logging.debug(header)
    if header.ne_exetyp not in (0, 2, 4):
        # 0 unknown (but used by Windows 1.0)
        # 1 OS/2
        # 2 Windows
        # 3 European MS_DOS 4.x
        # 4 Windows 386
        # 5 Borland Operating System Services
        logging.warning(
            'Not a Windows NE file: EXE type %d', header.ne_exetyp
        )
    # parse the first elements of the resource table
    res_table = _RES_TABLE_HEAD.from_bytes(data, ne_offset + header.ne_rsrctab)
    logging.debug(res_table)
    # loop over the rest of the resource table until exhausted
    # we don't know the number of entries
    resources = []
    # skip over rscAlignShift word
    ti_offset = ne_offset + header.ne_rsrctab + _RES_TABLE_HEAD.size
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
                resources.append(data[start : start+size])
            else:
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


def create_ne(pack, stubsize, version=0x200, vector=False):
    """Create an NE .FON font library."""
    n_fonts = len(pack)
    # (non)resident name tables
    nonres = _create_nonresident_name_table(pack)
    res = _create_resident_name_table(pack)
    # entry table / imported names table should contain a zero word.
    entry = b'\0\0'
    # the actual font data
    resdata, font_start = _create_resource_data(pack, version, vector)
    # create resource table and align
    header_size = stubsize + NE_HEADER.size
    post_size = len(res) + len(entry) + len(nonres)
    restable = _create_resource_table(header_size, post_size, len(resdata), n_fonts, font_start)
    # calculate offsets of stuff after the NE header.
    off_res = NE_HEADER.size + len(restable)
    off_entry = off_res + len(res)
    off_nonres = off_entry + len(entry)
    size_aligned = align(off_nonres + len(nonres), ALIGN_SHIFT)
    # create the NE header and put everything in place
    ne_header = NE_HEADER(
        ne_magic=b'NE',
        ne_ver=5,
        ne_rev=10,
        ne_enttab=off_entry,
        ne_cbenttab=len(entry),
        # 1<<3: protected mode only
        # 0x03: uses windows/p.m. api | 1<<7: dll or driver
        ne_flags=0x8308,
        ne_cbnrestab=len(nonres),
        # seg table is empty
        ne_segtab=NE_HEADER.size,
        ne_rsrctab=NE_HEADER.size,
        ne_restab=off_res,
        # point to empty table
        ne_modtab=off_entry,
        # point to empty table
        ne_imptab=off_entry,
        # nonresident names table offset is w.r.t. file start
        ne_nrestab=stubsize + off_nonres,
        ne_align=ALIGN_SHIFT,
        # target Windows 3.0
        ne_exetyp=2,
        ne_sdkrev=0,
        ne_sdkver=3,
    )
    return (
        (
            bytes(ne_header)
            + restable + res + entry + nonres
        ).ljust(size_aligned, b'\0')
        + resdata
    )
