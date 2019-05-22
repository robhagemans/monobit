"""
monobit.c - read and write .c source files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string

from .binary import ceildiv
from .typeface import Typeface
from .font import Font
from .glyph import Glyph


@Typeface.loads('c', 'cc', 'cpp', 'h')
def load(infile, identifier, width, height):
    """Load font from a .c file."""
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
    return Typeface([Font(glyphs)])


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
