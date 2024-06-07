"""
monobit.storage.containers.source - binary files embedded in C/Python/JS source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import re
import string
import logging
from pathlib import Path

from ..magic import FileFormatError
from ..base import containers
from ..containers.containers import FlatFilterContainer


class _CodedBinaryContainer(FlatFilterContainer):

    def __init__(
            self, stream, mode='r',
            delimiters:str='',
            comment:str='',
            # reader params
            block_comment:str='',
            assign:str='',
            # writer params
            assign_template:str='',
            separator:str='',
            final_separator:bool=None,
            bytes_per_line:int=16,
            pre:str='',
            post:str='',
        ):
        """
        Extract binary file encoded in source code.

        delimiters: delimiter characters surrounding array definition. (use language default)
        comment: comment character. (use language default)
        block_comment: block comment character. (use language default)
        assign: assignment character. (use language default)
        separator: character separating statements. (use language default)
        final_separator: separator is written on the last statement. (use language default)
        assign_template: format of assignemnt statement, used on write. (use language default)
        bytes_per_line: number of bytes to write to one line. (default: 16)
        pre: characters needed at start of file. (use language default)
        post: characters needed at end of file. (use language default)
        """
        super().__init__(stream, mode)
        cls = type(self)
        self.decode_kwargs = dict(
            delimiters=delimiters or cls.delimiters,
            comment=comment or cls.comment,
            block_comment=block_comment or cls.block_comment,
            assign=assign or cls.assign,
            int_conv=cls.int_conv,
        )
        self.encode_kwargs = dict(
            delimiters=delimiters or cls.delimiters,
            comment=comment or cls.comment,
            assign_template=assign_template or cls.assign_template,
            bytes_per_line=bytes_per_line or cls.bytes_per_line,
            conv_int=cls.conv_int,
            # container writer parameters
            separator=separator or cls.separator,
            pre=pre or cls.pre,
            post=post or cls.post,
        )

    ###########################################################################
    # reader

    @classmethod
    def decode_all(
            cls, instream, *,
            delimiters, comment, block_comment, assign, int_conv
        ):
        """Generator to decode all identifiers with payload."""
        instream = instream.text
        start, end = delimiters
        found_identifier = ''
        data = {}
        for line in instream:
            line = _strip_line(line, comment, block_comment)
            if assign in line:
                found_identifier, _, _ = line.partition(assign)
                logging.debug('Found assignment to `%s`', found_identifier)
                found_identifier = _clean_identifier(found_identifier)
            if found_identifier and start in line:
                _, line = line.split(start)
                data[found_identifier] = _get_payload(
                    instream, line, start, end,
                    comment, block_comment, int_conv
                )
                found_identifier = ''
        return data

    ###############################################################################
    # writer

    @classmethod
    def encode_all(
            cls, data, outstream, *,
            pre, separator, post,
            **kwargs
        ):
        outstream = outstream.text
        outstream.write(pre)
        for count, (name, filedata) in enumerate(data.items()):
            cls.encode(
                filedata,
                outstream=outstream,
                name=name,
                **kwargs
            )
            if count < len(data) - 1:
                outstream.write(separator)
        outstream.write(post)

    @classmethod
    def encode(
            cls, rawbytes, outstream, *, name,
            assign_template, delimiters, comment,
            bytes_per_line, conv_int,
        ):
        """
        Generate font file encoded as source code.

        name: Identifier to use.
        assign_template: assignment operator. May include `identifier` and `bytesize` variable.
        delimiters: Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
        comment: Line comment character(s).
        bytes_per_line: number of encoded bytes in a source line
        conv_int: converter function for int values
        """
        if len(delimiters) < 2:
            raise ValueError('A start and end delimiter must be given. E.g. []')
        start_delimiter, end_delimiter = delimiters
        # remove non-ascii
        identifier = name.encode('ascii', 'ignore').decode('ascii')
        identifier = ''.join(_c if _c.isalnum() else '_' for _c in identifier)
        assign = assign_template.format(
            identifier=identifier, bytesize=len(rawbytes)
        )
        # emit code
        outstream.write(f'{assign}{start_delimiter}\n')
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
            outstream.write(f'  {line}')
            if i < len(lines) - 1:
                outstream.write(',')
            outstream.write('\n')
        outstream.write(end_delimiter)


###############################################################################
# helper functions for reader

def _strip_line(line, comment, block_comment):
    """Strip comments. Handles inline but not multiline block comments."""
    if comment:
        line, _, _ = line.partition(comment)
    if block_comment:
        while block_comment[0] in line:
            before, _, after = line.partition(block_comment[0])
            _, _, after = after.partition(block_comment[1])
            line = before + after
    line = line.strip(' \r\n')
    return line


def _get_payload(instream, line, start, end, comment, block_comment, int_conv):
    """Retrieve coded array as string."""
    # special case: whole array in one line
    if end in line:
        line, _ = line.split(end, 1)
        return line
    # multi-line array
    payload = [line]
    for line in instream:
        line = _strip_line(line, comment, block_comment)
        if start in line:
            _, line = line.split(start, 1)
        if end in line:
            line, _ = line.split(end, 1)
            payload.append(line)
            break
        if line:
            payload.append(line)
    try:
        return bytes(
            int_conv(_s) for _s in ''.join(payload).split(',') if _s.strip()
        )
    except ValueError:
        logging.warning(
            f"Could not convert coded data for identifier '{name}'"
        )
        return b''


def _clean_identifier(found_identifier):
    """clean up identifier found in source code."""
    # take last element separated by whitespace e.g. char foo[123] -> foo[123]
    *_, found_identifier = found_identifier.strip().split()
    # strip non-alnum at either end (e.g. "abc" -> abc)s
    found_identifier = re.sub(r"^\W+|\W+$", "", found_identifier)
    # take first alphanum part (e.g. name[123 -> name)
    found_identifier, *_ = re.split(r"\W+", found_identifier)
    return found_identifier



###############################################################################
# C

def _int_from_c(cvalue):
    """Parse integer from C/Python/JS code."""
    cvalue = cvalue.strip()
    # C suffixes
    while cvalue[-1:].lower() in ('u', 'l'):
        cvalue = cvalue[:-1]
    if cvalue.startswith('0') and cvalue[1:2] and cvalue[1:2] in string.digits:
        # C / Python-2 octal 0777
        cvalue = '0o' + cvalue[1:]
    # 0x, 0b, decimals - like Python
    return int(cvalue, 0)

def _int_to_c(value):
    """Output hex number in C format."""
    return f'0x{value:02x}'


class _CodedBinary(_CodedBinaryContainer):
    """Default parameters for coded binary."""
    delimiters = '{}'
    comment = '//'
    assign = '='
    int_conv = _int_from_c
    conv_int = _int_to_c
    block_comment = ()
    separator = '\n\n'

    # writer parameters
    assign_template = None
    pre = ''
    post = separator


@containers.register(
    name='c',
    patterns=('*.c', '*.cc', '*.cpp', '*.h')
)
class CCodedBinary(_CodedBinary):
    """C source code wrapper."""
    delimiters = '{}'
    comment = '//'
    separator = ';\n\n'
    block_comment = ('/*','*/')

    assign_template = 'char {identifier}[{bytesize}] = '
    post = separator


###############################################################################
# JSON

@containers.register(
    name='json',
    patterns=('*.js', '*.json',),
)
class JSONCodedBinary(_CodedBinary):
    """JSON wrapper."""
    delimiters = '[]'
    comment = '//'
    # JSON separator should only be written *between* multiple entries
    separator = ',\n\n'
    assign = ':'

    assign_template = '"{identifier}": '
    pre = '{\n'
    post = '\n}\n'


###############################################################################
# Python

@containers.register(
    name='python',
    patterns=('*.py',),
)
class PythonCodedBinary(_CodedBinary):
    """Python source code wrapper, using lists."""
    delimiters = '[]'
    comment = '#'
    separator = '\n\n'

    assign_template = '{identifier} = '
    post = separator


@containers.register(
    name='python-tuple',
    patterns=('*.py',),
)
class PythonTupleCodedBinary(_CodedBinary):
    """Python source code wrapper, using tuples."""
    delimiters = '()'
    comment = '#'
    separator = '\n\n'

    assign_template = '{identifier} = '
    post = separator


###############################################################################
# Pascal

def _int_from_pascal(cvalue):
    """Parse integer from Pascal code."""
    cvalue = cvalue.strip()
    if cvalue.startswith('#'):
        # char literal
        return int(cvalue[1:], 10)
    if cvalue.startswith('$'):
        return int(cvalue[1:], 16)

def _int_to_pascal(value):
    """Output hex number in Pascal format."""
    return f'${value:02x}'


@containers.register(
    name='pascal',
    patterns=('*.pas',),
)
class PascalCodedBinary(_CodedBinary):
    """Pascal source code wrapper."""
    delimiters = '()'
    # pascal has block comments only
    comment = ''
    block_comment = ('{','}')
    int_conv = _int_from_pascal
    separator = ';\n\n'

    conv_int = _int_to_pascal
    assign_template = '{identifier}: Array[1..{bytesize}] of Integer = '
    pre = 'const\n\n'
    post = separator
