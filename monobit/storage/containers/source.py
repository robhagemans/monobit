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

from ..streams import Stream, KeepOpen
from ..magic import FileFormatError
from ..base import containers
from ..containers.containers import Archive


###############################################################################

class _CodedBinaryContainer(Archive):

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
        start, end = self.delimiters
        self._coded_data = {}
        found_identifier = ''
        for line in instream:
            line = _strip_line(line, self.comment, self.block_comment)
            if self.assign in line:
                found_identifier, _, _ = line.partition(self.assign)
                logging.debug('Found assignment to `%s`', found_identifier)
                found_identifier = _clean_identifier(found_identifier)
            if found_identifier and start in line:
                _, line = line.split(start)
                data = _get_payload(
                    instream, line, start, end, self.comment, self.block_comment
                )
                self._coded_data[found_identifier] = data
                found_identifier = ''

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
            conv_int=type(self).conv_int,
        )


###############################################################################
# reader

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
# writer

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


def _write_out_coded_binary(
        rawbytes, outstream, *,
        assign_template, delimiters, comment,
        bytes_per_line, pre, post, conv_int, identifier,
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
    conv_int: converter function for int values
    """
    if len(delimiters) < 2:
        raise ValueError('A start and end delimiter must be given. E.g. []')
    start_delimiter, end_delimiter = delimiters
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
class CCodedBinary(_CodedBinary):
    """C source code wrapper."""
    delimiters = '{}'
    comment = '//'
    separator = ';'
    block_comment = ('/*','*/')

    assign_template = 'char {identifier}[{bytesize}] = '


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
    separator = ','
    final_separator = False
    assign = ':'

    assign_template = '"{identifier}": '
    pre = '{\n'
    post = '}\n'


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
    separator = ''

    assign_template = '{identifier} = '


@containers.register(
    name='python-tuple',
    patterns=('*.py',),
)
class PythonTupleCodedBinary(_CodedBinary):
    """Python source code wrapper, using tuples."""
    delimiters = '()'
    comment = '#'
    separator = ''

    assign_template = '{identifier} = '


###############################################################################
# Pascal

def _int_from_pascal(cvalue):
    """Parse integer from Pascal code."""
    cvalue = cvalue.strip()
    if cvalue.startswith('#'):
        # char literal
        cvalue = cvalue[1:]
    if cvalue.startswith('$'):
        cvalue = '0x' + cvalue[1:]
    return int(cvalue, 0)


# writing not implemented for the below

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
    separator = ';'
