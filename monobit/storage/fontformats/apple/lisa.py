"""
monobit.storage.fontformats.apple.lisa - Apple Lisa fonts

(c) 2023--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be
from monobit.base.binary import align
from monobit.base import FileFormatError, UnsupportedError
from monobit.storage import loaders, savers

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


@loaders.register(name='lisa')
def load_lisa(instream):
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
    fonts = []
    for num, (name, rcd) in enumerate(zip(names, rsrc_rcds)):
        name = name.decode('mac-roman')
        loc = 4 + 2*(rcd.fontResourceStart + header.headerLength)
        size = 2*(rcd.fontResourceEnd - rcd.fontResourceStart)
        instream.seek(loc)
        magic = instream.peek(2)[:2]
        is_bitfont = magic[0] & 0x80
        if is_bitfont:
            act = "Reading"
        else:
            act = "Skipping"
        logging.debug(
            "%s resource #%d at offset 0x%x: name '%s' font-type %s size 0x%x",
            act, num, loc, name, magic.hex(), size
        )
        if not is_bitfont:
            continue
        try:
            fontdata = extract_nfnt(instream)
        except (FileFormatError, UnsupportedError, ValueError) as e:
            logging.warning("Could not load resource '%s': %s", name, e)
            continue
        font = convert_nfnt(**fontdata)
        font = font.modify(
            name=name, source_format=f'[Lisa] {font.source_format}',
        )
        fonts.append(font)
    return fonts
