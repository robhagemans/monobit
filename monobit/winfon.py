"""
monobit.winfon - read and write windows .fon files

based on Simon Tatham's dewinfont; see MIT-style licence below.
changes (c) 2019 Rob Hagemans and released under the same licence.

dewinfont is copyright 2001,2017 Simon Tatham. All rights reserved.

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import string
import logging

from .binary import friendlystruct, ceildiv, align
from .typeface import Typeface

from .winfnt import parse_fnt, create_fnt, _get_prop_x, _get_prop_y


##############################################################################
# MZ (DOS) executable headers

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

# DOS executable (MZ) header
_MZ_HEADER = friendlystruct(
    '<',
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

##############################################################################
# NE (16-bit) executable structures

# align on 16-byte (1<<4) boundaries
_ALIGN_SHIFT = 4

# Windows executable (NE) header
_NE_HEADER = friendlystruct(
    '<',
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

_NAMEINFO = friendlystruct(
    'le',
    rnOffset='word',
    rnLength='word',
    rnFlags='word',
    rnID='word',
    rnHandle='word',
    rnUsage='word',
)

def type_info_struct(rtResourceCount=0):
    """TYPEINFO structure."""
    return friendlystruct(
        'le',
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
_RES_TABLE_HEAD = friendlystruct(
    'le',
    rscAlignShift='word',
    #rscTypes=[type_info ...],
    #rscEndTypes='word',
    #rscResourceNames=friendlystruct.char * len_names,
    #rscEndNames='byte'
)

# https://docs.microsoft.com/en-us/windows/desktop/menurc/direntry
# this is immediately followed by FONTDIRENTRY
# https://docs.microsoft.com/en-us/windows/desktop/menurc/fontdirentry
# which is just a copy of part of the FNT header, plus name and device
_DIRENTRY = friendlystruct(
    'le',
    fontOrdinal='word',
)

# default module name in resident names table
_MODULE_NAME = b'FONTLIB'


##############################################################################
# PE (32-bit) executable structures

# PE header (winnt.h _IMAGE_FILE_HEADER)
_PE_HEADER = friendlystruct(
    'le',
    # PE\0\0 magic:
    Signature='4s',
    # struct _IMAGE_FILE_HEADER:
    Machine='word',
    NumberOfSections='word',
    TimeDateStamp='dword',
    PointerToSymbolTable='dword',
    NumberOfSymbols='dword',
    SizeOfOptionalHeader='word',
    Characteristics='word',
    # followed by the non-optional Optional Header
    # which we don't care about for now
)

_IMAGE_SECTION_HEADER = friendlystruct(
    'le',
    Name='8s',
    VirtualSize='dword',
    VirtualAddress='dword',
    SizeOfRawData='dword',
    PointerToRawData='dword',
    PointerToRelocations='dword',
    PointerToLinenumbers='dword',
    NumberOfRelocations='word',
    NumberOfLinenumbers='word',
    Characteristics='dword',
)

_IMAGE_RESOURCE_DIRECTORY = friendlystruct(
    'le',
    Characteristics='dword',
    TimeDateStamp='dword',
    MajorVersion='word',
    MinorVersion='word',
    NumberOfNamedEntries='word',
    NumberOfIdEntries='word',
)
_IMAGE_RESOURCE_DIRECTORY_ENTRY = friendlystruct(
    'le',
    Id='dword', # technically a union with NameOffset, but meh
    OffsetToData='dword', # or OffsetToDirectory, if high bit set
)

_ID_FONTDIR = 0x07
_ID_FONT = 0x08

_IMAGE_RESOURCE_DATA_ENTRY = friendlystruct(
    'le',
    OffsetToData='dword',
    Size='dword',
    CodePage='dword',
    Reserved='dword',
)


##############################################################################
# top level functions

@Typeface.loads('fon', name='Windows FON', encoding=None)
def load(instream):
    """Load a Windows .FON file."""
    data = instream.read()
    mz_header = _MZ_HEADER.from_bytes(data)
    if mz_header.magic not in (b'MZ', b'ZM'):
        raise ValueError('MZ signature not found. Not a Windows .FON file')
    ne_magic = data[mz_header.ne_offset:mz_header.ne_offset+2]
    if ne_magic == b'NE':
        fonts = _parse_ne(data, mz_header.ne_offset)
    elif ne_magic == b'PE':
        # PE magic should be padded by \0\0 but I'll believe it at this stage
        fonts = _parse_pe(data, mz_header.ne_offset)
    else:
        raise ValueError(
            'Executable signature is `{}`, not NE or PE. Not a Windows .FON file'.format(
                ne_magic.decode('latin-1', 'replace')
            )
        )
    for font in fonts:
        font._properties['source-format'] += ' ({} FON container)'.format(ne_magic.decode('ascii'))
    return Typeface(fonts)

@Typeface.saves('fon', encoding=None)
def save(typeface, outstream):
    """Write fonts to a Windows .FON file."""
    outstream.write(_create_fon(typeface))
    return typeface


##############################################################################
# .FON (NE executable) file reader

def _parse_ne(data, ne_offset):
    """Parse an NE-format FON file."""
    header = _NE_HEADER.from_bytes(data, ne_offset)
    # parse the first elements of the resource table
    res_table = _RES_TABLE_HEAD.from_bytes(data, ne_offset+header.res_table_offset)
    # loop over the rest of the resource table until exhausted - we don't know the number of entries
    fonts = []
    # skip over rscAlignShift word
    ti_offset = ne_offset + header.res_table_offset + _RES_TABLE_HEAD.size
    while True:
        # parse typeinfo excluding nameinfo array (of as yet unknown size)
        type_info_head = type_info_struct(0)
        type_info = type_info_head.from_bytes(data, ti_offset)
        if type_info.rtTypeID == 0:
            # end of resource table
            break
        # type, count, 4 bytes reserved
        nameinfo_array = (_NAMEINFO * type_info.rtResourceCount)
        for name_info in nameinfo_array.from_buffer_copy(data, ti_offset + type_info_head.size):
            # the are offsets w.r.t. the file start, not the NE header
            # they could be *before* the NE header for all we know
            start = name_info.rnOffset << res_table.rscAlignShift
            size = name_info.rnLength << res_table.rscAlignShift
            if start < 0 or size < 0 or start + size > len(data):
                raise ValueError('Resource overruns file boundaries')
            if type_info.rtTypeID == _RT_FONT:
                try:
                    fonts.append(parse_fnt(data[start : start+size]))
                except ValueError as e:
                    # e.g. not a bitmap font
                    # don't raise exception so we can continue with other resources
                    logging.error('Failed to read font resource at {:x}: {}'.format(start, e))
        # rtResourceCount * 12
        ti_offset += type_info_head.size + friendlystruct.sizeof(nameinfo_array)
    return fonts


##############################################################################
# .FON (PE executable) file reader
#
# https://docs.microsoft.com/en-gb/windows/desktop/Debug/pe-format
# https://github.com/deptofdefense/SalSA/wiki/PE-File-Format
# https://source.winehq.org/source/include/winnt.h

def _parse_pe(fon, peoff):
    """Parse a PE-format FON file."""
    # We could try finding the Resource Table entry in the Optional
    # Header, but it talks about RVAs instead of file offsets, so
    # it's probably easiest just to go straight to the section table.
    # So let's find the size of the Optional Header, which we can
    # then skip over to find the section table.
    pe_header = _PE_HEADER.from_bytes(fon, peoff)
    section_table_offset = peoff + _PE_HEADER.size + pe_header.SizeOfOptionalHeader
    section_table_array = _IMAGE_SECTION_HEADER * pe_header.NumberOfSections
    section_table = section_table_array.from_buffer_copy(fon, section_table_offset)
    # find the resource section
    for section in section_table:
        if section.Name == b'.rsrc':
            break
    else:
        raise ValueError('Unable to locate resource section')
    # Now we've found the resource section, let's throw away the rest.
    rsrc = fon[section.PointerToRawData : section.PointerToRawData+section.SizeOfRawData]
    # Now the fun begins. To start with, we must find the initial
    # Resource Directory Table and look up type 0x08 (font) in it.
    # If it yields another Resource Directory Table, we recurse
    # into that; below the top level of type font we accept all Ids
    dataentries = _traverse_dirtable(rsrc, 0, _ID_FONT)
    # Each of these describes a font.
    ret = []
    for data_entry in dataentries:
        start = data_entry.OffsetToData - section.VirtualAddress
        try:
            font = parse_fnt(rsrc[start : start+data_entry.Size])
        except ValueError as e:
            raise ValueError('Failed to read font resource at {:x}: {}'.format(start, e))
        ret = ret + [font]
    return ret

def _traverse_dirtable(rsrc, off, rtype):
    """Recursively traverse the dirtable, returning all data entries under the given type id."""
    # resource directory header
    resdir = _IMAGE_RESOURCE_DIRECTORY.from_bytes(rsrc, off)
    number = resdir.NumberOfNamedEntries + resdir.NumberOfIdEntries
    # followed by resource directory entries
    direntry_array = _IMAGE_RESOURCE_DIRECTORY_ENTRY * number
    direntries = direntry_array.from_buffer_copy(rsrc, off+_IMAGE_RESOURCE_DIRECTORY.size)
    dataentries = []
    for entry in direntries:
        if rtype in (entry.Id, None):
            off = entry.OffsetToData
            if off & (1<<31):
                # if it's a subdir, traverse recursively
                dataentries.extend(
                    _traverse_dirtable(rsrc, off & ~(1<<31), None)
                )
            else:
                # if it's a data entry, get the data
                dataentries.append(
                    _IMAGE_RESOURCE_DATA_ENTRY.from_bytes(rsrc, off)
                )
    return dataentries


##############################################################################
# windows .FON (NE executable) writer
#
# NE format:
#   http://www.csn.ul.ie/~caolan/pub/winresdump/winresdump/doc/winexe.txt
#   http://www.fileformat.info/format/exe/corion-ne.htm
#   https://wiki.osdev.org/NE
#   http://benoit.papillault.free.fr/c/disc2/exefmt.txt
#
# MZ header:
#   http://www.delorie.com/djgpp/doc/exe/
#   https://wiki.osdev.org/MZ


def _create_mz_stub():
    """Create a small MZ executable."""
    dos_stub_size = _MZ_HEADER.size + len(_STUB_CODE) + len(_STUB_MSG) + 1
    ne_offset = align(dos_stub_size, _ALIGN_SHIFT)
    mz_header = _MZ_HEADER(
        magic=b'MZ',
        last_page_length=dos_stub_size % 512,
        num_pages=ceildiv(dos_stub_size, 512),
        # 4-para header - FIXME: calculate?
        header_size=4,
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


def _create_fontdirentry(ordinal, fnt, properties):
    """Return the DIRENTRY+FONTDIRENTRY, given the data in a .FNT file."""
    direntry = _DIRENTRY(ordinal)
    face_name = properties['family'].encode('latin-1', 'replace') + b'\0'
    device_name = properties.get('device', '').encode('latin-1', 'replace') + b'\0'
    return (
        bytes(direntry)
        + fnt[0:0x71]
        + device_name
        + face_name
    )

def _create_resource_table(header_size, post_size, resdata_size, n_fonts, font_start):
    """Build the resource table."""
    res_names = b'\x07FONTDIR'
    # dynamic-size struct types
    typeinfo_fontdir_struct = type_info_struct(1)
    typeinfo_font_struct = type_info_struct(n_fonts)
    res_table_struct = friendlystruct(
        'le',
        rscAlignShift='word',
        # rscTypes is a list of non-equal TYPEINFO entries
        rscTypes_fontdir=typeinfo_fontdir_struct,
        rscTypes_font=typeinfo_font_struct,
        rscEndTypes='word', # 0
        rscResourceNames=friendlystruct.char * len(res_names),
        rscEndNames='byte', # 0
    )
    # calculate offset to resource data
    res_size_aligned = align(res_table_struct.size, _ALIGN_SHIFT)
    resdata_offset = align(header_size + res_size_aligned + post_size, _ALIGN_SHIFT)
    # FONTDIR resource table entry
    typeinfo_fontdir = typeinfo_fontdir_struct(
        rtTypeID=_RT_FONTDIR,
        rtResourceCount=1,
        rtNameInfo=(_NAMEINFO*1)(
            _NAMEINFO(
                rnOffset=resdata_offset >> _ALIGN_SHIFT,
                rnLength=resdata_size >> _ALIGN_SHIFT,
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
                rnOffset=(resdata_offset+font_start[_i]) >> _ALIGN_SHIFT,
                rnLength=(font_start[_i+1]-font_start[_i]) >> _ALIGN_SHIFT,
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
        rscAlignShift=_ALIGN_SHIFT,
        rscTypes_fontdir=typeinfo_fontdir,
        rscTypes_font=typeinfo_font,
        rscResourceNames=res_names,
    )
    return bytes(res_table).ljust(res_size_aligned, b'\0')


def _create_nonresident_name_table(typeface):
    """Non-resident name tabe containing the FONTRES line."""
    # get name, dpi of first font
    # FIXME: assuming all the same here, but FONTRES is probably largely ignored anyway
    name = typeface._fonts[0]._properties.get('family', '')
    if not name:
        name, *_ = typeface._fonts[0]._properties.get('name', '').split(' ')
    if not name:
        name = 'NoName'
    dpi = typeface._fonts[0]._properties.get('dpi', 96)
    xdpi, ydpi = _get_prop_x(dpi), _get_prop_y(dpi)
    points = [
        int(_font._properties['point-size'])
        for _font in typeface._fonts if 'point-size' in _font._properties
    ]
    # FONTRES Aspect, LogPixelsX, LogPixelsY : Name Pts0,Pts1,... (Device res.)
    nonres = ('FONTRES %d,%d,%d : %s %s' % (
        (100 * xdpi) // ydpi, xdpi, ydpi,
        name, ','.join(str(_pt) for _pt in sorted(points))
    )).encode('ascii', 'ignore')
    return bytes([len(nonres)]) + nonres + b'\0\0\0'


def _create_resident_name_table(typeface):
    """Resident name table containing the module name."""
    # use font-family name of first font
    name = typeface._fonts[0]._properties.get('family', _MODULE_NAME).upper()
    # Resident name table should just contain a module name.
    mname = ''.join(
        _c for _c in name
        if _c in set(string.ascii_letters + string.digits)
    )
    return bytes([len(mname)]) + mname.encode('ascii') + b'\0\0\0'


def _create_resource_data(typeface):
    """Store the actual font resources."""
    # construct the FNT resources
    fonts = [create_fnt(_font) for _font in typeface._fonts]
    # construct the FONTDIR (FONTGROUPHDR)
    # https://docs.microsoft.com/en-us/windows/desktop/menurc/fontgrouphdr
    fontdir_struct = friendlystruct(
        'le',
        NumberOfFonts='word',
        # + array of DIRENTRY/FONTDIRENTRY structs
    )
    fontdir = bytes(fontdir_struct(len(fonts))) + b''.join(
        _create_fontdirentry(
            i+1, fonts[i], typeface._fonts[i]._properties
        )
        for i in range(len(fonts))
    )
    resdata = fontdir.ljust(align(len(fontdir), _ALIGN_SHIFT), b'\0')
    font_start = [len(resdata)]
    # append FONT resources
    for i in range(len(fonts)):
        resdata = resdata + fonts[i]
        resdata = resdata.ljust(align(len(resdata), _ALIGN_SHIFT), b'\0')
        font_start.append(len(resdata))
    return resdata, font_start


def _create_fon(typeface):
    """Create a .FON font library."""
    n_fonts = len(typeface._fonts)
    # MZ DOS executable stub
    stubdata = _create_mz_stub()
    # (non)resident name tables
    nonres = _create_nonresident_name_table(typeface)
    res = _create_resident_name_table(typeface)
    # entry table / imported names table should contain a zero word.
    entry = b'\0\0'
    # the actual font data
    resdata, font_start = _create_resource_data(typeface)
    # create resource table and align
    header_size = len(stubdata) + _NE_HEADER.size
    post_size = len(res) + len(entry) + len(nonres)
    restable = _create_resource_table(header_size, post_size, len(resdata), n_fonts, font_start)
    # calculate offsets of stuff after the NE header.
    off_res = _NE_HEADER.size + len(restable)
    off_entry = off_res + len(res)
    off_nonres = off_entry + len(entry)
    size_aligned = align(off_nonres + len(nonres), _ALIGN_SHIFT)
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
        file_alignment_size_shift_count=_ALIGN_SHIFT,
        # target Windows 3.0
        target_os=2,
        expected_windows_version=0x300
    )
    return (
        stubdata
        + (bytes(ne_header) + restable + res + entry + nonres).ljust(size_aligned, b'\0')
        + resdata
    )
