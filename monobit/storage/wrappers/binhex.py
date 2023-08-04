"""
monobit.storage.wrappers.binhex - BinHex containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from binascii import crc_hqx
from itertools import zip_longest

from monobit.storage import Stream
from monobit.storage import loaders, load_stream
from monobit.storage import FileFormatError, Magic
from monobit.base.struct import big_endian as be

from .apple import load_macforks


@loaders.register(
    name='binhex',
    magic=(
        b'(This file must be converted',
        b'\r(This file must be converted',
    ),
    patterns=('*.hqx',),
    wrapper=True,
)
def load_binhex(instream, format='', **kwargs):
    """BinHex 4.0 loader."""
    return load_macforks(_parse_binhex, instream, format, **kwargs)


###############################################################################
# BinHex 4.0 container
# https://files.stairways.com/other/binhex-40-specs-info.txt

_BINHEX_CODES = (
    '''!"#$%&'()*+,-012345689@ABCDEFGHIJKLMNPQRSTUVXYZ[`abcdefhijklmpqr'''
)
_BINHEX_CODEDICT = {_BINHEX_CODES[_i]: _i for _i in range(64)}

_BINHEX_HEADER = be.Struct(
    type='4s',
    auth='4s',
    flag='uint16',
    dlen='uint32',
    rlen='uint32',
)
_CRC = be.Struct(
    crc='uint16',
)

def _parse_binhex(stream):
    """Parse a BinHex 4.0 file."""
    front, binhex, *back = stream.text.read().split(':')
    if 'BinHex 4.0' not in front:
        logging.warning('No BinHex 4.0 signature found.')
    back = ''.join(back).strip()
    if back:
        logging.warning('Additional data found after BinHex section: %r', back)
    binhex = ''.join(binhex.split('\n'))
    # decode into 6-bit ints
    data = (_BINHEX_CODEDICT[_c] for _c in binhex)
    # convert to bit sequence
    bits = ''.join(bin(_d)[2:].zfill(6) for _d in data)
    # group into chunks of 8
    args = [iter(bits)] * 8
    octets = (''.join(_t) for _t in zip_longest(*args, fillvalue='0'))
    # convert to bytes
    bytestr = bytes(int(_s, 2) for _s in octets)
    # find run-length encoding marker
    chunks = bytestr.split(b'\x90')
    out = bytearray(chunks[0])
    for c in chunks[1:]:
        if c:
            # run-length byte
            repeat = c[0]
        else:
            # ...\x90\x90... -> ...', '', '...
            repeat = 0x90
        if not repeat:
            # zero-byte is placeholder for just 0x90
            out += b'\x90'
        else:
            # apply RLE. the last byte counts as the first of the run
            out += out[-1:] * (repeat-1)
        out += c[1:]
    # decode header
    length = out[0]
    name = bytes(out[1:1+length]).decode('mac-roman')
    if out[1+length] != 0:
        logging.warning('No null byte after name')
    header = _BINHEX_HEADER.from_bytes(out, 2+length)
    logging.debug(header)
    offset = 2 + length + _BINHEX_HEADER.size
    crc_header = out[:offset]
    hc = _CRC.from_bytes(out, offset)
    offset += _CRC.size
    if crc_hqx(crc_header, 0) != hc.crc:
        logging.error('CRC fault in header')
    data = out[offset:offset+header.dlen]
    offset += header.dlen
    dc = _CRC.from_bytes(out, offset)
    offset += _CRC.size
    rsrc = out[offset:offset+header.rlen]
    offset += header.rlen
    rc = _CRC.from_bytes(out, offset)
    if crc_hqx(data, 0) != dc.crc:
        logging.error('CRC fault in data fork')
    if crc_hqx(rsrc, 0) != rc.crc:
        logging.error('CRC fault in resource fork')
    return name, data, rsrc
