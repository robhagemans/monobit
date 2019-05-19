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

import os
import sys
import string
import struct
import logging
import itertools

from .base import (
    VERSION, Glyph, Font, Typeface, friendlystruct,
    bytes_to_bits, ceildiv, align, bytes_to_str
)

from .winfnt import parse_fnt, create_fnt, _get_prop_x, _get_prop_y


##############################################################################
# MZ/NE/PE executable headers

# align on 16-byte (2<<4) boundaries
_ALIGN_SHIFT = 4

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
_STUB_MSG = b'This is a Windows font file.\r\n'


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


##############################################################################
# top level functions

@Typeface.loads('fon', encoding=None)
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
        font._properties['source-name'] = os.path.basename(instream.name)
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

def unpack(format, buffer, offset):
    """Unpack a single value from bytes."""
    return struct.unpack_from(format, buffer, offset)[0]

def _parse_pe(fon, peoff):
    """Finish splitting up a PE-format FON file."""
    dirtables = []
    dataentries = []

    def gotoffset(off, dirtables=dirtables, dataentries=dataentries):
        if off & 0x80000000:
            off &= ~0x80000000
            dirtables.append(off)
        else:
            dataentries.append(off)

    def dodirtable(rsrc, off, rtype, gotoffset=gotoffset):
        number = unpack('<H', rsrc, off+12) + unpack('<H', rsrc, off+14)
        for i in range(number):
            entry = off + 16 + 8*i
            thetype = unpack('<L', rsrc, entry)
            theoff = unpack('<L', rsrc, entry+4)
            if rtype == -1 or rtype == thetype:
                gotoffset(theoff)

    # We could try finding the Resource Table entry in the Optional
    # Header, but it talks about RVAs instead of file offsets, so
    # it's probably easiest just to go straight to the section table.
    # So let's find the size of the Optional Header, which we can
    # then skip over to find the section table.
    secentries = unpack('<H', fon, peoff+0x06)
    sectable = peoff + 0x18 + unpack('<H', fon, peoff+0x14)
    for i in range(secentries):
        secentry = sectable + i * 0x28
        secname = bytes_to_str(fon[secentry:secentry+8])
        secrva = unpack('<L', fon, secentry+0x0C)
        secsize = unpack('<L', fon, secentry+0x10)
        secptr = unpack('<L', fon, secentry+0x14)
        if secname == '.rsrc':
            break
    else:
        raise ValueError('Unable to locate resource section')
    # Now we've found the resource section, let's throw away the rest.
    rsrc = fon[secptr:secptr+secsize]
    # Now the fun begins. To start with, we must find the initial
    # Resource Directory Table and look up type 0x08 (font) in it.
    # If it yields another Resource Directory Table, we stick the
    # address of that on a list. If it gives a Data Entry, we put
    # that in another list.
    dodirtable(rsrc, 0, 0x08)
    # Now process Resource Directory Tables until no more remain
    # in the list. For each of these tables, we accept _all_ entries
    # in it, and if they point to subtables we stick the subtables in
    # the list, and if they point to Data Entries we put those in
    # the other list.
    while len(dirtables) > 0:
        table = dirtables[0]
        del dirtables[0]
        dodirtable(rsrc, table, -1) # accept all entries
    # Now we should be left with Resource Data Entries. Each of these
    # describes a font.
    ret = []
    for off in dataentries:
        rva = unpack('<L', rsrc, off)
        size = unpack('<L', rsrc, off+4)
        start = rva - secrva
        try:
            font = _read_fnt(rsrc[start:start+size])
        except Exception as e:
            raise ValueError('Failed to read font resource at {:x}: {}'.format(start, e))
        ret = ret + [font]
    return ret


##############################################################################
# windows .FON (NE executable) writer

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


def _create_fontdirentry(fnt, properties):
    """Return the FONTDIRENTRY, given the data in a .FNT file."""
    face_name = properties['family'].encode('latin-1', 'replace') + b'\0'
    device_name = properties.get('device', '').encode('latin-1', 'replace') + b'\0'
    return (
        fnt[0:0x71] +
        device_name +
        face_name
    )

def _create_resource_table(real_resource_offset, resrcsize, resdata_size, n_fonts, font_start):
    """Build the resource table."""
    # FONTDIR resource table entry
    typeinfo_fontdir_struct = type_info_struct(1)
    typeinfo_fontdir = typeinfo_fontdir_struct(
        rtTypeID=_RT_FONTDIR,
        rtResourceCount=1,
        rtNameInfo=(_NAMEINFO*1)(
            _NAMEINFO(
                rnOffset=real_resource_offset >> _ALIGN_SHIFT,
                rnLength=resdata_size >> _ALIGN_SHIFT,
                # PRELOAD=0x0040 | MOVEABLE=0x0010 | 0x0c00 ?
                rnFlags=0x0c50,
                #FIXME: why? should this be -9 as we added 1 to resrcsize?
                rnID=resrcsize-8,
            )
        )
    )
    # FONT resource table entry
    typeinfo_font_struct = type_info_struct(n_fonts)
    typeinfo_font = typeinfo_font_struct(
        rtTypeID=_RT_FONT,
        rtResourceCount=n_fonts,
        rtNameInfo=(_NAMEINFO*n_fonts)(*(
            _NAMEINFO(
                rnOffset=(real_resource_offset+font_start[_i]) >> _ALIGN_SHIFT,
                rnLength=(font_start[_i+1]-font_start[_i]) >> _ALIGN_SHIFT,
                # PURE=0x0020 | MOVEABLE=0x0010 | 0x1c00 ?
                rnFlags=0x1c30,
                rnID=0x8001+_i,
            )
            for _i in range(n_fonts)
        ))
    )
    # construct the resource table
    res_names = b'\x07FONTDIR'
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
    res_table = res_table_struct(
        # rscAlignShift: shift count 2<<n
        rscAlignShift=_ALIGN_SHIFT,
        rscTypes_fontdir=typeinfo_fontdir,
        rscTypes_font=typeinfo_font,
        rscResourceNames=res_names,
    )
    return bytes(res_table)


def _create_fon(typeface):
    """Create a .FON font library, given a bunch of .FNT file contents."""

    # use font-family name and dpi of first font
    name = typeface._fonts[0]._properties.get('family', 'NoName')
    dpi = typeface._fonts[0]._properties.get('dpi', 96)
    xdpi, ydpi = _get_prop_x(dpi), _get_prop_y(dpi)
    points = [
        int(_font._properties['points'])
        for _font in typeface._fonts if 'points' in _font._properties
    ]

    # The MZ stub.
    stubdata = _create_mz_stub()

    # Non-resident name table should contain a FONTRES line.
    # FONTRES Aspect, LogPixelsX, LogPixelsY : Name Pts0,Pts1,... (Device res.)
    nonres = ('FONTRES %d,%d,%d : %s %s' % (
        (100 * xdpi) // ydpi, xdpi, ydpi,
        name, ','.join(str(_pt) for _pt in sorted(points))
    )).encode('ascii', 'ignore')
    nonres = bytes([len(nonres)]) + nonres + b'\0\0\0'

    # Resident name table should just contain a module name.
    mname = bytes(
        _c for _c in name.encode('ascii')
        if _c in set(string.ascii_letters + string.digits)
    )
    res = bytes([len(mname)]) + mname + b'\0\0\0'

    # Entry table / imported names table should contain a zero word.
    entry = struct.pack('<H', 0)

    # Compute length of resource table.
    # 12 (2 for the shift count, plus 2 for end-of-table, plus 8 for the
    #    "FONTDIR" resource name), plus
    # 20 for FONTDIR (TYPEINFO and NAMEINFO), plus
    # 8 for font entry TYPEINFO, plus
    # 12 for each font's NAMEINFO
    # 1 for zero byte at end

    # Resources are currently one FONTDIR plus n fonts.
    resrcsize = 12 + 20 + 8 + 12 * len(typeface._fonts) + 1
    resrcsize_aligned = align(resrcsize, _ALIGN_SHIFT)

    # Now position all of this after the NE header.
    off_segtable = off_restable = _NE_HEADER.size
    off_res = off_restable + resrcsize_aligned
    off_modref = off_import = off_entry = off_res + len(res)
    off_nonres = off_modref + len(entry)
    size_unpadded = off_nonres + len(nonres)
    # align on 16-byte boundary
    padding = align(size_unpadded, _ALIGN_SHIFT) - size_unpadded

    # file offset where the real resources begin.
    real_resource_offset = size_unpadded + padding + len(stubdata)

    # construct the FNT resources
    fonts = [create_fnt(_font) for _font in typeface._fonts]

    # Construct the FONTDIR.
    fontdir = struct.pack('<H', len(fonts))
    for i in range(len(fonts)):
        fontdir += struct.pack('<H', i+1) + _create_fontdirentry(
            fonts[i], typeface._fonts[i]._properties
        )
    resdata = fontdir.ljust(align(len(fontdir), _ALIGN_SHIFT), b'\0')

    font_start = [len(resdata)]
    # The FONT resources.
    for i in range(len(fonts)):
        resdata = resdata + fonts[i]
        resdata = resdata.ljust(align(len(resdata), _ALIGN_SHIFT), b'\0')
        font_start.append(len(resdata))

    # create resource table and align
    restable = _create_resource_table(real_resource_offset, resrcsize, len(resdata), len(fonts), font_start)
    assert resrcsize == len(restable)
    restable = restable.ljust(resrcsize_aligned, b'\0')

    ne_header = _NE_HEADER(
        magic=b'NE',
        linker_major_version=5,
        linker_minor_version=10,
        entry_table_offset=off_entry,
        entry_table_length=len(entry),
        file_load_crc=0,
        program_flags=0x08,
        application_flags=0x83,
        auto_data_seg_index=0,
        initial_heap_size=0,
        initial_stack_size=0,
        entry_point_csip=0,
        initial_stack_pointer_sssp=0,
        segment_count=0,
        module_ref_count=0,
        nonresident_names_table_size=len(nonres),
        seg_table_offset=off_segtable,
        res_table_offset=off_restable,
        resident_names_table_offset=off_res,
        module_ref_table_offset=off_modref,
        imp_names_table_offset=off_import,
        nonresident_names_table_offset=len(stubdata) + off_nonres,
        movable_entry_point_count=0,
        file_alignment_size_shift_count=_ALIGN_SHIFT,
        number_res_table_entries=0,
        target_os=2,
        other_os2_exe_flags=8,
        return_thunks_offset=0,
        seg_ref_thunks_offset=0,
        min_code_swap_size=0,
        expected_windows_version=0x300
    )

    file = stubdata + bytes(ne_header) + restable + res + entry + nonres + b'\0'*padding + resdata
    return file
