"""
monobit.storage.formats.source - fonts embedded in C source files

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Glyph, Font
from monobit.base import Props

from ..containers.source import (
    CCodedBinary, strip_line_comments, read_array, decode_array, int_from_c,
    clean_identifier
)
from .raw.wsf import load_wsfont_bitmap


_KEY_TYPE = 'wsdisplay_font'

_HEADER_FIELDS = (
    'name', 'firstchar', 'numchars', 'encoding', 'fontwidth', 'fontheight', 'stride', 'bitorder', 'byteorder', 'data'
)

# constants from # https://ftp.iij.ad.jp/pub/NetBSD/NetBSD-release-10/xsrc/local/programs/bdfload/bdfload.c

_ORDER_CONST = {
    # /* i.e, no need to convert */
    # whatever that means
    'WSDISPLAY_FONTORDER_KNOWN': 0,
    'WSDISPLAY_FONTORDER_L2R': 1,
    'WSDISPLAY_FONTORDER_R2L': 2,
}

_ENCODING_CONST = {
    # > ISO-8859-1 encoding
    'WSDISPLAY_FONTENC_ISO': 0,
    # > IBM CP437 encoding
    'WSDISPLAY_FONTENC_IBM': 1,
    # > the custom encoding of the supplemental
    # > fonts which came with the BSD ``pcvt'' console driver
    'WSDISPLAY_FONTENC_PCVT': 2,
    # > ISO-8859-7 (Greek) encoding
    'WSDISPLAY_FONTENC_ISO7': 3,
    # > ISO-8859-2 (Eastern European) encoding
    'WSDISPLAY_FONTENC_ISO2': 4,
    # > KOI8-R (Russian) encoding
    'WSDISPLAY_FONTENC_KOI8_R': 5,
}


@loaders.register(
    name='netbsd',
    patterns=('*.h',),
)
def read_netbsd(instream):
    """Load font from NetBSD wsfont C header."""
    instream = instream.text
    start, end = CCodedBinary.delimiters
    found_identifier = ''
    data = {}
    header = None
    for line in instream:
        line = strip_line_comments(
            line, CCodedBinary.comment, CCodedBinary.block_comment
        )
        if CCodedBinary.assign in line:
            found_identifier, _, _ = line.partition(CCodedBinary.assign)
            logging.debug('Found assignment to `%s`', found_identifier)
            if _KEY_TYPE in found_identifier:
                header = _read_header(line, instream)
            elif start in line:
                found_identifier = clean_identifier(found_identifier)
                _, line = line.split(start)
                coded_data = read_array(
                    instream, line, start, end,
                    CCodedBinary.comment, CCodedBinary.block_comment
                )
                data[found_identifier] = decode_array(coded_data, int_from_c)
    stream = BytesIO(data[header.data])
    return load_wsfont_bitmap(stream, header)


def _read_header(line, instream):
    """Read the wsfont header from a c file."""
    start, end = CCodedBinary.delimiters
    _, line = line.split(start)
    headerlist = read_array(
        instream, line,
        start, end,
        comment=CCodedBinary.comment,
        block_comment=CCodedBinary.block_comment,
    )
    header = decode_struct(
        headerlist, CCodedBinary.assign, _HEADER_FIELDS
    )
    header.name = header.name.strip('"').encode('ascii', 'replace')
    header.firstchar = int_from_c(header.firstchar)
    # ignore numchars - it is often an expression
    # and we can work it out anyway
    header.numchars = None
    header.fontwidth = int_from_c(header.fontwidth)
    header.fontheight = int_from_c(header.fontheight)
    header.stride = int_from_c(header.stride)
    try:
        header.encoding = _ENCODING_CONST[header.encoding]
    except KeyError:
        header.encoding = int_from_c(header.encoding)
    try:
        header.bitorder = _ORDER_CONST[header.bitorder]
    except KeyError:
        header.bitorder = int_from_c(header.bitorder)
    try:
        header.byteorder = _ORDER_CONST[header.byteorder]
    except KeyError:
        header.byteorder = int_from_c(header.byteorder)
    return header


def decode_struct(payload, assign, fields):
    """Decode struct value from list."""
    return Props(**{
        _key: _field.rpartition(assign)[-1].strip()
        for _key, _field in zip(fields, payload)
    })
