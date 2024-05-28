"""
monobit.storage.wrappers.source - binary files embedded in C/Python/JS source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string
import logging
from io import BytesIO
from pathlib import Path

from monobit.base.binary import ceildiv
from ..streams import Stream, KeepOpen
from ..magic import FileFormatError
from ..holders import Wrapper
from ..base import wrappers


###############################################################################

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


def _int_from_pascal(cvalue):
    """Parse integer from Pascal code."""
    cvalue = cvalue.strip()
    if cvalue.startswith('#'):
        # char literal
        cvalue = cvalue[1:]
    if cvalue.startswith('$'):
        cvalue = '0x' + cvalue[1:]
    return int(cvalue, 0)


def _int_from_basic(cvalue):
    """Parse integer from BASIC code."""
    cvalue = cvalue.strip().lower()
    if cvalue.startswith('&h'):
        cvalue = '0x' + cvalue[2:]
    return int(cvalue, 0)


###############################################################################

class _CodedBinaryWrapperBase(Wrapper):

    def __init__(
            self, stream, mode='r',
            identifier:str='',
            delimiters:str='',
            comment:str='',
            # reader params
            block_comment:str='',
            assign:str='',
            # writer params
            assign_template:str='',
            separator:str='',
            bytes_per_line:int=16,
            pre:str='',
            post:str='',
        ):
        """
        Extract binary file encoded in source code.

        identifier: text at start of line where encoded file starts. (default: first array literal)
        delimiters: delimiter characters surrounding array definition. (use language default)
        comment: comment character. (use language default)
        block_comment: block comment character. (use language default)
        assign: assignment character. (use language default)
        separator: character separating statements. (use language default)
        assign_template: format of assignemnt statement, used on write. (use language default)
        bytes_per_line: number of bytes to write to one line. (default: 16)
        pre: characters needed at start of file. (use language default)
        post: characters needed at end of file. (use language default)
        """
        cls = type(self)
        # read & write
        self.identifier = identifier or 'font'
        self.delimiters = delimiters or cls.delimiters
        self.comment = comment or cls.comment
        # write
        self.assign_template = assign_template or cls.assign_template
        self.separator = separator or cls.separator
        self.bytes_per_line = bytes_per_line or cls.bytes_per_line
        self.pre = pre or cls.pre
        self.post = post or cls.post
        # read
        self.block_comment = block_comment or cls.block_comment
        self.assign = assign or cls.assign
        super().__init__(stream, mode)

    def open(self):
        if self.mode == 'r':
            self._unwrapped_stream = self._open_read()
        else:
            self._unwrapped_stream = self._open_write()
        return self._unwrapped_stream

    def _open_read(self):
        """Open input stream on source wrapper."""
        infile = self._wrapped_stream
        found_identifier, coded_data = self._get_payload(
            infile.text, identifier=self.identifier,
            delimiters=self.delimiters,
            comment=self.comment,
            block_comment=self.block_comment,
            assign=self.assign,
        )
        try:
            data = bytes(
                type(self).int_conv(_s)
                for _s in coded_data.split(',') if _s.strip()
            )
        except ValueError:
            raise FileFormatError(
                f'Could not convert coded data for identifier {found_identifier}'
            )
        # name = _remove_suffix(infile.name, Path(infile.name).suffix)
        name = found_identifier
        return Stream.from_data(data, mode='r', name=name)

    @staticmethod
    def _get_payload(
        instream, *, identifier,
        delimiters, comment, block_comment, assign,
    ):
        """Find the identifier and get the part between delimiters."""
        def _strip_line(line):
            if comment:
                line, _, _ = line.partition(comment)
            if block_comment:
                while block_comment[0] in line:
                    before, _, after = line.partition(block_comment[0])
                    _, _, after = after.partition(block_comment[1])
                    line = before + after
            line = line.strip(' \r\n')
            return line

        start, end = delimiters
        found_identifier = ''
        for line in instream:
            line = _strip_line(line)
            if identifier in line and assign in line:
                if identifier:
                    _, _, line = line.partition(identifier)
                    found_identifier = identifier
                else:
                    found_identifier, _, _ = line.partition(assign)
                    *_, found_identifier = found_identifier.strip().split()
            if found_identifier and start in line:
                _, line = line.split(start)
                break
        else:
            raise FileFormatError(
                f'No payload with identifier `{identifier}` found in file'
            )
        # special case: whole array in one line
        if end in line:
            line, _ = line.split(end, 1)
            return line
        # multi-line array
        payload = [line]
        for line in instream:
            line = _strip_line(line)
            if start in line:
                _, line = line.split(start, 1)
            if end in line:
                line, _ = line.split(end, 1)
                payload.append(line)
                break
            if line:
                payload.append(line)
        return found_identifier, ''.join(payload)

    def _open_write(self):
        """Open output stream on source wrapper."""
        outfile = self._wrapped_stream
        name = Path(outfile.name).stem
        return WrappedWriterStream(
            outfile,
            _write_out_coded_binary,
            name=name,
            identifier=self.identifier,
            assign_template=self.assign_template,
            delimiters=self.delimiters,
            comment=self.comment,
            separator=self.separator,
            bytes_per_line=self.bytes_per_line,
            pre=self.pre,
            post=self.post,
        )


def _write_out_coded_binary(
        rawbytes, outstream, *,
        assign_template, delimiters, comment, separator,
        bytes_per_line, pre, post, identifier='',
    ):
    """
    Generate font file encoded as source code.

    identifier: Identifier to use.
    assign_template: assignment operator. May include `identifier` and `bytesize` variable.
    delimiters: Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
    comment: Line comment character(s).
    separator: string to separate statements
    bytes_per_line: number of encoded bytes in a source line
    pre: string to write before output
    post: string to write after output
    """
    if len(delimiters) < 2:
        raise ValueError('A start and end delimiter must be given. E.g. []')
    start_delimiter = delimiters[0]
    end_delimiter = delimiters[1]
    outstream = outstream.text

    # remove non-ascii
    identifier = identifier.encode('ascii', 'ignore').decode('ascii')
    identifier = ''.join(_c if _c.isalnum() else '_' for _c in identifier)
    assign = assign_template.format(
        identifier=identifier, bytesize=len(rawbytes)
    )
    # emit code
    outstream.write(pre)
    outstream.write(f'{assign}{start_delimiter}\n')
    # grouper
    args = [iter(rawbytes)] * bytes_per_line
    groups = zip(*args)
    lines = [
        ', '.join(f'0x{_b:02x}' for _b in _group)
        for _group in groups
    ]
    rem = len(rawbytes) % bytes_per_line
    if rem:
        lines.append(', '.join(f'0x{_b:02x}' for _b in rawbytes[-rem:]))
    for i, line in enumerate(lines):
        outstream.write(f'  {line}')
        if i < len(lines) - 1:
            outstream.write(',')
        outstream.write('\n')
    outstream.write(end_delimiter)

    # C must have a separator at end of statement,
    # JSON must not have separator for last item in dict
    # outstream.write(separator)

    outstream.write('\n')
    outstream.write(post)


###############################################################################

class _CodedBinaryWrapper(_CodedBinaryWrapperBase):
    """Default parameters for coded binary."""
    delimiters = '{}'
    comment = '//'
    assign = '='
    int_conv = _int_from_c
    block_comment = ()
    separator = ''

    # writer parameters
    assign_template = None
    pre = ''
    post = ''


@wrappers.register(
    name='c',
    patterns=('*.c', '*.cc', '*.cpp', '*.h')
)
class CCodedBinaryWrapper(_CodedBinaryWrapper):
    """C source code wrapper."""
    delimiters = '{}'
    comment = '//'
    separator = ';'
    block_comment = ('/*','*/')

    assign_template = 'char {identifier}[{bytesize}] = '


@wrappers.register(
    name='json',
    patterns=('*.js', '*.json',),
)
class JSONCodedBinaryWrapper(_CodedBinaryWrapper):
    """JSON wrapper."""
    delimiters = '[]'
    comment = '//'
    # JSON separator should only be written *between* multiple entries
    # separator = ','
    assign = ':'

    assign_template = '"{identifier}": '
    pre = '{\n'
    post = '}\n'


@wrappers.register(
    name='python',
    patterns=('*.py',),
)
class PythonCodedBinaryWrapper(_CodedBinaryWrapper):
    """Python source code wrapper, using lists."""
    delimiters = '[]'
    comment = '#'
    separator = ''

    assign_template = '{identifier} = '


@wrappers.register(
    name='python-tuple',
    patterns=('*.py',),
)
class PythonTupleCodedBinaryWrapper(_CodedBinaryWrapper):
    """Python source code wrapper, using tuples."""
    delimiters = '()'
    comment = '#'
    separator = ''

    assign_template = '{identifier} = '


# writing not implemented for the below

@wrappers.register(
    name='pascal',
    patterns=('*.pas',),
)
class PascalCodedBinaryWrapper(_CodedBinaryWrapper):
    """Pascal source code wrapper."""
    delimiters = '()'
    # pascal has block comments only
    comment = ''
    block_comment = ('{','}')
    int_conv = _int_from_pascal
    separator = ';'


###############################################################################

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
        ', '.join(f'&h{_b:02x}' for _b in _group)
        for _group in groups
    ]
    rem = len(rawbytes) % bytes_per_line
    if rem:
        lines.append(', '.join(f'&h{_b:02x}' for _b in rawbytes[-rem:]))
    if line_number_start is not None and line_number_start >= 0:
        line_number = line_number_start
    else:
        line_number = None
    for line in lines:
        if line_number is not None:
            outfile.write(f'{line_number} ')
            line_number += line_number_inc
        outfile.write(f'DATA {line}\n')


###############################################################################

class WrappedWriterStream(Stream):

    def __init__(self, outfile, write_out, name='', **kwargs):
        bytesio = BytesIO()
        self._outfile = outfile
        self._write_out = write_out
        self._write_out_kwargs = kwargs
        super().__init__(bytesio, name=name, mode='w')

    def close(self):
        if not self.closed:
            rawbytes = bytes(self._stream.getbuffer())
            self._write_out(rawbytes, self._outfile, **self._write_out_kwargs)
        super().close()
