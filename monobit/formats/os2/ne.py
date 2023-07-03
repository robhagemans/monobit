"""
monobit.formats.os2.ne - read OS/2 NE containers

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...magic import FileFormatError
from ...struct import little_endian as le
from ..windows.ne import NE_HEADER
from .gpifont import parse_os2_font_directory

# resource ids
OS2RES_FONTDIR = 6
OS2RES_FONTFACE = 7

# Resource table entry
# this diverges form the Windows format
RT_ENTRY = le.Struct(
    # resource type
    etype='uint16',
    # the resource name (well, for OS/2, it's a number).
    ename='uint16',
)

# https://www.pcjs.org/documents/books/mspl13/msdos/encyclopedia/appendix-k/
ST_ENTRY = le.Struct(
    # Offset of segment relative to beginning
    # of file after shifting value left by alignment shift count
    sector='uint16',
    # Length of segment (0000H for segment of 65536 bytes)
    length='uint16',
    # Segment flag word
    segflag='uint16',
    # Minimum allocation size for segment
    minalloc='uint16',
)


def read_os2_ne(instream, all_type_ids):
    """Read an OS/2 16-bit NE executable."""
    # the header is the same as for the Windows NE format
    ne_offset = instream.tell()
    header = NE_HEADER.read_from(instream)
    if header.ne_exetyp != 1:
        logging.warning(
            'Not an OS/2 NE file: EXE type %d', header.ne_exetyp
        )
    logging.debug(header)
    # parse the segment table
    seg_table = ST_ENTRY.array(header.ne_cseg).read_from(
        instream, ne_offset + header.ne_segtab
    )
    logging.debug(seg_table)
    # parse the OS/2 resource table
    res_table = RT_ENTRY.array(header.ne_cres).read_from(
        instream, ne_offset + header.ne_rsrctab
    )
    logging.debug(res_table)
    # locate resources
    # do something like http://www.edm2.com/0206/resources.html
    resources = []
    font_resource_ids = ()
    # assume resource segments are at end of file
    non_res_segs = header.ne_cseg - header.ne_cres
    for rte, ste in zip(res_table, seg_table[non_res_segs:]):
        offset = ste.sector << header.ne_align
        if (
                not all_type_ids
                and rte.ename not in font_resource_ids
                and rte.etype not in (OS2RES_FONTFACE, OS2RES_FONTDIR)
            ):
            logging.debug(
                'Skipping resource of type %d with id %d at %x',
                rte.etype, rte.ename, offset
            )
            continue
        logging.debug(
            'Reading resource of type %d with id %d at %x',
            rte.etype, rte.ename, offset
        )
        instream.seek(offset)
        rsrc = instream.read(ste.length)
        if rte.etype == OS2RES_FONTDIR:
            font_dir = parse_os2_font_directory(rsrc)
            font_resource_ids = tuple(_fe.usIndex for _fe in font_dir)
        else:
            resources.append(rsrc)
    return resources
