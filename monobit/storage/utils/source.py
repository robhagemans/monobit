"""
monobit.storage.utils.source - utilities for reading and writing source code

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import re
import string


###############################################################################
# helper functions for reader

def strip_line_comments(line, comment, block_comment):
    """Strip comments. Handles inline but not multiline block comments."""
    if comment:
        line, _, _ = line.partition(comment)
    if block_comment:
        while block_comment[0] in line:
            before, _, after = line.partition(block_comment[0])
            _, _, after = after.partition(block_comment[1])
            line = before + after
    line = line.strip(' \r\n\t')
    return line


def read_array(instream, line, start, end, comment, block_comment):
    """Retrieve coded array as list of strings."""
    # special case: whole array in one line
    if end in line:
        line, _ = line.split(end, 1)
        return line
    # multi-line array
    payload = [line]
    for line in instream:
        line = strip_line_comments(line, comment, block_comment)
        if start in line:
            _, line = line.split(start, 1)
        if end in line:
            line, _ = line.split(end, 1)
            payload.append(line)
            break
        if line:
            payload.append(line)
    return ''.join(payload).split(',')


def decode_array(payload, int_conv):
    """Decode coded array to bytes."""
    try:
        return bytes(
            int_conv(_s) for _s in payload if _s.strip()
        )
    except ValueError:
        return b''


def clean_identifier(found_identifier):
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

def to_identifier(identifier):
    """Convert name to C identifier."""
    return ''.join(_c.lower() if _c.isalnum() else '_' for _c in identifier)


def encode_array(rawbytes, delimiters, bytes_per_line, conv_int):
    """Encode bytes to array."""
    start_delimiter, end_delimiter = delimiters
    outstrs = []
    # emit code
    outstrs.append(f'{start_delimiter}\n')
    # grouper
    args = [iter(rawbytes)] * bytes_per_line
    groups = zip(*args)
    lines = [
        ', '.join(conv_int(_b) for _b in _group)
        for _group in groups
    ]
    rem = len(rawbytes) % bytes_per_line
    if rem:
        lines.append(', '.join(conv_int(_b) for _b in rawbytes[-rem:]))
    for i, line in enumerate(lines):
        outstrs.append(f'  {line}')
        if i < len(lines) - 1:
            outstrs.append(',')
        outstrs.append('\n')
    outstrs.append(end_delimiter)
    return ''.join(outstrs)


###############################################################################
# C

def int_from_c(cvalue):
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


def int_to_c(value):
    """Output hex number in C format."""
    return f'0x{value:02x}'


class CCode:
    """C source code."""
    delimiters = '{}'
    comment = '//'
    assign = '='
    int_conv = int_from_c
    conv_int = int_to_c
    block_comment = ('/*','*/')
    separator = ';\n\n'

    assign_template = 'char {identifier}[{bytesize}] = '
    pre = ''
    post = separator


###############################################################################
# JSON

class JSONCode:
    """JSON code."""
    delimiters = '[]'
    comment = '//'
    # JSON separator should only be written *between* multiple entries
    separator = ',\n\n'
    assign = ':'
    int_conv = int_from_c
    conv_int = int_to_c
    block_comment = ()

    assign_template = '"{identifier}": '
    pre = '{\n'
    post = '\n}\n'


###############################################################################
# Python

class PythonCode:
    """Python source code, using lists."""
    delimiters = '[]'
    comment = '#'
    assign = '='
    # Python and C nottations are not quite the same but this works
    int_conv = int_from_c
    conv_int = int_to_c
    block_comment = ()
    separator = '\n\n'

    assign_template = '{identifier} = '
    pre = ''
    post = separator


class PythonTupleCode:
    """Python source code, using tuples."""
    delimiters = '()'
    comment = '#'
    int_conv = int_from_c
    conv_int = int_to_c
    block_comment = ()
    separator = '\n\n'

    assign_template = '{identifier} = '
    pre = ''
    post = separator


###############################################################################
# Pascal

def int_from_pascal(cvalue):
    """Parse integer from Pascal code."""
    cvalue = cvalue.strip()
    if cvalue.startswith('#'):
        # char literal
        return int(cvalue[1:], 10)
    if cvalue.startswith('$'):
        return int(cvalue[1:], 16)

def int_to_pascal(value):
    """Output hex number in Pascal format."""
    return f'${value:02x}'


class PascalCode:
    """Pascal source code wrapper."""
    delimiters = '()'
    # pascal has block comments only
    comment = ''
    assign = '='
    block_comment = ('{','}')
    int_conv = int_from_pascal
    separator = ';\n\n'

    conv_int = int_to_pascal
    assign_template = '{identifier}: Array[1..{bytesize}] of Integer = '
    pre = 'const\n\n'
    post = separator
