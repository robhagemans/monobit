"""
monobit.c - fonts embedded in C source files

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from ..base.binary import ceildiv
from ..formats import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError
from ..base import pair
from .raw import parse_aligned


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

@loaders.register('c', 'cc', 'cpp', 'h', name='C source')
def load_c(
        infile, where=None, *,
        identifier:str,
        cell:pair=(8, 8), n_chars:int=None, offset:int=0, padding:int=0,
    ):
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, n_chars=n_chars, offset=offset, padding=padding,
        **_C_PARAMS
    )

@loaders.register('js', 'json', name='JavaScript source')
def load_js(
        infile, where=None, *,
        identifier:str,
        cell:pair=(8, 8), n_chars:int=None, offset:int=0, padding:int=0,
    ):
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, n_chars=n_chars, offset=offset, padding=padding,
        **_JS_PARAMS
    )

@loaders.register('py', name='Python source')
def load(
        infile, where=None, *,
        identifier:str,
        cell:pair=(8, 8), n_chars:int=None, offset:int=0, padding:int=0,
    ):
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, n_chars=n_chars, offset=offset, padding=padding,
        **_PY_PARAMS
    )

@loaders.register(name='source')
def load(
        infile, where=None, *,
        identifier:str, delimiters:str='{}', comment:str='//',
        cell:pair=(8, 8), n_chars:int=None, offset:int=0, padding:int=0,
    ):
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, n_chars=n_chars, offset=offset, padding=padding,
        elimiters=delimiters, comment=coment
    )


def _load_coded_binary(
        infile, where, identifier, delimiters, comment,
        cell, n_chars, offset, padding,
    ):
    """Load font from binary encoded in source code."""
    width, height = cell
    payload = _get_payload(infile.text, identifier, delimiters, comment)
    bytelist = [_int_from_c(_s) for _s in payload.split(',') if _s]
    glyphs = parse_aligned(bytelist, width, height, n_chars, offset, padding)
    return Font(glyphs)

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
    """Find the identifier and get the part between {curly brackets}."""
    start, end = delimiters
    for line in instream:
        if comment in line:
            line, _ = line.split(comment, 1)
        line = line.strip(' \r\n')
        # for this to work the declaration must be at the start of the line
        # (whitespace excluded). compound statements would break this.
        if line.startswith(identifier):
            break
    else:
        raise ValueError('Identifier `{}` not found in file'.format(identifier))
    if start in line[len(identifier):]:
        _, line = line.split(start)
        if end in line:
            line, _ = line.split(end, 1)
            return line
        payload = [line]
    else:
        payload = []
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

@savers.register('c', loader=load)
def save(fonts, outstream, where=None):
    """Save font to c source as byte-aligned binary (DOS font)."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to BDF file.')
    font = fonts[0]
    outstream = outstream.text
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    # convert name to c identifier
    ascii_name = font.name.encode('ascii', 'ignore').decode('ascii')
    ascii_name = ''.join(_c if _c.isalnum() else '_' for _c in ascii_name)
    identifier = 'char font_' + ascii_name
    width, height = font.max_raster_size
    bytesize = ceildiv(width, 8) * height
    outstream.write(f'{identifier}[{len(font.glyphs) * bytesize}]')
    outstream.write(' = {\n')
    for glyph in font.glyphs:
        outstream.write('  ')
        for byte in glyph.as_bytes():
            outstream.write(f'0x{byte:02x}, ')
        outstream.write('\n')
    outstream.write('}\n')
    return font
