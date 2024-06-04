"""
monobit.storage.wrappers.source - binary files embedded in BASIC source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..magic import FileFormatError
from ..base import wrappers
from .wrappers import FilterWrapper


###############################################################################
# BASIC

@wrappers.register(
    name='basic',
    patterns=('*.bas',),
)
class BASICCodedBinaryWrapper(FilterWrapper):
    """BASIC source code wrapper, using DATA lines."""

    def __init__(
            self, stream, mode='r',
            *,
            line_number_start:int=1000,
            line_number_inc:int=10,
            bytes_per_line:int=8
        ):
        """
        Binary file encoded in DATA lines in classic BASIC source code. Options for save:

        line_number_start: line number of first DATA line (-1 for no line numbers; default: 1000)
        line_number_inc: increment between line numbers (default: 10)
        bytes_per_line: number of encoded bytes in a source line (default: 8)
        """
        self.encode_kwargs = dict(
            line_number_start=line_number_start,
            line_number_inc=line_number_inc,
            bytes_per_line=bytes_per_line,
        )
        super().__init__(stream, mode)

    @staticmethod
    def decode(instream, outstream):
        """
        Extract binary file encoded in DATA lines in classic BASIC source code.
        Tokenised BASIC files are not supported.
        """
        infile = instream.text
        for line in infile:
            _, _, dataline = line.partition('DATA')
            dataline = dataline.strip()
            if not dataline:
                continue
            values = dataline.split(',')
            data = bytes(_int_from_basic(_s) for _s in values)
            outstream.write(data)

    @staticmethod
    def encode(
            instream, outstream,
            *,
            line_number_start,
            line_number_inc,
            bytes_per_line,
        ):
        """
        Write binary file encoded into DATA lines in classic BASIC source code.
        Tokenised BASIC files are not supported.
        """
        outfile = outstream.text
        if (
                line_number_inc <= 0
                and line_number_start is not None and line_number_start > -1
            ):
            raise ValueError('line_number_inc must be > 0')
        line_number = None
        if line_number_start is not None and line_number_start >= 0:
            line_number = line_number_start
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
