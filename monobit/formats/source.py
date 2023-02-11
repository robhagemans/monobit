"""
monobit.formats.source - fonts embedded in C/Python/JS source files

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


_C_PARAMS = dict(
    delimiters='{}',
    comment='//',
)

_JS_PARAMS = dict(
    delimiters='[]',
    comment='//',
)

_PY_PARAMS = dict(
    delimiters='[]',
    comment='#',
)

###################################################################################################

@loaders.register('c', 'cc', 'cpp', 'h', name='c', wrapper=True)
def load_c(infile, *, identifier:str='', **kwargs):
    """
    Extract font from bitmap encoded in C or C++ source code.

    identifier: text at start of line where bitmap starts. (default: first array literal {})
    """
    return _load_coded_binary(
        infile, identifier=identifier,
        **_C_PARAMS, **kwargs
    )

@loaders.register('js', 'json', name='json', wrapper=True)
def load_json(infile, *, identifier:str='', **kwargs):
    """
    Extract font from bitmap encoded in JavaScript source code.

    identifier: text at start of line where bitmap starts (default: first list [])
    """
    return _load_coded_binary(
        infile, identifier=identifier,
        **_JS_PARAMS, **kwargs
    )

@loaders.register('py', name='python', wrapper=True)
def load_python(infile, *, identifier:str='', **kwargs):
    """
    Extract font from bitmap encoded as a list in Python source code.

    identifier: text at start of line where bitmap starts (default: first list [])
    """
    return _load_coded_binary(
        infile, identifier=identifier,
        **_PY_PARAMS, **kwargs
    )

@loaders.register(name='source', wrapper=True)
def load_source(
        infile, *,
        identifier:str='', delimiters:str='{}', comment:str='//',
        **kwargs
    ):
    """
    Extract font from bitmap encoded in source code.

    identifier: text at start of line where bitmap starts (default: first delimiter)
    delimiters: pair of delimiters that enclose the bitmap (default: {})
    comment: string that introduces inline comment (default: //)
    """
    return _load_coded_binary(
        infile, identifier=identifier,
        delimiters=delimiters, comment=comment,
        **kwargs
    )


def _load_coded_binary(
        infile, identifier, delimiters, comment,
        offset=0, format='raw', **kwargs,
    ):
    """Load font from binary encoded in source code."""
    payload = _get_payload(infile.text, identifier, delimiters, comment)
    data = bytes(_int_from_c(_s) for _s in payload.split(',') if _s.strip())
    bytesio = Stream.from_data(data[offset:], mode='r')
    return load_stream(bytesio, format=format, **kwargs)

def _int_from_c(cvalue):
    """Parse integer from c code."""
    # suffixes
    while cvalue[-1:].lower() in ('u', 'l'):
        cvalue = cvalue[:-1]
    if cvalue.startswith('0') and cvalue[1:2] and cvalue[1:2] in string.digits:
        # C / Python-2 octal 0777
        cvalue = '0o' + cvalue[1:]
    # 0x, 0b, decimals - like Python
    return int(cvalue, 0)

def _get_payload(instream, identifier, delimiters, comment):
    """Find the identifier and get the part between delimiters."""
    start, end = delimiters
    for line in instream:
        if comment in line:
            line, _ = line.split(comment, 1)
        line = line.strip(' \r\n')
        if identifier in line:
            if identifier:
                _, line = line.split(identifier)
            if start in line:
                _, line = line.split(start)
                break
    else:
        raise ValueError('No payload with identifier `{}` found in file'.format(identifier))
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


###################################################################################################

@savers.register('c', linked=load_c, wrapper=True)
def save_c(fonts, outstream, **kwargs):
    """
    Save font to bitmap encoded in C source code.
    """
    return _save_coded_binary(
        fonts, outstream, 'char font_{compactname}[{bytesize}] = ',
        **_C_PARAMS, **kwargs
    )

@savers.register('py', 'python', linked=load_python, wrapper=True)
def save_python(fonts, outstream, **kwargs):
    """
    Save font to bitmap encoded in Python source code.
    """
    return _save_coded_binary(
        fonts, outstream, 'font_{compactname} = ', **_PY_PARAMS, **kwargs
    )

@savers.register('json', linked=load_json, wrapper=True)
def save_json(fonts, outstream, **kwargs):
    """
    Save font to bitmap encoded in JSON code.
    """
    return _save_coded_binary(fonts, outstream, '', **_JS_PARAMS, **kwargs)

@savers.register('source', linked=load_source, wrapper=True)
def save_source(
        fonts, outstream, *,
        identifier:str, assign:str='=', delimiters:str='{}', comment:str='//',
        **kwargs
    ):
    """
    Save font to bitmap encoded in source code.
    """
    return _save_coded_binary(
        fonts, outstream,
        f'{identifier} {assign} ', delimiters, comment,
        **kwargs
    )

def _save_coded_binary(
        fonts, outstream, assignment_pattern, delimiters, comment,
        bytes_per_line=16, format='raw', **kwargs
    ):
    """
    Generate bitmap encoded source code from a font.

    fonts (List[Font]): Exactly one font must be given.
    outstream: Stream to write the source code to.
    assignment_pattern: Format pattern for the assignment statement. May include `compactname` amd `bytesize` variables.
    delimiters (str): Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
    comment (str): Line Comment character(s). Currently not used.
    bytes_per_line (int): number of encoded bytes in a source line
    format (str): format of payload
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
    save_stream(fonts, bytesio, format=format, **kwargs)
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
