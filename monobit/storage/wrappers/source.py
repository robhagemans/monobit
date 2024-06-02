"""
monobit.storage.wrappers.source - binary files embedded in C/Python/JS source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import re
import string
import logging
from io import BytesIO
from pathlib import Path

from monobit.base.binary import ceildiv
from ..streams import Stream, KeepOpen
from ..magic import FileFormatError
from ..base import wrappers, containers
from .wrappers import Wrapper
from ..containers.containers import Archive


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

class _CodedBinaryWrapperBase(Archive):

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
        cls = type(self)
        # read & write
        self.delimiters = delimiters or cls.delimiters
        self.comment = comment or cls.comment
        # write
        self.assign_template = assign_template or cls.assign_template
        self.separator = separator or cls.separator
        self.final_separator = final_separator or cls.final_separator
        self.bytes_per_line = bytes_per_line or cls.bytes_per_line
        self.pre = pre or cls.pre
        self.post = post or cls.post
        # read
        self.block_comment = block_comment or cls.block_comment
        self.assign = assign or cls.assign
        self._wrapped_stream = stream
        self._coded_data = {}
        self._files = []
        super().__init__(mode)


    def close(self):
        """Close the archive, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            self._wrapped_stream.text.write(self.pre)
            for count, file in enumerate(self._files):
                self._write_out(file)
                file.close()
                if self.final_separator or count < len(self._files) - 1:
                    self._wrapped_stream.text.write(self.separator)
                self._wrapped_stream.text.write('\n\n')
            self._wrapped_stream.text.write(self.post)
        self._wrapped_stream.close()
        super().close()


    def is_dir(self, name):
        """Item at `name` is a directory."""
        return Path(name) == Path('.')

    def list(self):
        self._get_names_and_data()
        return self._coded_data.keys()

    def open(self, name, mode):
        """Open a binary stream in the container."""
        if mode == 'r':
            return self._open_read(name)
        else:
            return self._open_write(name)

    def _open_read(self, name):
        """Open input stream on source wrapper."""
        infile = self._wrapped_stream
        self._get_names_and_data()
        name = str(name)
        try:
            coded_data = self._coded_data[name]
        except KeyError:
            raise FileNotFoundError(
                f"No payload with identifier '{name}' found in file."
            )
        try:
            data = bytes(
                type(self).int_conv(_s)
                for _s in coded_data.split(',') if _s.strip()
            )
        except ValueError:
            raise FileFormatError(
                f"Could not convert coded data for identifier '{name}'"
            )
        return Stream.from_data(data, mode='r', name=name)

    def _get_names_and_data(self):
        """Find all identifiers with payload."""
        if self._coded_data:
            return
        if self.mode == 'w':
            return

        instream = self._wrapped_stream.text
        identifier = ''
        delimiters = self.delimiters
        comment = self.comment
        block_comment = self.block_comment
        assign = self.assign

        self._coded_data = {}
        start, end = delimiters
        found_identifier = ''
        for line in instream:
            line = _strip_line(line, comment, block_comment)
            if identifier in line and assign in line:
                if identifier:
                    _, _, line = line.partition(identifier)
                    found_identifier = identifier
                else:
                    found_identifier, _, _ = line.partition(assign)
                    logging.debug('Found assignement to `%s`', found_identifier)
                    # clean up identifier
                    # take last element separated by whitespace e.g. char foo[123] -> foo[123]
                    *_, found_identifier = found_identifier.strip().split()
                    # strip non-alnum at either end (e.g. "abc" -> abc)
                    found_identifier = re.sub(r"^\W+|\W+$", "", found_identifier)
                    # take first alphanum part (e.g. name[123 -> name)
                    found_identifier, *_ = re.split(r"\W+", found_identifier)
            if found_identifier and start in line:
                _, line = line.split(start)
                data = _get_payload(
                    instream, line, start, end, comment, block_comment
                )
                self._coded_data[found_identifier] = data

    def _open_write(self, name):
        """Open output stream on source wrapper."""
        newfile = Stream(KeepOpen(BytesIO()), mode='w', name=name)
        if name in self._files:
            logging.warning('Creating multiple files of the same name `%s`.', name)
        self._files.append(newfile)
        return newfile

    def _write_out(self, file):
        return _write_out_coded_binary(
            file.getvalue(),
            outstream=self._wrapped_stream,
            identifier=str(file.name),
            assign_template=self.assign_template,
            delimiters=self.delimiters,
            comment=self.comment,
            bytes_per_line=self.bytes_per_line,
            pre=self.pre,
            post=self.post,
        )


def _strip_line(line, comment, block_comment):
    if comment:
        line, _, _ = line.partition(comment)
    if block_comment:
        while block_comment[0] in line:
            before, _, after = line.partition(block_comment[0])
            _, _, after = after.partition(block_comment[1])
            line = before + after
    line = line.strip(' \r\n')
    return line


def _get_payload(instream, line, start, end, comment, block_comment):
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
    return ''.join(payload)


def _write_out_coded_binary(
        rawbytes, outstream, *,
        assign_template, delimiters, comment,
        bytes_per_line, pre, post, identifier='',
    ):
    """
    Generate font file encoded as source code.

    identifier: Identifier to use.
    assign_template: assignment operator. May include `identifier` and `bytesize` variable.
    delimiters: Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
    comment: Line comment character(s).
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

    # outstream.write('\n')


###############################################################################

class _CodedBinaryWrapper(_CodedBinaryWrapperBase):
    """Default parameters for coded binary."""
    delimiters = '{}'
    comment = '//'
    assign = '='
    int_conv = _int_from_c
    block_comment = ()
    separator = ''
    final_separator = True

    # writer parameters
    assign_template = None
    pre = ''
    post = ''


@containers.register(
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


@containers.register(
    name='json',
    patterns=('*.js', '*.json',),
)
class JSONCodedBinaryWrapper(_CodedBinaryWrapper):
    """JSON wrapper."""
    delimiters = '[]'
    comment = '//'
    # JSON separator should only be written *between* multiple entries
    separator = ','
    final_separator = False
    assign = ':'

    assign_template = '"{identifier}": '
    pre = '{\n'
    post = '}\n'


@containers.register(
    name='python',
    patterns=('*.py',),
)
class PythonCodedBinaryWrapper(_CodedBinaryWrapper):
    """Python source code wrapper, using lists."""
    delimiters = '[]'
    comment = '#'
    separator = ''

    assign_template = '{identifier} = '


@containers.register(
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

@containers.register(
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
