"""
monobit.storage.formats.wsfont - NetBSD wsfont binaries and C headers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Glyph, Font
from monobit.base import Props, reverse_dict
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv
from monobit.encoding import EncodingName

from monobit.storage.utils.source import CCodeReader, CCodeWriter
from monobit.storage.utils.limitations import ensure_single, make_contiguous, ensure_charcell

from .raw import load_bitmap, save_bitmap


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
    # should be strike width given in bytes
    # but in NetBSD kernel header files this is *sometimes* the pixel width
    # so the field may well be ignored by the kernel
    stride='uint32',
    bitorder='uint32',
    byteorder='uint32',
)

#define WSDISPLAY_FONTORDER_KNOWN 0     /* i.e, no need to convert */
#define WSDISPLAY_FONTORDER_L2R 1
#define WSDISPLAY_FONTORDER_R2L 2
_WSF_ORDER = {
    0: 'left',
    1: 'left',
    2: 'right',
}


# > ISO-8859-1 encoding
#define WSDISPLAY_FONTENC_ISO 0
# > IBM CP437 encoding
#define WSDISPLAY_FONTENC_IBM 1
# > the custom encoding of the supplemental
# > fonts which came with the BSD ``pcvt'' console driver
#define WSDISPLAY_FONTENC_PCVT 2
# > ISO-8859-7 (Greek) encoding
#define WSDISPLAY_FONTENC_ISO7 3 /* greek */
# > ISO-8859-2 (Eastern European) encoding
#define WSDISPLAY_FONTENC_ISO2 4 /* east european */
# > KOI8-R (Russian) encoding
#define WSDISPLAY_FONTENC_KOI8_R 5 /* russian */
_WSF_ENCODING = {
    0: EncodingName('iso-8859-1'),
    1: EncodingName('cp437'),
    2: None,
    3: EncodingName('iso-8859-7'),
    4: EncodingName('iso-8859-2'),
    5: EncodingName('koi8-r'),
}
_TO_WSF_ENCODING = reverse_dict(_WSF_ENCODING)



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
def load_netbsd(instream):
    """Load font from NetBSD wsfont C header."""
    instream = instream.text
    identifier = ''
    data = {}
    headers = []
    for line in instream:
        line = CCodeReader.strip_line_comments(line, instream)
        if CCodeReader.assign in line:
            identifier, _, _ = line.partition(CCodeReader.assign)
            logging.debug('Found assignment to `%s`', identifier)
            if _KEY_TYPE in identifier:
                headers.append(_read_header(line, instream))
            elif CCodeReader.delimiters[0] in line:
                identifier = CCodeReader.clean_identifier(identifier)
                coded_data = CCodeReader.read_array(instream, line)
                data[identifier] = CCodeReader.decode_array(coded_data)
    return tuple(
        load_wsfont_bitmap(BytesIO(data[_header.data]), _header)
        for _header in headers
    )


def _read_header(line, instream):
    """Read the wsfont header from a c file."""
    headerlist = CCodeReader.read_array(instream, line)
    header = CCodeReader.decode_struct(headerlist, _HEADER_FIELDS)
    header.name = header.name.strip('"').encode('ascii', 'replace')
    header.firstchar = CCodeReader.decode_int(header.firstchar)
    # ignore numchars - it is often an expression
    # and we can work it out anyway
    header.numchars = None
    header.fontwidth = CCodeReader.decode_int(header.fontwidth)
    header.fontheight = CCodeReader.decode_int(header.fontheight)
    header.stride = CCodeReader.decode_int(header.stride)
    try:
        header.encoding = _ENCODING_CONST[header.encoding]
    except KeyError:
        header.encoding = CCodeReader.decode_int(header.encoding)
    try:
        header.bitorder = _ORDER_CONST[header.bitorder]
    except KeyError:
        header.bitorder = CCodeReader.decode_int(header.bitorder)
    try:
        header.byteorder = _ORDER_CONST[header.byteorder]
    except KeyError:
        header.byteorder = CCodeReader.decode_int(header.byteorder)
    return header


@savers.register(linked=load_netbsd)
def save_netbsd(
        fonts, outstream, *,
        byte_order:str=None,
        bit_order:str='left',
        add_visuals:bool=True,
    ):
    """
    Save to a NetBSD wsfont header.

    bit_order: 'left' for most significant bit left (default), or 'right'
    byte_order: 'left' or 'right'; default: same as bit-order
    add_visuals: add comments with visual representation of glyphs (default: True)
    """
    for font in fonts:
        _write_netbsd(font, outstream, byte_order, bit_order, add_visuals)


def _write_netbsd(font, outstream, byte_order, bit_order, add_visuals):
    """Write single NetBSD wsfont header."""
    identifier = CCodeWriter.to_identifier(font.name)
    header, data = convert_to_wsfont(font, byte_order, bit_order)
    header = Props(**vars(header))
    header.name = '"' + header.name.decode('ascii', 'replace') + '"'
    header.data = f'{identifier}_data'
    header.encoding = reverse_dict(_ENCODING_CONST)[header.encoding]
    header.bitorder = reverse_dict(_ORDER_CONST)[header.bitorder]
    header.byteorder = reverse_dict(_ORDER_CONST)[header.byteorder]
    headerstr = CCodeWriter.encode_struct(header, _HEADER_FIELDS)
    if add_visuals:
        arraystr = CCodeWriter.encode_array(
            data, bytes_per_line=header.stride,
            lines_per_block=header.fontheight,
            add_visuals=True, index=header.firstchar,
        )
    else:
        # compact format
        arraystr = CCodeWriter.encode_array(
            data, bytes_per_line=header.stride * header.fontheight,
        )
    outstream = outstream.text
    outstream.write('\n\n')
    if font.get_comment():
        outstream.write(f'/*\n{font.get_comment()}\n*/\n\n')
    outstream.write(f'static u_char {header.data}[];\n\n')
    outstream.write(f'struct wsdisplay_font {identifier} = {headerstr};\n\n')
    outstream.write(f'static u_char {header.data}[] = {arraystr};\n')


###############################################################################

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
    return load_wsfont_bitmap(instream, header)


def load_wsfont_bitmap(instream, header):
    """Load bitmap font with geometry defined by wsfont header."""
    # if header.stride == header.fontwidth:
    #     header.stride = ceildiv(header.fontwidth, 8)
    font = load_bitmap(
        instream,
        width=header.fontwidth, height=header.fontheight,
        count=header.numchars,
        align=_WSF_ORDER[header.bitorder],
        strike_bytes=header.stride,
        strike_count=1,
        first_codepoint=header.firstchar,
        msb=_WSF_ORDER[header.bitorder],
        byte_swap=(
            header.stride
            if header.byteorder and header.byteorder != header.bitorder
            else 0
        ),
    )
    encoding = _WSF_ENCODING.get(header.encoding, '')
    if encoding:
        font = font.label(char_from=encoding)
    font = font.modify(name=header.name.decode('ascii', 'replace'))
    return font


@savers.register(linked=load_wsfont)
def save_wsfont(
        fonts, outstream, *,
        byte_order:str=None,
        bit_order:str='left',
    ):
    """
    Save to a wsfont .wsf font.

    bit_order: 'left' for most significant bit left (default), or 'right'
    byte_order: 'left' or 'right'; default: same as bit-order
    """
    font = ensure_single(fonts)
    header, data = convert_to_wsfont(font, byte_order, bit_order)
    outstream.write(bytes(header))
    outstream.write(data)


def convert_to_wsfont(font, byte_order, bit_order):
    if not byte_order:
        byte_order = bit_order
    font = ensure_charcell(font)
    if font.encoding not in _TO_WSF_ENCODING and font.get_chars():
        # standard encoding is latin-1 in this format
        font = font.label(codepoint_from='latin-1', overwrite=True)
    font = make_contiguous(font, missing='space')
    codepoints = font.get_codepoints()
    if not codepoints:
        raise ValueError('No storable codepoints found in font.')
    header = _WSF_HEADER(
        magic=_WSF_MAGIC,
        name=font.name.encode('ascii', 'replace'),
        firstchar=min(int(_cp) for _cp in codepoints),
        numchars=len(codepoints),
        encoding=_TO_WSF_ENCODING.get(font.encoding, 0),
        fontwidth=font.cell_size.x,
        fontheight=font.cell_size.y,
        stride=ceildiv(font.cell_size.x, 8),
        bitorder=2 if bit_order.startswith('r') else 1,
        byteorder=2 if byte_order.startswith('r') else 1,
    )
    stream = BytesIO()
    save_bitmap(
        stream, font,
        align=bit_order, msb=bit_order,
        byte_swap=(header.stride if byte_order != bit_order else 0),
    )
    return header, stream.getvalue()
