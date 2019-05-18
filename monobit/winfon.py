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
    bytes_to_bits, ceildiv, pad, bytes_to_str
)

from .winfnt import parse_fnt, create_fnt, _get_prop_x, _get_prop_y


##############################################################################
# MZ/NE/PE executable headers

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


_TYPEINFO = friendlystruct(
    '<',
    rtTypeID='H',
    rtResourceCount='H',
    rtReserved='L',
    #rtNameInfo=_NAMEINFO * rtResourceCount
)

_NAMEINFO = friendlystruct(
    '<',
    rnOffset='H',
    rnLength='H',
    rnFlags='H',
    rnID='H',
    rnHandle='H',
    rnUsage='H',
)
# type ID values that matter to us
_RT_FONTDIR = 0x8007
_RT_FONT = 0x8008




##############################################################################
# top level functions

@Typeface.loads('fon', encoding=None)
def load(instream):
    """Load a Windows .FON file."""
    data = instream.read()
    # determine if a file is a .FON or a .FNT format font
    if data[0:2] != b'MZ':
        raise ValueError('Not a Windows .FON file')
    fonts = _read_fon(data)
    for font in fonts:
        font._properties['source-name'] = os.path.basename(instream.name)
    return Typeface(fonts)

@Typeface.saves('fon', encoding=None)
def save(typeface, outstream):
    """Write fonts to a Windows .FON file."""
    outstream.write(_create_fon(typeface))
    return typeface



##############################################################################
# .FON (NE/PE executable) file reader

def unpack(format, buffer, offset):
    """Unpack a single value from bytes."""
    return struct.unpack_from(format, buffer, offset)[0]


def _read_ne_fon(fon, neoff):
    """Finish splitting up a NE-format FON file."""
    ret = []
    # Find the resource table.
    rtable = neoff + unpack('<H', fon, neoff + 0x24)
    # Read the shift count out of the resource table.
    shift = unpack('<H', fon, rtable)
    # Now loop over the rest of the resource table.
    p = rtable + 2
    while True:
        rtype = unpack('<H', fon, p)
        if rtype == 0:
            break  # end of resource table
        count = unpack('<H', fon, p+2)
        p += 8  # type, count, 4 bytes reserved
        for i in range(count):
            start = unpack('<H', fon, p) << shift
            size = unpack('<H', fon, p+2) << shift
            if start < 0 or size < 0 or start+size > len(fon):
                raise ValueError('Resource overruns file boundaries')
            if rtype == 0x8008: # this is an actual font
                try:
                    font = parse_fnt(fon[start:start+size])
                except Exception as e:
                    raise ValueError('Failed to read font resource at {:x}: {}'.format(start, e))
                ret.append(font)
            p += 12 # start, size, flags, name/id, 4 bytes reserved
    return ret

def _read_pe_fon(fon, peoff):
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

def _read_fon(fon):
    """Split a .FON up into .FNTs and pass each to _read_fnt."""
    # Find the NE header.
    neoff = unpack('<L', fon, 0x3C)
    if fon[neoff:neoff+2] == b'NE':
        return _read_ne_fon(fon, neoff)
    elif fon[neoff:neoff+4] == b'PE\0\0':
        return _read_pe_fon(fon, neoff)
    else:
        raise ValueError('NE or PE signature not found')



##############################################################################
# windows .FON writer


def _create_mz_stub():
    """Create a small MZ executable."""
    dos_stub_size = _MZ_HEADER.size + len(_STUB_CODE) + len(_STUB_MSG) + 1
    num_pages = ceildiv(dos_stub_size, 512)
    last_page_length = dos_stub_size % 512
    mod = dos_stub_size % 16
    if mod:
        padding = b'\0' * (16-mod)
    else:
        padding = b''
    ne_offset = dos_stub_size + len(padding)
    mz_header = _MZ_HEADER(
        magic=b'MZ',
        last_page_length=last_page_length,
        num_pages=num_pages,
        num_relocations=0,
        header_size=4,
        # 16 extra para for stack
        min_allocation=0x10,
        # maximum extra paras: LOTS
        max_allocation=0xffff,
        initial_ss=0,
        initial_sp=0x100,
        checksum=0,
        # CS:IP = 0:0, start at beginning
        initial_csip=0,
        relocation_table_offset=0x40,
        overlay_number=0,
        reserved_0=b'\0'*4,
        behavior_bits=0,
        reserved_1=b'\0'*26,
        ne_offset=ne_offset
    )
    dos_stub = bytes(mz_header) + _STUB_CODE + _STUB_MSG + b'$' + padding
    return dos_stub


def _create_fontdirentry(fnt, properties):
    """Return the FONTDIRENTRY, given the data in a .FNT file."""
    face_name = properties['family'].encode('latin-1', 'replace') + b'\0'
    device_name = properties.get('device', '').encode('latin-1', 'replace') + b'\0'
    return (
        fnt[0:0x71] +
        device_name +
        face_name
    )

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
    nonres = struct.pack('B', len(nonres)) + nonres + b'\0\0\0'

    # Resident name table should just contain a module name.
    mname = bytes(
        _c for _c in name.encode('ascii')
        if _c in set(string.ascii_letters + string.digits)
    )
    res = struct.pack('B', len(mname)) + mname + b'\0\0\0'

    # Entry table / imported names table should contain a zero word.
    entry = struct.pack('<H', 0)

    # Compute length of resource table.
    # 12 (2 for the shift count, plus 2 for end-of-table, plus 8 for the
    #    "FONTDIR" resource name), plus
    # 20 for FONTDIR (TYPEINFO and NAMEINFO), plus
    # 8 for font entry TYPEINFO, plus
    # 12 for each font's NAMEINFO

    # Resources are currently one FONTDIR plus n fonts.
    resrcsize = 12 + 20 + 8 + 12 * len(typeface._fonts)
    resrcpad = ((resrcsize + 15) & ~15) - resrcsize

    # Now position all of this after the NE header.
    off_segtable = off_restable = _NE_HEADER.size # 0x40
    off_res = off_restable + resrcsize + resrcpad
    off_modref = off_import = off_entry = off_res + len(res)
    off_nonres = off_modref + len(entry)
    size_unpadded = off_nonres + len(nonres)
    pad = ((size_unpadded + 15) & ~15) - size_unpadded

    # file offset where the real resources begin.
    real_resource_offset = size_unpadded + pad + len(stubdata)

    # construct the FNT resources
    fonts = [create_fnt(_font) for _font in typeface._fonts]
    # Construct the FONTDIR.
    fontdir = struct.pack('<H', len(fonts))
    for i in range(len(fonts)):
        fontdir += struct.pack('<H', i+1) + _create_fontdirentry(
            fonts[i], typeface._fonts[i]._properties
        )
    resdata = fontdir
    while len(resdata) % 16: # 2 << rscAlignShift
        resdata = resdata + b'\0'
    font_start = [len(resdata)]

    # The FONT resources.
    for i in range(len(fonts)):
        resdata = resdata + fonts[i]
        while len(resdata) % 16:
            resdata = resdata + b'\0'
        font_start.append(len(resdata))


    # The FONTDIR resource table entry
    typeinfo_fontdir = _TYPEINFO(
        rtTypeID=_RT_FONTDIR,
        rtResourceCount=1,
        rtReserved=0,
    )
    # this should be an array, but with only one element...
    nameinfo_fontdir = _NAMEINFO(
        rnOffset=real_resource_offset >> 4, # >> rscAlignShift
        rnLength=len(resdata) >> 4,
        rnFlags=0x0c50, # PRELOAD=0x0040 | MOVEABLE=0x0010 | 0x0c00
        rnID=resrcsize-8,
        rnHandle=0,
        rnUsage=0,
    )

    # FONT resource table entry
    typeinfo_font = _TYPEINFO(
        rtTypeID=_RT_FONT,
        rtResourceCount=len(fonts),
        rtReserved=0,
    )
    nameinfo_font = [
        _NAMEINFO(
            rnOffset=(real_resource_offset+font_start[_i]) >> 4, # >> rscAlignShift
            rnLength=(font_start[_i+1]-font_start[_i]) >> 4,
            rnFlags=0x1c30, # PURE=0x0020 | MOVEABLE=0x0010 | 0x1c00
            rnID=0x8001+_i,
            rnHandle=0,
            rnUsage=0,
        )
        for _i in range(len(fonts))
    ]

    # construct the resource table
    rscAlignShift = struct.pack('<H', 4) # rscAlignShift: shift count 2<<n
    rscTypes = (
        bytes(typeinfo_fontdir) + bytes(nameinfo_fontdir)
        + bytes(typeinfo_font) + b''.join(bytes(_ni) for _ni in nameinfo_font)
    )
    rscEndTypes = b'\0\0' # The zero word.
    rscResourceNames = b'\x07FONTDIR'
    rscEndNames = b'\0'
    restable = rscAlignShift + rscTypes + rscEndTypes + rscResourceNames + rscEndNames

    # resrcsize underestimates struct length by 1
    restable = restable + b'\0' * (resrcpad-1)

    assert resrcsize == (
        len(rscAlignShift) + len(rscEndTypes) + len(rscResourceNames)
        + _TYPEINFO.size + _NAMEINFO.size * 1 #(for FONTDIR)
        + _TYPEINFO.size + _NAMEINFO.size * len(fonts) #(for FONTS)
    )

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
        file_alignment_size_shift_count=4,
        number_res_table_entries=0,
        target_os=2,
        other_os2_exe_flags=8,
        return_thunks_offset=0,
        seg_ref_thunks_offset=0,
        min_code_swap_size=0,
        expected_windows_version=0x300
    )

    file = stubdata + bytes(ne_header) + restable + res + entry + nonres + b'\0' * pad + resdata
    return file
