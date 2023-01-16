"""
monobit.formats.windows.pe - Windows 32-bit PE executable header

`monobit.formats.windows` is copyright 2019--2023 Rob Hagemans
`mkwinfont` is copyright 2001 Simon Tatham. All rights reserved.
`dewinfont` is copyright 2001,2017 Simon Tatham. All rights reserved.

See `LICENSE.md` in this package's directory.
"""


import logging

from ...struct import little_endian as le
from ...streams import FileFormatError
from .fnt import parse_fnt


##############################################################################
# PE (32-bit) executable structures

# https://docs.microsoft.com/en-gb/windows/desktop/Debug/pe-format
# https://github.com/deptofdefense/SalSA/wiki/PE-File-Format
# https://source.winehq.org/source/include/winnt.h


# PE header (winnt.h _IMAGE_FILE_HEADER)
_PE_HEADER = le.Struct(
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

_IMAGE_SECTION_HEADER = le.Struct(
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

_IMAGE_RESOURCE_DIRECTORY = le.Struct(
    Characteristics='dword',
    TimeDateStamp='dword',
    MajorVersion='word',
    MinorVersion='word',
    NumberOfNamedEntries='word',
    NumberOfIdEntries='word',
)
_IMAGE_RESOURCE_DIRECTORY_ENTRY = le.Struct(
    Id='dword', # technically a union with NameOffset, but meh
    OffsetToData='dword', # or OffsetToDirectory, if high bit set
)

_ID_FONTDIR = 0x07
_ID_FONT = 0x08

_IMAGE_RESOURCE_DATA_ENTRY = le.Struct(
    OffsetToData='dword',
    Size='dword',
    CodePage='dword',
    Reserved='dword',
)


def _parse_pe(data, peoff):
    """Parse a PE-format FON file."""
    # We could try finding the Resource Table entry in the Optional
    # Header, but it talks about RVAs instead of file offsets, so
    # it's probably easiest just to go straight to the section table.
    # So let's find the size of the Optional Header, which we can
    # then skip over to find the section table.
    pe_header = _PE_HEADER.from_bytes(data, peoff)
    section_table_offset = peoff + _PE_HEADER.size + pe_header.SizeOfOptionalHeader
    section_table_array = _IMAGE_SECTION_HEADER.array(pe_header.NumberOfSections)
    section_table = section_table_array.from_bytes(data, section_table_offset)
    # find the resource section
    for section in section_table:
        if section.Name == b'.rsrc':
            logging.debug('Found section `%s`', section.Name.decode('latin-1'))
            break
        logging.debug('Skipping section `%s`', section.Name.decode('latin-1'))
    else:
        raise FileFormatError('Unable to locate resource section')
    # Now we've found the resource section, let's throw away the rest.
    rsrc = data[section.PointerToRawData : section.PointerToRawData+section.SizeOfRawData]
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
            raise FileFormatError('Failed to read font resource at {:x}: {}'.format(start, e))
        ret = ret + [font]
    return ret

def _traverse_dirtable(rsrc, off, rtype):
    """Recursively traverse the dirtable, returning all data entries under the given type id."""
    # resource directory header
    resdir = _IMAGE_RESOURCE_DIRECTORY.from_bytes(rsrc, off)
    number = resdir.NumberOfNamedEntries + resdir.NumberOfIdEntries
    # followed by resource directory entries
    direntry_array = _IMAGE_RESOURCE_DIRECTORY_ENTRY.array(number)
    direntries = direntry_array.from_bytes(rsrc, off+_IMAGE_RESOURCE_DIRECTORY.size)
    dataentries = []
    for entry in direntries:
        logging.debug('Found resource of type %d', entry.Id)
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
