"""
monobit.storage.containers.sourcecoded - binary files embedded in C/Python/JS source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string
import logging
from pathlib import Path

from ..magic import FileFormatError
from ..base import containers
from ..containers import SerialTextContainer
from ..utils.source import (
    CCodeReader, CCodeWriter, PythonCodeReader, PythonCodeWriter,
    PythonTupleCodeReader, PythonTupleCodeWriter,
    JSONCodeReader, JSONCodeWriter,
    PascalCodeReader, PascalCodeWriter,
)

class _CodedBinaryContainer(SerialTextContainer):

    def decode(self, name):
        """
        Decode files from source code file.
        """
        return super().decode(name)

    def encode(self, name, *, bytes_per_line:int=16):
        """
        Encode files to source code file.

        bytes_per_line: number of bytes to write to one line. (default: 16)
        """
        return super().encode(name, bytes_per_line=bytes_per_line)


    ###########################################################################
    # reader

    @classmethod
    def decode_all(cls, instream):
        """Generator to decode all identifiers with payload."""
        instream = instream.text
        start, end = cls.reader.delimiters
        identifier = ''
        data = {}
        for line in instream:
            line = cls.reader.strip_line_comments(line, instream)
            if cls.reader.assign in line:
                identifier, _, _ = line.partition(cls.reader.assign)
                logging.debug('Found assignment to `%s`', identifier)
                identifier = cls.reader.clean_identifier(identifier)
            if identifier and start in line:
                coded_data = cls.reader.read_array(instream, line)
                decoded_data = cls.reader.decode_array(coded_data)
                data[identifier] = decoded_data
                if not decoded_data:
                    logging.warning(
                        "Could not decode data for identifier '%s'",
                        identifier
                    )
                identifier = ''
        return data


    ###############################################################################
    # writer

    @classmethod
    def _head(cls):
        return cls.writer.pre

    @classmethod
    def _tail(cls):
        return cls.writer.post

    @classmethod
    def _separator(cls):
        return cls.writer.separator

    @classmethod
    def _encode(cls, name, rawbytes, outstream, *, bytes_per_line):
        # remove non-ascii
        identifier = name.encode('ascii', 'ignore').decode('ascii')
        identifier = cls.writer.to_identifier(identifier)
        assignment = cls.writer.assign_template.format(
            identifier=identifier, bytesize=len(rawbytes)
        )
        array = cls.writer.encode_array(rawbytes, bytes_per_line)
        outstream.write(assignment)
        outstream.write(array)


@containers.register(
    name='c',
    # don't provide patterns to avoid capturing other source-coded formats
    # patterns=('*.c', '*.cc', '*.cpp', '*.h')
)
class CCodedBinary(_CodedBinaryContainer):
    """C source code wrapper."""
    reader = CCodeReader
    writer = CCodeWriter


@containers.register(
    name='json',
    # patterns=('*.js', '*.json',),
)
class JSONCodedBinary(_CodedBinaryContainer):
    """JSON wrapper."""
    reader = JSONCodeReader
    writer = JSONCodeWriter


@containers.register(
    name='python',
    patterns=('*.py',),
)
class PythonCodedBinary(_CodedBinaryContainer):
    """Python source code wrapper, using lists."""
    reader = PythonCodeReader
    writer = PythonCodeWriter


@containers.register(
    name='python-tuple',
    # patterns=('*.py',),
)
class PythonTupleCodedBinary(_CodedBinaryContainer):
    """Python source code wrapper, using tuples."""
    reader = PythonTupleCodeReader
    writer = PythonTupleCodeWriter


@containers.register(
    name='pascal',
    # patterns=('*.pas',),
)
class PascalCodedBinary(_CodedBinaryContainer):
    """Pascal source code wrapper."""
    reader = PascalCodeReader
    writer = PascalCodeWriter
