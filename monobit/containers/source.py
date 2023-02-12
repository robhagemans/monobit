"""
monobit.containers.source - fonts embedded in C/Python/JS source files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from io import BytesIO
import string

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


_C_PARAMS = dict(
    delimiters='{}',
    comment='//',
)

_JS_PARAMS = dict(
    delimiters='[]',
    comment='//',
)

_PY_PARAMS = dict(
    comment='#',
)

_PAS_PARAMS = dict(
    delimiters='()',
    comment='{',
    int_conv=_int_from_pascal,
)


###############################################################################


@loaders.register('c', 'cc', 'cpp', 'h', name='c', wrapper=True)
def load_c(infile, *, identifier:str='', payload:str='raw', **kwargs):
    """
    Extract font from bitmap encoded in C or C++ source code.

    identifier: text at start of line where bitmap starts. (default: first array literal {})
    payload: format of payload (default: 'raw')
    """
    return _load_coded_binary(
        infile, identifier=identifier, payload=payload,
        **_C_PARAMS, **kwargs
    )


@loaders.register('js', 'json', name='json', wrapper=True)
def load_json(infile, *, identifier:str='', payload:str='raw', **kwargs):
    """
    Extract font from bitmap encoded in JavaScript source code.

    identifier: text at start of line where bitmap starts (default: first list [])
    payload: format of payload (default: 'raw')
    """
    return _load_coded_binary(
        infile, identifier=identifier, payload=payload,
        **_JS_PARAMS, **kwargs
    )


@loaders.register('py', name='python', wrapper=True)
def load_python(infile, *, identifier:str='', payload:str='raw', **kwargs):
    """
    Extract font from bitmap encoded as a list in Python source code.

    identifier: text at start of line where bitmap starts (default: first list [])
    payload: format of payload (default: 'raw')
    """
    return _load_coded_binary(
        infile, identifier=identifier, payload=payload,
        delimiters='[]', **_PY_PARAMS, **kwargs
    )


@loaders.register('py', name='python-tuple', wrapper=True)
def load_python_tuple(infile, *, identifier:str='', payload:str='raw', **kwargs):
    """
    Extract font from bitmap encoded as a list in Python source code.

    identifier: text at start of line where bitmap starts (default: first tuple)
    payload: format of payload (default: 'raw')
    """
    return _load_coded_binary(
        infile, identifier=identifier, payload=payload,
        delimiters='()', **_PY_PARAMS, **kwargs
    )


@loaders.register('pas', name='pascal', wrapper=True)
def load_pascal(infile, *, identifier:str='', payload:str='raw', **kwargs):
    """
    Extract font from bitmap encoded as a list in Pascal source code.

    identifier: text at start of line where bitmap starts (default: first array)
    payload: format of payload (default: 'raw')
    """
    return _load_coded_binary(
        infile, identifier=identifier, payload=payload,
        **_PAS_PARAMS, **kwargs
    )


@loaders.register(name='source', wrapper=True)
def load_source(
        infile, *,
        identifier:str='', delimiters:str='{}', comment:str='//', assign:str='=',
        payload:str='raw',
        **kwargs
    ):
    """
    Extract font from bitmap encoded in source code.

    identifier: text at start of line where bitmap starts (default: first delimiter)
    delimiters: pair of delimiters that enclose the bitmap (default: {})
    comment: string that introduces inline comment (default: //)
    payload: format of payload (default: 'raw')
    """
    return _load_coded_binary(
        infile, identifier=identifier,
        delimiters=delimiters, comment=comment,
        payload=payload, assign=assign,
        **kwargs
    )


def _load_coded_binary(
        infile, *, identifier, delimiters, comment,
        assign='=', int_conv=_int_from_c,
        payload='raw', **kwargs,
    ):
    """Load font from binary encoded in source code."""
    coded_data = _get_payload(
        infile.text, identifier, delimiters, comment, assign
    )
    data = bytes(int_conv(_s) for _s in coded_data.split(',') if _s.strip())
    bytesio = Stream.from_data(data, mode='r')
    return load_stream(bytesio, format=payload, **kwargs)


def _get_payload(instream, identifier, delimiters, comment, assign):
    """Find the identifier and get the part between delimiters."""
    start, end = delimiters
    for line in instream:
        if comment in line:
            line, _ = line.split(comment, 1)
        line = line.strip(' \r\n')
        if identifier in line and assign in line:
            if identifier:
                _, line = line.split(identifier)
            if start in line:
                _, line = line.split(start)
                break
    else:
        raise FileFormatError(
            f'No payload with identifier `{identifier}` found in file'
        )
    if end in line:
        line, _ = line.split(end, 1)
        return line
    payload = [line]
    for line in instream:
        if comment in line:
            line, _ = line.split(comment, 1)
        line = line.strip(' \r\n')
        if start in line:
            _, line = line.split(start, 1)
        if end in line:
            line, _ = line.split(end, 1)
            payload.append(line)
            break
        if line:
            payload.append(line)
    return ''.join(payload)


###############################################################################

@savers.register(linked=load_c, wrapper=True)
def save_c(fonts, outstream, payload:str='raw', bytes_per_line:int=16, **kwargs):
    """
    Save font to bitmap encoded in C source code.

    bytes_per_line: number of encoded bytes in a source line (default: 16)
    payload: format of payload (default: 'raw')
    """
    return _save_coded_binary(
        fonts, outstream, 'char font_{compactname}[{bytesize}] = ',
        payload=payload, bytes_per_line=bytes_per_line,
        **_C_PARAMS, **kwargs
    )


@savers.register(linked=load_python, wrapper=True)
def save_python(
        fonts, outstream,
        delimiters:str='[]',
        payload:str='raw', bytes_per_line:int=16,
        **kwargs
    ):
    """
    Save font to bitmap encoded in Python source code.

    delimiters: pair of delimiters that enclose the bitmap (default: [])
    bytes_per_line: number of encoded bytes in a source line (default: 16)
    payload: format of payload (default: 'raw')
    """
    return _save_coded_binary(
        fonts, outstream, 'font_{compactname} = ',
        payload=payload, bytes_per_line=bytes_per_line,
        delimiters=delimiters, **_PY_PARAMS, **kwargs
    )


@savers.register(linked=load_json, wrapper=True)
def save_json(
        fonts, outstream, payload:str='raw', bytes_per_line:int=16, **kwargs
    ):
    """
    Save font to bitmap encoded in JSON code.

    bytes_per_line: number of encoded bytes in a source line (default: 16)
    payload: format of payload (default: 'raw')
    """
    return _save_coded_binary(
        fonts, outstream, '',
        payload=payload, bytes_per_line=bytes_per_line,
        **_JS_PARAMS, **kwargs
    )

@savers.register(linked=load_source, wrapper=True)
def save_source(
        fonts, outstream, *,
        identifier:str, assign:str='=', delimiters:str='{}', comment:str='//',
        bytes_per_line:int=16, payload:str='raw',
        **kwargs
    ):
    """
    Save font to bitmap encoded in source code.

    identifier: text at start of line where bitmap starts (default: first delimiter)
    assign: assignment operator (default: =)
    delimiters: pair of delimiters that enclose the bitmap (default: {})
    comment: string that introduces inline comment (default: //)
    bytes_per_line: number of encoded bytes in a source line (default: 16)
    payload: format of payload (default: 'raw')
    """
    return _save_coded_binary(
        fonts, outstream,
        f'{identifier} {assign} ', delimiters, comment,
        payload=payload,
        **kwargs
    )

def _save_coded_binary(
        fonts, outstream, assignment_pattern, delimiters, comment,
        bytes_per_line=16, payload='raw', **kwargs
    ):
    """
    Generate bitmap encoded source code from a font.

    fonts (List[Font]): Exactly one font must be given.
    outstream: Stream to write the source code to.
    assignment_pattern: Format pattern for the assignment statement. May include `compactname` amd `bytesize` variables.
    delimiters (str): Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
    comment (str): Line Comment character(s). Currently not used.
    bytes_per_line (int): number of encoded bytes in a source line
    payload (str): format of payload
    """
    if len(delimiters) < 2:
        raise ValueError('A start and end delimiter must be given. E.g. []')
    start_delimiter = delimiters[0]
    end_delimiter = delimiters[1]
    # build the identifier from first font name
    ascii_name = fonts[0].name.encode('ascii', 'ignore').decode('ascii')
    ascii_name = ''.join(_c if _c.isalnum() else '_' for _c in ascii_name)
    # get the raw data
    bytesio = Stream(BytesIO(), mode='w')
    save_stream(fonts, bytesio, format=payload, **kwargs)
    rawbytes = bytesio.getbuffer()
    assignment = assignment_pattern.format(
        compactname=ascii_name, bytesize=len(rawbytes)
    )
    # emit code
    outstream = outstream.text
    outstream.write(f'{assignment}{start_delimiter}\n')
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
    outstream.write(f'{end_delimiter}\n')
    return fonts
