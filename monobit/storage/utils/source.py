"""
monobit.storage.utils.source - utilities for reading and writing source code

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import re
import string
from itertools import zip_longest, cycle, chain

from monobit.base import Props
from monobit.core import Raster


class CodeReader:

    @classmethod
    def strip_line_comments(cls, line, instream):
        """Strip comments. Handles inline but not multiline block comments."""
        if cls.comment:
            line, _, _ = line.partition(cls.comment)
        if cls.block_comment:
            start, end = cls.block_comment
            closed = True
            while start in line:
                before, _, after = line.partition(start)
                _, closed, after = after.partition(end)
                line = before + after
            if not closed:
                for new_line in instream:
                    _, closed, after = new_line.partition(end)
                    if closed:
                        line += after
                        break
        line = line.strip(' \r\n\t')
        return line

    @classmethod
    def read_array(cls, instream, line):
        """Retrieve coded array as list of strings. Flattens nested arrays."""
        start, end = cls.delimiters
        depth = 0
        coded_data = []
        for line in chain((line,), instream):
            line = cls.strip_line_comments(line, instream)
            while start in line:
                pre, line = line.split(start, 1)
                if depth:
                    line = pre + line
                depth += 1
            while end in line:
                line, post = line.split(end, 1)
                depth = max(depth - 1, 0)
                if depth:
                    line += post
            coded_data.append(line)
            if not depth:
                break
        return ''.join(coded_data).split(',')

    @classmethod
    def decode_array(cls, coded_data):
        """Decode coded array to bytes."""
        try:
            return bytes(cls.decode_int(_s) for _s in coded_data if _s.strip())
        except ValueError:
            return b''

    @classmethod
    def clean_identifier(cls, identifier):
        """Clean up identifier found in source code."""
        # take last element separated by whitespace e.g. char foo[123] -> foo[123]
        *_, identifier = identifier.strip().split()
        # strip non-alnum at either end (e.g. "abc" -> abc)s
        identifier = re.sub(r"^\W+|\W+$", "", identifier)
        # take first alphanum part (e.g. name[123 -> name)
        identifier, *_ = re.split(r"\W+", identifier)
        return identifier


###############################################################################
# helper functions for writer

class CodeWriter:

    @classmethod
    def to_identifier(cls, identifier):
        """Convert name to C identifier."""
        identifier = ''.join(_c.lower() if _c.isalnum() else '_' for _c in identifier)
        if not identifier[:1].isalpha():
            identifier = 'data_' + identifier
        return identifier

    @classmethod
    def encode_array(
            cls, data, bytes_per_line, lines_per_block=0, add_visuals=False,
            index=None,
        ):
        """Encode bytes to array."""
        start_delimiter, end_delimiter = cls.delimiters
        outstrs = []
        # emit code
        outstrs.append(f'{start_delimiter}\n')
        # grouper
        args = [iter(data)] * bytes_per_line
        groups = list(zip(*args))
        lines = [
            ', '.join(cls.encode_int(_b) for _b in _group)
            for _group in groups
        ]
        if add_visuals and cls.block_comment:
            visuals = [
                Raster
                    .from_bytes(_group, height=1)
                    .as_text(
                        start=cls.block_comment[0] + ' ',
                        end=' ' + cls.block_comment[1],
                    )
                for _group in groups
            ]
        else:
            visuals = []
        rem = len(data) % bytes_per_line
        if rem:
            lines.append(', '.join(
                cls.encode_int(_b) for _b in data[-rem:])
            )
        for i, (line, visual) in enumerate(zip_longest(lines, visuals)):
            if lines_per_block:
                if (i % lines_per_block == 0):
                    # if i:
                    outstrs.append('\n')
                    if index is not None:
                        outstrs.append(
                            cls.indent + cls.block_comment[0] + ' '
                            + cls.encode_int(index+i//lines_per_block)
                            + ' ' + cls.block_comment[1] + '\n'
                        )
            outstrs.append(f'{cls.indent}{line}')
            if i < len(lines) - 1:
                outstrs.append(',')
            if add_visuals:
                outstrs.append(f'{cls.indent}{visual}')
            outstrs.append('\n')
        outstrs.append(end_delimiter)
        return ''.join(outstrs)


###############################################################################
# C

class CCode:
    """C source code."""
    delimiters = '{}'
    comment = '//'
    assign = '='
    block_comment = ('/*', '*/')
    separator = ';\n\n'

    indent = '\t'
    assign_template = 'char {identifier}[{bytesize}] = '
    pre = ''
    post = separator


class CCodeReader(CodeReader, CCode):

    @classmethod
    def decode_int(cls, cvalue):
        """Parse integer from C/Python/JS code."""
        cvalue = cvalue.strip()
        # char value is also int in C
        if len(cvalue) == 3 and cvalue[0] == cvalue[-1] == "'":
            return ord(cvalue[1])
        # C suffixes
        while cvalue[-1:].lower() in ('u', 'l'):
            cvalue = cvalue[:-1]
        if cvalue.startswith('0') and cvalue[1:2] and cvalue[1:2] in string.digits:
            # C / Python-2 octal 0777
            cvalue = '0o' + cvalue[1:]
        # 0x, 0b, decimals - like Python
        return int(cvalue, 0)

    @classmethod
    def decode_struct(cls, coded_data, fields):
        """Decode struct value from list."""
        return Props(**{
            # may be `.name = 0` or just `0`
            _key: _field.rpartition(cls.assign)[-1].strip()
            for _key, _field in zip(fields, coded_data)
        })

    @classmethod
    def decode_struct_array(cls, coded_data, fields):
        """Decode struct value from list."""
        array_len = len(coded_data) // len(fields)
        iterators = [iter(coded_data)] * len(fields)
        return tuple(
            Props(**{
                _key: _field.rpartition(cls.assign)[-1].strip()
                for _key, _field in zip(fields, _chunk)
            })
            for _chunk in zip(*iterators)
        )


class CCodeWriter(CodeWriter, CCode):

    @classmethod
    def encode_int(cls, value):
        """Output hex number in C format."""
        return f'0x{value:02x}'

    @classmethod
    def encode_struct(cls, header, fields=(), compact=False, show_names=True):
        """Encode namespace class as struct."""
        if fields:
            header_dict = {
                _name: getattr(header, _name)
                for _name in fields
            }
        else:
            header_dict = vars(header)
        if compact:
            joiner = ', '
            start, end = cls.delimiters
            indent = ''
        else:
            joiner = ',\n'
            start, end = cls.delimiters[0] + '\n', '\n' + cls.delimiters[1]
            indent = cls.indent
        if show_names:
            # format with explicit member names
            data = joiner.join(
                f'{indent}.{_name} = {_value}'
                for _name, _value in header_dict.items()
            )
            return start + data + end
        else:
            data = joiner.join(
                f'{indent}{_value}'
                for _name, _value in header_dict.items()
            )
            return start + data + end




###############################################################################
# JSON

class JSONCode:
    """JSON code."""
    delimiters = '[]'
    comment = '//'
    # JSON separator should only be written *between* multiple entries
    separator = ',\n\n'
    assign = ':'
    block_comment = ()

    indent = ' ' * 2
    assign_template = '"{identifier}": '
    pre = '{\n'
    post = '\n}\n'


class JSONCodeReader(CodeReader, JSONCode):
    decode_int = CCodeReader.decode_int

class JSONCodeWriter(CodeWriter, JSONCode):
    encode_int = CCodeWriter.encode_int


###############################################################################
# Python

class PythonCode:
    """Python source code, using lists."""
    delimiters = '[]'
    comment = '#'
    assign = '='
    block_comment = ()
    separator = '\n\n'

    indent = ' ' * 4
    assign_template = '{identifier} = '
    pre = ''
    post = separator

class PythonTupleCode(PythonCode):
    """Python source code, using tuples."""
    delimiters = '()'


class PythonCodeReader(CodeReader, PythonCode):
    # Python and C notations are not quite the same but this works
    decode_int = CCodeReader.decode_int

class PythonCodeWriter(CodeWriter, PythonCode):
    encode_int = CCodeWriter.encode_int

class PythonTupleCodeReader(CodeReader, PythonTupleCode):
    decode_int = CCodeReader.decode_int

class PythonTupleCodeWriter(CodeWriter, PythonTupleCode):
    encode_int = CCodeWriter.encode_int


###############################################################################
# Pascal

class PascalCode:
    """Pascal source code wrapper."""
    delimiters = '()'
    # pascal has block comments only
    comment = ''
    assign = '='
    block_comment = ('{','}')
    separator = ';\n\n'

    indent = ' ' * 2
    assign_template = '{identifier}: Array[1..{bytesize}] of Integer = '
    pre = 'const\n\n'
    post = separator


class PascalCodeReader(CodeReader, PascalCode):

    @classmethod
    def decode_int(cls, cvalue):
        """Parse integer from Pascal code."""
        cvalue = cvalue.strip()
        if cvalue.startswith('#'):
            # char literal
            return int(cvalue[1:], 10)
        if cvalue.startswith('$'):
            return int(cvalue[1:], 16)


class PascalCodeWriter(CodeWriter, PascalCode):

    @classmethod
    def encode_int(cls, value):
        """Output hex number in Pascal format."""
        return f'${value:02x}'
