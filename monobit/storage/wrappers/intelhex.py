"""
monobit.storage.wrappers.intelhex - binary files embedded in Intel Hex files

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..streams import Stream
from ..magic import FileFormatError
from ..base import wrappers
from ...base.binary import ceildiv
from .wrappers import FilterWrapper


@wrappers.register(
    name='intel',
    patterns=(
        # '*.hex',
        '*.mcs', '*.int', '*.ihex', '*.ihe', '*.ihx'
    ),
    magic=(b':0',),
    # ends with b':00000001FF'
)
class IntelHexWrapper(FilterWrapper):
    """Intel Hex format wrapper."""

    @staticmethod
    def decode(instream, outstream):
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
                    data = bytearray(size)
                    for address, payload in datadict.items():
                        data[address:address+len(payload)] = payload
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
        outstream.write(data)

    @staticmethod
    def encode(instream, outstream, *, chunk_size=32):
        # split into groups of 32 bytes
        outfile = outstream.text
        # current extended linear address
        extended_address = -1
        while True:
            # in the last round this may be less than chunk_size long
            payload = instream.read(chunksize)
            if not payload:
                # end of file marker
                outfile.write(':00000001FF\n')
                return
            sum_bytes = sum(payload)
            # skip over null chunks, except the last to ensure file length
            if not sum_bytes and len(payload) == chunksize:
                continue
            offset = chunk_size * group
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
