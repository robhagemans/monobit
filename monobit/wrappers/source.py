"""
monobit.containers.source - fonts embedded in C/Python/JS source files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string
import logging
from io import BytesIO

from ..binary import ceildiv
from ..storage import loaders, savers, load_stream, save_stream
from ..streams import Stream
from ..font import Font
from ..glyph import Glyph
from ..magic import FileFormatError
from ..basetypes import Coord


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


_C_PARAMS = dict(
    delimiters='{}',
    comment='//',
    separator=';',
    block_comment=('/*','*/'),
)

_JS_PARAMS = dict(
    delimiters='[]',
    comment='//',
    separator=',',
)

_PY_PARAMS = dict(
    comment='#',
    separator='',
)

_PAS_PARAMS = dict(
    delimiters='()',
    # pascal has block comments only
    comment='',
    block_comment=('{','}'),
    int_conv=_int_from_pascal,
    separator=';',
)


###############################################################################


@loaders.register(
    name='c',
    patterns=('*.c', '*.cc', '*.cpp', '*.h'),
    wrapper=True,
)
def load_c(infile, *, identifier:str='', format='', **kwargs):
    """
    Extract font file encoded in C or C++ source code.

    identifier: text at start of line where encoded file starts. (default: first array literal {})
    """
    return _load_coded_binary(
        infile, identifier=identifier, format=format,
        **_C_PARAMS, **kwargs
    )


@loaders.register(
    name='json',
    patterns=('*.js', '*.json',),
    wrapper=True,
)
def load_json(infile, *, identifier:str='', format='', **kwargs):
    """
    Extract font file encoded in JSON dictionary.

    identifier: text at start of line where encoded file starts (default: first list [] in dict)
    """
    return _load_coded_binary(
        infile, identifier=identifier, format=format, assign=':',
        **_JS_PARAMS, **kwargs
    )


@loaders.register(
    name='python',
    patterns=('*.py',),
    wrapper=True
)
def load_python(infile, *, identifier:str='', format='', **kwargs):
    """
    Extract font file encoded as a list in Python source code.

    identifier: text at start of line where encoded file starts (default: first list [])
    """
    return _load_coded_binary(
        infile, identifier=identifier, format=format,
        delimiters='[]', **_PY_PARAMS, **kwargs
    )


@loaders.register(
    name='python-tuple',
    patterns=('*.py',),
    wrapper=True,
)
def load_python_tuple(infile, *, identifier:str='', format='', **kwargs):
    """
    Extract font file encoded as a list in Python source code.

    identifier: text at start of line where encoded file starts (default: first tuple)
    """
    return _load_coded_binary(
        infile, identifier=identifier, format=format,
        delimiters='()', **_PY_PARAMS, **kwargs
    )


@loaders.register(
    name='pascal',
    patterns=('*.pas',),
    wrapper=True,
)
def load_pascal(infile, *, identifier:str='', format='', **kwargs):
    """
    Extract font file encoded as a list in Pascal source code.

    identifier: text at start of line where encoded file starts (default: first array)
    """
    return _load_coded_binary(
        infile, identifier=identifier, format=format,
        **_PAS_PARAMS, **kwargs
    )


@loaders.register(name='source', wrapper=True)
def load_source(
        infile, *,
        identifier:str='', delimiters:str='{}', comment:str='//', assign:str='=',
        format='',
        **kwargs
    ):
    """
    Extract font file encoded in source code.

    identifier: text at start of line where encoded file starts (default: first delimiter)
    delimiters: pair of delimiters that enclose the file data (default: {})
    comment: string that introduces inline comment (default: //)
    """
    return _load_coded_binary(
        infile, identifier=identifier,
        delimiters=delimiters, comment=comment,
        format=format, assign=assign,
        **kwargs
    )


def _load_coded_binary(
        infile, *, identifier, delimiters, comment,
        assign='=', int_conv=_int_from_c,
        block_comment=(),
        # dummy for load; keep out of kwargs
        separator='',
        format='', **kwargs,
    ):
    """Load font from binary encoded in source code."""
    fonts = []
    while True:
        try:
            found_identifier, coded_data = _get_payload(
                infile.text, identifier, delimiters, comment, assign,
                block_comment=block_comment,
            )
        except FileFormatError as e:
            # raised at end of file
            break
        try:
            data = bytes(int_conv(_s) for _s in coded_data.split(',') if _s.strip())
        except ValueError:
            logging.warning(
                f'Could not convert coded data for identifier {found_identifier}'
            )
        try:
            with Stream.from_data(data, mode='r', name=found_identifier) as bytesio:
                fonts.extend(load_stream(bytesio, format=format, **kwargs))
        except FileFormatError as e:
            logging.debug(e)
            continue
    return fonts


def _get_payload(
        instream, identifier, delimiters, comment, assign, block_comment=()
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



@loaders.register(
    name='basic',
    patterns=('*.bas',),
    wrapper=True,
)
def load_basic(infile, *, format='raw', **kwargs):
    """
    Extract font file encoded in DATA lines in classic BASIC source code.
    Tokenised BASIC files are not supported.
    """
    infile = infile.text
    coded_data = []
    for line in infile:
        _, _, dataline = line.partition('DATA')
        dataline = dataline.strip()
        if not dataline:
            continue
        values = dataline.split(',')
        coded_data.extend(values)
    data = bytes(_int_from_basic(_s) for _s in coded_data)
    with Stream.from_data(data, mode='r') as bytesio:
        return load_stream(bytesio, format=format, **kwargs)


###############################################################################

@savers.register(linked=load_c, wrapper=True)
def save_c(
        fonts, outstream,
        bytes_per_line:int=16, distribute:bool=True,
        format='raw',
        **kwargs
    ):
    """
    Save to font file encoded in C source code.

    bytes_per_line: number of encoded bytes in a source line (default: 16)
    distribute: save each font as a separate identifier (default: True)
    """
    return _save_coded_binary(
        fonts, outstream, 'font_{name}', 'char {identifier}[{bytesize}] = ',
        format=format, bytes_per_line=bytes_per_line, distribute=distribute,
        **_C_PARAMS, **kwargs
    )


@savers.register(linked=load_python, wrapper=True)
def save_python(
        fonts, outstream,
        delimiters:str='[]',
        bytes_per_line:int=16, distribute:bool=True,
        format='raw',
        **kwargs
    ):
    """
    Save to font file encoded in Python source code.

    delimiters: pair of delimiters that enclose the file data (default: [])
    bytes_per_line: number of encoded bytes in a source line (default: 16)
    distribute: save each font as a separate identifier (default: True)
    """
    return _save_coded_binary(
        fonts, outstream, 'font_{name}', '{identifier} = ',
        format=format, bytes_per_line=bytes_per_line, distribute=distribute,
        delimiters=delimiters, **_PY_PARAMS, **kwargs
    )


@savers.register(linked=load_json, wrapper=True)
def save_json(
        fonts, outstream,
        bytes_per_line:int=16, distribute:bool=True,
        format='raw',
        **kwargs
    ):
    """
    Save to font file encoded in JSON code.

    bytes_per_line: number of encoded bytes in a source line (default: 16)
    distribute: save each font as a separate identifier (default: True)
    """
    outstream.text.write('{\n')
    fonts = _save_coded_binary(
        fonts, outstream, 'font_{name}', '"{identifier}": ',
        format=format, bytes_per_line=bytes_per_line, distribute=distribute,
        **_JS_PARAMS, **kwargs
    )
    outstream.text.write('}\n')


@savers.register(linked=load_source, wrapper=True)
def save_source(
        fonts, outstream, *,
        identifier:str, assign:str='=', delimiters:str='{}', comment:str='//',
        separator:str=';',
        bytes_per_line:int=16, distribute:bool=True,
        format='raw',
        **kwargs
    ):
    """
    Save to font file encoded in source code.

    identifier: text at start of line where file data starts (default: first delimiter)
    assign: assignment operator (default: =)
    delimiters: pair of delimiters that enclose the file data (default: {})
    comment: string that introduces inline comment (default: //)
    separator: string to separate statements (default: ;)
    bytes_per_line: number of encoded bytes in a source line (default: 16)
    distribute: save each font as a separate identifier (default: True)
    """
    return _save_coded_binary(
        fonts, outstream,
        identifier, f'{identifier} {assign} ', delimiters, comment,
        format=format, distribute=distribute, separator=separator,
        **kwargs
    )

def _save_coded_binary(
        fonts, outstream,
        identifier_template, assign_template, delimiters, comment, separator,
        # block_comment is unused in writer but specified in arguments for reader
        block_comment=None,
        bytes_per_line=16, format='raw', distribute=True, **kwargs
    ):
    """
    Generate font file encoded as source code.

    identifier_template: Template for the identifier. May include font properties.
    assign_template: assignment operator. May include `identifier` and `bytesize` variable.
    delimiters: Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
    comment: Line comment character(s).
    separator: string to separate statements
    bytes_per_line: number of encoded bytes in a source line
    distribute: save each font as a separate identifier (default: True)
    format: format of payload
    """
    if len(delimiters) < 2:
        raise ValueError('A start and end delimiter must be given. E.g. []')
    outstream = outstream.text
    start_delimiter = delimiters[0]
    end_delimiter = delimiters[1]
    if distribute:
        packs = tuple((_font,) for _font in fonts)
    else:
        packs = (fonts,)
    for count, fonts in enumerate(packs):
        # get the raw data
        bytesio = Stream(BytesIO(), mode='w')
        save_stream(fonts, bytesio, format=format, **kwargs)
        rawbytes = bytesio.getbuffer()
        # if multiple fonts, build the identifier from first font name
        identifier = fonts[0].format_properties(identifier_template)
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
        if count < len(packs) - 1:
            outstream.write(separator)
        outstream.write('\n')
    return fonts


@savers.register(linked=load_basic, wrapper=True)
def save_basic(
        fonts, outfile, *,
        line_number_start:int=1000, line_number_inc:int=10,
        bytes_per_line:int=8, format='raw',
        **kwargs
    ):
    """
    Save to font file encoded in DATA lines in classic BASIC source code.

    line_number_start: line number of first DATA line (-1 for no line numbers; default: 1000)
    line_number_inc: increment between line numbers (default: 10)
    bytes_per_line: number of encoded bytes in a source line (default: 8)
    """
    if (
            line_number_inc <= 0
            and line_number_start is not None and line_number_start > -1
        ):
        raise ValueError('line_number_inc must be > 0')
    with Stream(BytesIO(), mode='w') as bytesio:
        save_stream(fonts, bytesio, format=format, **kwargs)
        rawbytes = bytes(bytesio.getbuffer())
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
    outfile = outfile.text
    if line_number_start is not None and line_number_start >= 0:
        line_number = line_number_start
    else:
        line_number = None
    for line in lines:
        if line_number is not None:
            outfile.write(f'{line_number} ')
            line_number += line_number_inc
        outfile.write(f'DATA {line}\n')
    return fonts
