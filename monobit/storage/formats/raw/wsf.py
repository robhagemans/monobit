"""
monobit.storage.formats.raw.wsf - BSD wsfont .wsf file

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap
from ..limitations import ensure_single


# https://ftp.iij.ad.jp/pub/NetBSD/NetBSD-release-10/xsrc/local/programs/bdfload/bdfload.c

_WSF_MAGIC = b'WSFT'

_WSF_HEADER = le.Struct(
    magic='4s',
    name='64s',
    firstchar='uint32',
    numchars='uint32',
    encoding='uint32',
    fontwidth='uint32',
    fontheight='uint32',
    stride='uint32',
    bitorder='uint32',
    byteorder='uint32',
)
#define WSDISPLAY_FONTENC_ISO 0
#define WSDISPLAY_FONTENC_IBM 1
#define WSDISPLAY_FONTENC_PCVT 2
#define WSDISPLAY_FONTENC_ISO7 3 /* greek */
#define WSDISPLAY_FONTENC_ISO2 4 /* east european */
#define WSDISPLAY_FONTENC_KOI8_R 5 /* russian */
#define WSDISPLAY_MAXFONTSZ     (512*1024)
#define WSDISPLAY_FONTORDER_KNOWN 0     /* i.e, no need to convert */
#define WSDISPLAY_FONTORDER_L2R 1
#define WSDISPLAY_FONTORDER_R2L 2

_WSF_ENCODING = {
    0: 'iso-8859-1',
    1: 'cp437',
    2: '',
    3: 'iso-8859-7',
    4: 'iso-8859-2',
    5: 'koi8-r',
}


@loaders.register(
    name='wsfont',
    magic=(_WSF_MAGIC,),
    patterns=('*.wsf',),
)
def load_wsfont(instream):
    """Load a wsfont .wsf font."""
    header = _WSF_HEADER.read_from(instream)
    if header.magic != _WSF_MAGIC:
        raise FileFormatError(
            f'Not a .wsf file: incorrect signature {header.magic}'
        )
    if header.stride == header.fontwidth:
        # should be given in bytes, but often this is the pixel width
        strike_bytes = -1
    else:
        strike_bytes = header.stride
    font = load_bitmap(
        instream,
        width=header.fontwidth, height=header.fontheight,
        count=header.numchars,
        # TODO: if byteorder and bitorder don't match
        align=('right' if header.bitorder == 2 else 'left'),
        strike_bytes=strike_bytes,
        first_codepoint=header.firstchar,
        msb=('right' if header.bitorder == 2 else 'left'),
    )
    encoding = _WSF_ENCODING.get(header.encoding, '')
    if encoding:
        font = font.label(char_from=encoding)
    return font
