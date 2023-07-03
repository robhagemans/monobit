"""
monobit.formats.mac.lisa - Apple Lisa fonts

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...struct import big_endian as be
from ...binary import align
from ...magic import FileFormatError

from .nfnt import extract_nfnt, convert_nfnt


# https://www.kreativekorp.com/swdownload/lisa/AppleLisaFontFormat.pdf

_LISA_HEADER = be.Struct(
    # numer of words in header, less 4
    headerLength='uint16',
    numFontRsrcs='uint16',
)
_LISA_RSRC_RCD1 = be.Struct(
    fontResourceStart='uint32',
    fontResourceEnd='uint32',
    fontMetricsStart='uint32',
    fontMetricsEnd='uint32',
)

def _load_lisa(instream):
    """Load a LISA font library."""
    header = _LISA_HEADER.read_from(instream)
    rsrc_rcds = []
    names = []
    for _ in range(header.numFontRsrcs):
        fontRsrcNameLen = be.uint8.read_from(instream)
        fontRsrcName = (be.char * fontRsrcNameLen).read_from(instream)
        offset = align(fontRsrcNameLen+1,1)
        instream.read(offset - int(fontRsrcNameLen)-1)
        rcd1 = _LISA_RSRC_RCD1.read_from(instream)
        names.append(bytes(fontRsrcName))
        rsrc_rcds.append(rcd1)
    resources = []
    for rcd in rsrc_rcds:
        instream.seek(4 + 2*(rcd.fontResourceStart + header.headerLength))
        resources.append(
            instream.read(2*(rcd.fontResourceEnd - rcd.fontResourceStart))
        )
    fonts = []
    for name, data in zip(names, resources):
        try:
            fontdata = extract_nfnt(data, 0)
            font = convert_nfnt({}, **fontdata)
            font = font.modify(
                name=name.decode('mac-roman'),
                source_format=f'[Lisa] {font.source_format}',
            )
            fonts.append(font)
        except (ValueError, FileFormatError):
            pass
    return fonts
