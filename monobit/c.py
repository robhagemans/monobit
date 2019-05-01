"""
monobit.hexdraw - read and write .c source files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import Font, ensure_stream, ceildiv


@Font.loads('c', 'cc', 'cpp', 'h')
def load(infile, identifier, width, height):
    """Load font from a .c file."""
    payload = _get_payload(infile, identifier)
    # c bytes are python bytes, except 0777-style octal (which we therefore don't support correctly)
    bytelist = [int(_s, 0) for _s in payload.split(',') if _s]
    bitrows = ['{:08b}'.format(_n) for _n in bytelist]
    bytewidth = ceildiv(width, 8)
    bitrows = [
        ''.join(_row for _row in bitrows[_offs:_offs+bytewidth])
        for _offs in range(0, len(bitrows), bytewidth)
    ]
    bitrows = [[(_c == '1') for _c in _row] for _row in bitrows]
    bitrows = [_row[:width] for _row in bitrows]
    font = {_key: bitrows[_key*height:(_key+1)*height] for _key in range(len(bitrows)//height)}
    return font


def _get_payload(infile, identifier):
    """Find the identifier and get the part between {curly brackets}."""
    with ensure_stream(infile, 'r') as instream:
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
