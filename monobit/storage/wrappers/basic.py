"""
monobit.storage.wrappers.basic - binary files embedded in BASIC source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from io import BytesIO

from ..magic import FileFormatError
from ..base import encoders, decoders
from ..streams import Stream, DelayedWriterStream


@decoders.register(
    name='basic',
    patterns=('*.bas',),
)
def decode_basic(instream):
    """
    Extract binary file encoded in DATA lines in classic BASIC source code.
    Tokenised BASIC files are not supported.
    """
    infile = instream.text
    data = []
    for line in infile:
        _, _, dataline = line.partition('DATA')
        dataline = dataline.strip()
        if not dataline:
            continue
        values = dataline.split(',')
        data.append(bytes(_int_from_basic(_s) for _s in values))
    name = Path(instream.name).stem
    return Stream.from_data(b''.join(data), mode='r', name=name)


@encoders.register(linked=decode_basic)
def encode_basic(
        outstream,
        *,
        line_number_start:int=1000,
        line_number_inc:int=10,
        bytes_per_line:int=8
    ):
    """
    Write binary file encoded into DATA lines in classic BASIC source code.
    Tokenised BASIC files are not supported.

    line_number_start: line number of first DATA line (-1 for no line numbers; default: 1000)
    line_number_inc: increment between line numbers (default: 10)
    bytes_per_line: number of encoded bytes in a source line (default: 8)
    """
    encode_func = _do_encode_basic
    name = Path(outstream.name).stem
    return DelayedWriterStream(
        outstream, encode_func, name,
        line_number_start=line_number_start,
        line_number_inc=line_number_inc,
        bytes_per_line=bytes_per_line,
    )


def _do_encode_basic(
        data, outstream,
        *,
        line_number_start,
        line_number_inc,
        bytes_per_line,
    ):
    outfile = outstream.text
    if (
            line_number_inc <= 0
            and line_number_start is not None and line_number_start > -1
        ):
        raise ValueError('line_number_inc must be > 0')
    line_number = None
    if line_number_start is not None and line_number_start >= 0:
        line_number = line_number_start
    with BytesIO(data) as instream:
        while True:
            data = instream.read(bytes_per_line)
            if not data:
                return
            line = ', '.join(_int_to_basic(_b) for _b in data)
            if line_number is not None:
                outfile.write(f'{line_number} ')
                line_number += line_number_inc
            outfile.write(f'DATA {line}\n')


def _int_to_basic(value):
    """Output hex number in BASIC format."""
    return f'&h{value:02x}'


def _int_from_basic(cvalue):
    """Parse integer from BASIC code."""
    cvalue = cvalue.strip().lower()
    if cvalue.startswith('&h'):
        cvalue = '0x' + cvalue[2:]
    return int(cvalue, 0)
