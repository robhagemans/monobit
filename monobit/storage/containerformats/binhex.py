"""
monobit.storage.containers.binhex - BinHex containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from binascii import crc_hqx
from itertools import zip_longest
from functools import partial

from monobit.base.struct import big_endian as be, little_endian as le
from ..streams import Stream
from ..magic import FileFormatError, Magic, Sentinel
from ..base import containers
from ..containers import FlatFilterContainer


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

def sixbitdecode(encoded, codedict, byteswap=False):
    """Deocde six-bit ascii representation into bytes."""
    # decode into 6-bit ints
    try:
        data = (codedict[_c] for _c in encoded)
    except KeyError as e:
        raise FileFormatError(f"Unexpected character '{e}' in encoding.") from e
    if byteswap:
        # reverse in groups of 4 code bytes, for binscii
        args = [iter(data)] * 4
        data = b''.join(bytearray(reversed(_chunk)) for _chunk in zip(*args))
    # convert to bit sequence
    bits = ''.join(bin(_d)[2:].zfill(6) for _d in data)
    # group into chunks of 8
    args = [iter(bits)] * 8
    octets = (''.join(_t) for _t in zip_longest(*args, fillvalue='0'))
    # convert to bytes
    bytestr = bytes(int(_s, 2) for _s in octets)
    return bytestr


@containers.register(
    name='binhex',
    magic=(
        b'(This file must be converted',
        b'\r(This file must be converted',
    ),
    patterns=('*.hqx',),
)
class BinHex(FlatFilterContainer):
    """BinHex 4.0 loader."""

    def decode(self, name):
        """
        Decode data and resource fork from BinHex container.
        """
        return super().decode(name)

    def encode(self, name):
        """
        Writing to BinHex is not supported.
        """
        raise ValueError(
            'Writing to BinHex is not supported.'
        )

    def decode_all(self, stream):
        """Parse a BinHex 4.0 file."""
        front, binhex, *back = stream.text.read().split(':')
        if 'BinHex 4.0' not in front:
            logging.warning('No BinHex 4.0 signature found.')
        back = ''.join(back).strip()
        if back:
            logging.warning('Additional data found after BinHex section: %r', back)
        binhex = ''.join(binhex.split('\n'))
        bytestr = sixbitdecode(binhex, _BINHEX_CODEDICT)
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
        if name:
            return {
                f'data/{name}': data,
                f'rsrc/{name}': rsrc,
            }
        else:
            return {
                f'data': data,
                f'rsrc': rsrc,
            }


###############################################################################
# BinSCII
# based on https://mirrors.apple2.org.za/ground.icaen.uiowa.edu/Mirrors/uni-kl/doc/binscii.format


_BINSCII_HEADER = le.Struct(
    # size fields are little-endian uint24, not supported by Struct
    filesize=be.uint8 * 3,
    segstart=be.uint8 * 3,
    acmode='byte',
    filetype='byte',
    auxtype='word',
    storetype='byte',
    blksize='word',
    credata='word',
    cretime='word',
    moddate='word',
    modtime='word',
    seglen=be.uint8 * 3,
    crc='word',
    filler='byte',
)

_BINSCII_SENTINEL = 'FiLeStArTfIlEsTaRt'


@containers.register(
    name='binscii',
    magic=(
        # this can occur on any line, probably not the first...
        Sentinel(_BINSCII_SENTINEL.encode('ascii')),
    ),
    patterns=('*.bsc', '*.bsq', '*.bns'),
)
class BinSCII(FlatFilterContainer):
    """BinSCII loader."""

    def decode(self, name):
        """
        Decode file from BinSCII container.
        """
        return super().decode(name)

    def encode(self, name):
        """
        Writing to BinSCII is not supported.
        """
        raise ValueError(
            'Writing to MacBinary is not supported.'
        )

    def decode_all(self, instream):
        """Parse a BinSCII file."""
        instream = instream.text
        output = {}
        while True:
            # locate binscii section sentinel
            for line in instream:
                if line.strip() == _BINSCII_SENTINEL:
                    break
            else:
                break
            # encoding alphabet
            encoding = instream.readline().strip()
            codedict = {_c: _i for _i, _c in enumerate(encoding)}
            # name and header
            metadata = instream.readline().strip()
            name_len = encoding.index(metadata[0]) + 1
            name = metadata[1:16]
            name = name[:name_len]
            binsciidecode = partial(sixbitdecode, codedict=codedict, byteswap=True)
            headerbytes = binsciidecode(metadata[16:16+36])
            header = _BINSCII_HEADER.from_bytes(headerbytes)
            # size fields are little-endian uint24, not supported by Struct
            filesize = int.from_bytes(header.filesize, 'little')
            segstart = int.from_bytes(header.segstart, 'little')
            seglen = int.from_bytes(header.seglen, 'little')
            logging.debug('binscii header: %s', header)
            logging.debug('filesize=%d segstart=%d seglen=%d', filesize, segstart, seglen)
            header_crc = crc_hqx(headerbytes[:-3], 0)
            if header_crc != header.crc:
                logging.warning(f"CRC failure while decoding '{name}'")
            # data section
            decoded = []
            crcline = ''
            for dataline in instream:
                dataline = dataline.strip()
                if len(dataline) != 64:
                    crcline = dataline
                    break
                decoded.append(binsciidecode(dataline))
            data = b''.join(decoded)
            crc_bytes = binsciidecode(crcline)
            crc_target = int.from_bytes(crc_bytes[:2], byteorder='little')
            if crc_hqx(data, 0) != crc_target:
                logging.warning(f"CRC failure while decoding '{name}'")
            if name not in output:
                output[name] = bytearray(filesize)
            output[name][segstart:segstart+seglen] = data
        if not output:
            raise FileFormatError(
                f"No BinSCII section found in file '{instream.name}'."
            )
        return output
