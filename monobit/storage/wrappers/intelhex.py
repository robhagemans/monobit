"""
monobit.storage.wrappers.intelhex - binary files embedded in Intel Hex files

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from io import BytesIO

from ..streams import Stream, DelayedWriterStream
from ..magic import FileFormatError
from ..base import encoders, decoders
from ...base.binary import ceildiv


@decoders.register(
    name='intel',
    patterns=(
        # '*.hex',
        '*.mcs', '*.int', '*.ihex', '*.ihe', '*.ihx'
    ),
    magic=(b':0',),
    # ends with b':00000001FF'
)
def decode_intel(instream):
    """Decode an intel hex-encoded stream."""
    infile = instream.text
    datadict = {}
    checksum = 0
    size = 0
    offset = 0
    for line in infile:
        _, _, dataline = line.partition(':')
        dataline = dataline.strip()
        if not dataline:
            continue
        try:
            databytes = int(dataline[:2], 16)
            address = offset + int.from_bytes(
                bytes.fromhex(dataline[2:6]),
                byteorder='big'
            )
            hexcode = dataline[6:8]
            checksum += int(dataline[-2:], 16)
            payload = bytes.fromhex(dataline[8:-2])
            if hexcode == '00':
                # data code
                if len(payload) != databytes:
                    logging.warning('Incorrect payload length.')
                datadict[address] = payload
                size = max(size, address+len(payload))
            elif hexcode == '01':
                # end of file code
                break
            elif hexcode == '02':
                # extended segment address
                offset = int.from_bytes(payload, byteorder='big') << 4
            elif hexcode == '04':
                # extended linear addresss
                offset = int.from_bytes(payload, byteorder='big') << 16
            elif hexcode in ('03', '05'):
                pass
            else:
                logging.warning(f'Ignoring unknown hex code {hexcode}.')
        except (IndexError, ValueError):
            raise FileFormatError('Malformed Intel Hex file.')
    data = bytearray(size)
    for address, payload in datadict.items():
        data[address:address+len(payload)] = payload
    name = Path(instream.name).stem
    return Stream.from_data(data, mode='r', name=name)


@encoders.register(linked=decode_intel)
def _encode_intel(outstream, *, chunk_size:int=32):
    """
    Decode an intel hex-encoded stream.

    chunk_size: byte count of a hex record line
    """
    encode_func = _do_encode_intel
    name = Path(outstream.name).stem
    return DelayedWriterStream(
        outstream, encode_func, name, chunk_size=chunk_size
    )


def _do_encode_intel(data, outstream, *, chunk_size):
    # split into groups of 32 bytes
    outfile = outstream.text
    # current extended linear address
    extended_address = -1
    offset = 0
    with BytesIO(data) as instream:
        while True:
            # in the last round this may be less than chunk_size long
            payload = instream.read(chunk_size)
            if not payload:
                # end of file marker
                outfile.write(':00000001FF\n')
                return
            sum_bytes = sum(payload)
            # skip over null chunks, except the last to ensure file length
            if not sum_bytes and len(payload) == chunksize:
                continue
            offset_hi, offset_lo = divmod(offset, 0x10000)
            if offset_hi > extended_address:
                extended_address = offset_hi
                ea_checksum = (
                    0x100 - sum(offset_hi.to_bytes(2, byteorder='big'))
                    - 0x02 - 0x04
                ) % 0x100
                outfile.write(f':02000004{offset_hi:04X}{ea_checksum:02X}\n')
            checksum = (
                0x100
                - sum_bytes - len(payload)
                - sum(offset_lo.to_bytes(2, byteorder='big'))
            ) % 0x100
            outfile.write(
                f':{len(payload):02X}{offset_lo:04X}00'
                f'{payload.hex().upper()}{checksum:02X}\n'
            )
            offset += chunk_size
