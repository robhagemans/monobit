"""
monobit.storage.utils.source - utilities for reading and writing source code

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import re
import string

from monobit.base import Props


class CodeReader:

    @classmethod
    def strip_line_comments(cls, line):
        """Strip comments. Handles inline but not multiline block comments."""
        if cls.comment:
            line, _, _ = line.partition(cls.comment)
        if cls.block_comment:
            start, end = cls.block_comment
            while start in line:
                before, _, after = line.partition(start)
                _, _, after = after.partition(end)
                line = before + after
        line = line.strip(' \r\n\t')
        return line

    @classmethod
    def read_array(cls, instream, line):
        """Retrieve coded array as list of strings."""
        start, end = cls.delimiters
        # special case: whole array in one line
        if end in line:
            line, _ = line.split(end, 1)
            return line
        # multi-line array
        payload = [line]
        for line in instream:
            line = cls.strip_line_comments(line)
            if start in line:
                _, line = line.split(start, 1)
            if end in line:
                line, _ = line.split(end, 1)
                payload.append(line)
                break
            if line:
                payload.append(line)
        return ''.join(payload).split(',')

    @classmethod
    def decode_array(cls, payload):
        """Decode coded array to bytes."""
        try:
            return bytes(cls.decode_int(_s) for _s in payload if _s.strip())
        except ValueError:
            return b''

    @classmethod
    def clean_identifier(cls, found_identifier):
        """Clean up identifier found in source code."""
        # take last element separated by whitespace e.g. char foo[123] -> foo[123]
        *_, found_identifier = found_identifier.strip().split()
        # strip non-alnum at either end (e.g. "abc" -> abc)s
        found_identifier = re.sub(r"^\W+|\W+$", "", found_identifier)
        # take first alphanum part (e.g. name[123 -> name)
        found_identifier, *_ = re.split(r"\W+", found_identifier)
        return found_identifier


###############################################################################
# helper functions for writer

class CodeWriter:

    @classmethod
    def to_identifier(cls, identifier):
        """Convert name to C identifier."""
        return ''.join(_c.lower() if _c.isalnum() else '_' for _c in identifier)

    @classmethod
    def encode_array(cls, rawbytes, bytes_per_line):
        """Encode bytes to array."""
        start_delimiter, end_delimiter = cls.delimiters
        outstrs = []
        # emit code
        outstrs.append(f'{start_delimiter}\n')
        # grouper
        args = [iter(rawbytes)] * bytes_per_line
        groups = zip(*args)
        lines = [
            ', '.join(cls.encode_int(_b) for _b in _group)
            for _group in groups
        ]
        rem = len(rawbytes) % bytes_per_line
        if rem:
            lines.append(', '.join(
                cls.encode_int(_b) for _b in rawbytes[-rem:])
            )
        for i, line in enumerate(lines):
            outstrs.append(f'  {line}')
            if i < len(lines) - 1:
                outstrs.append(',')
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
    def decode_struct(cls, payload, fields):
        """Decode struct value from list."""
        return Props(**{
            # may be `.name = 0` or just `0`
            _key: _field.rpartition(cls.assign)[-1].strip()
            for _key, _field in zip(fields, payload)
        })


class CCodeWriter(CodeWriter, CCode):

    @classmethod
    def encode_int(cls, value):
        """Output hex number in C format."""
        return f'0x{value:02x}'

    @classmethod
    def encode_struct(cls, header, fields):
        """Encode namespace class as struct."""
        fields = ',\n'.join(
            f'\t.{_name} = {getattr(header, _name)}'
            for _name in fields
        )
        return '{\n' + fields + '\n}'




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
