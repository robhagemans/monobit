"""
monobit.storage.wrappers.source - binary files embedded in BASIC source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..streams import Stream
from ..magic import FileFormatError
from ..base import wrappers
from .wrappers import Wrapper
from ..containers.source import WrappedWriterStream


###############################################################################
# BASIC

@wrappers.register(
    name='basic',
    patterns=('*.bas',),
)
class BASICCodedBinaryWrapper(Wrapper):
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
        self._line_number_start = line_number_start
        self._line_number_inc = line_number_inc
        self._bytes_per_line = bytes_per_line
        super().__init__(stream, mode)

    def open(self):
        if self.mode == 'r':
            self._unwrapped_stream = self._open_read()
        else:
            self._unwrapped_stream = self._open_write()
        return self._unwrapped_stream

    def _open_read(self):
        """
        Extract binary file encoded in DATA lines in classic BASIC source code.
        Tokenised BASIC files are not supported.
        """
        infile = self._wrapped_stream.text
        coded_data = []
        for line in infile:
            _, _, dataline = line.partition('DATA')
            dataline = dataline.strip()
            if not dataline:
                continue
            values = dataline.split(',')
            coded_data.extend(values)
        data = bytes(_int_from_basic(_s) for _s in coded_data)
        # clip off outer extension .bas
        name = _remove_suffix(infile.name, '.bas')
        return Stream.from_data(data, mode='r', name=name)

    def _open_write(self):
        """
        Write binary file encoded into DATA lines in classic BASIC source code.
        Tokenised BASIC files are not supported.
        """
        outfile = self._wrapped_stream.text
        # clip off outer extension .bas
        name = _remove_suffix(outfile.name, '.bas')
        return WrappedWriterStream(
            outfile, _write_out_basic, name=name,
            line_number_start= self._line_number_start,
            line_number_inc=self._line_number_inc,
            bytes_per_line=self._bytes_per_line,
        )


def _remove_suffix(oldname, suffix):
    """Case insensitive removesuffix"""
    if Path(oldname).suffix.lower() == suffix:
        return Path(oldname).stem
    return oldname


def _write_out_basic(
        rawbytes, outfile,
        *,
        line_number_start:int=1000,
        line_number_inc:int=10,
        bytes_per_line:int=8
    ):
    """Output raw btes encoded into BASIC-format file."""
    if (
            line_number_inc <= 0
            and line_number_start is not None and line_number_start > -1
        ):
        raise ValueError('line_number_inc must be > 0')
    # grouper
    args = [iter(rawbytes)] * bytes_per_line
    groups = zip(*args)
    lines = [
        ', '.join(_int_to_basic(_b) for _b in _group)
        for _group in groups
    ]
    rem = len(rawbytes) % bytes_per_line
    if rem:
        lines.append(', '.join(_int_to_basic(_b) for _b in rawbytes[-rem:]))
    if line_number_start is not None and line_number_start >= 0:
        line_number = line_number_start
    else:
        line_number = None
    for line in lines:
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
