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
from .wrappers import FilterWrapper
from ..containers.source import WrappedWriterStream


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
    def decode(instream):
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
                elif hexcode in ('02', '04'):
                    offset = int.from_bytes(payload, byteorder='big')
                elif hexcode in ('03', '05'):
                    pass
                else:
                    logging.warning(f'Ignoring unknown hex code {hexcode}.')
            except (IndexError, ValueError):
                raise FileFormatError('Malformed Intel Hex file.')
        return data
