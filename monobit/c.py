"""
monobit.c - fonts embedded in C source files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from .binary import ceildiv
from .formats import Loaders, Savers
from .font import Font
from .glyph import Glyph
from .base import pair


###################################################################################################

@Loaders.register('c', 'cc', 'cpp', 'h', name='C-source')
def load(infile, identifier:str, cell:pair):
    """Load font from a .c file."""
    width, height = cell
    payload = _get_payload(infile, identifier)
    # c bytes are python bytes, except 0777-style octal (which we therefore don't support correctly)
    bytelist = [_int_from_c(_s) for _s in payload.split(',') if _s]
    # split into chunks
    bytewidth = ceildiv(width, 8)
    bytesize = bytewidth * height
    n_glyphs = ceildiv(len(bytelist), bytesize)
    glyphbytes = [
        bytelist[_ord*bytesize:(_ord+1)*bytesize]
        for _ord in range(n_glyphs)
    ]
    glyphs = [
        Glyph.from_bytes(_bytes, width)
        for _bytes in glyphbytes
    ]
    return Font(glyphs)


def _int_from_c(cvalue):
    """Parse integer from c code."""
    # suffixes
    while cvalue[-1:].lower() in ('u', 'l'):
        cvalue = cvalue[:-1]
    if cvalue.startswith('0') and cvalue[1:2] and cvalue[1:2] in string.digits:
        # c-style octal 0777
        cvalue = '0o' + cvalue[1:]
    # 0x, 0b, decimals - like Python
    return int(cvalue, 0)

def _get_payload(instream, identifier):
    """Find the identifier and get the part between {curly brackets}."""
    for line in instream:
        if '//' in line:
            line, _ = line.split('//', 1)
        line = line.strip(' \r\n')
        # for this to work the declaration must be at the start of the line
        # (whitespace excluded). compound statements would break this.
        if line.startswith(identifier):
            break
    else:
        raise ValueError('Identifier `{}` not found in file'.format(identifier))
    if '{' in line[len(identifier):]:
        _, line = line.split('{')
        if '}' in line:
            line, _ = line.split('}', 1)
            return line
        payload = [line]
    else:
        payload = []
    for line in instream:
        if '//' in line:
            line, _ = line.split('//', 1)
        line = line.strip(' \r\n')
        if '{' in line:
            _, line = line.split('{', 1)
        if '}' in line:
            line, _ = line.split('}', 1)
            payload.append(line)
            break
        if line:
            payload.append(line)
    return ''.join(payload)


###################################################################################################

@Savers.register('c', binary=False, multi=False)
def save(font, outstream):
    """Save font to c source as byte-aligned binary (DOS font)."""
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise ValueError(
            'This format only supports character-cell fonts.'
        )
    # convert name to c identifier
    ascii_name = font.name.encode('ascii', 'ignore').decode('ascii')
    ascii_name = ''.join(_c if _c.isalnum() else '_' for _c in ascii_name)
    identifier = 'char font_' + ascii_name
    width, height = font.bounding_box
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
