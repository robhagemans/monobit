"""
monobit.hexdraw - read and write .bdf files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import binascii

from .base import ensure_stream


def _read_dict(instream, until=None):
    """Read key-value pairs."""
    result = {}
    for line in instream:
        if not line:
            continue
        if ' ' not in line:
            break
        keyword, values = line[:-1].split(' ', 1)
        result[keyword] = values.strip()
        if keyword == until:
            break
    return result

def load(infile):
    """Load font from a .bdf file."""
    with ensure_stream(infile, 'r') as instream:
        # read version
        line = instream.readline()[:-1]
        keyword, bdf_version = line.split(' ', 1)
        if keyword != 'STARTFONT':
            raise ValueError('Not a BDF file.')
        # read global section
        # we're ignoring metadata for now...
        metadata = {}
        comments = []
        while True:
            line = instream.readline()[:-1]
            if not line:
                continue
            if line.startswith('COMMENT'):
                comments.append(line[8:])
                continue
            keyword, values = line.split(' ', 1)
            if keyword == 'STARTPROPERTIES':
                metadata['PROPERTIES'] = _read_dict(instream, until='ENDPROPERTIES')
            else:
                metadata[keyword] = values.strip()
                if keyword == 'CHARS':
                    break
        # read character section
        # state
        current_char = None
        bitmap = False
        # output
        glyphs = {}
        glyph_meta = {}
        while True:
            line = instream.readline()[:-1]
            if not line:
                continue
            if line.startswith('ENDFONT'):
                break
            elif not line.startswith('STARTCHAR'):
                raise ValueError('Expected STARTCHAR')
            keyword, values = line.split(' ', 1)
            meta = _read_dict(instream, until='BITMAP')
            meta[keyword] = values
            width, height, _, _ = meta['BBX'].split(' ')
            width, height = int(width), int(height)
            # fix for ami2bdf fonts
            #if width > 65534:
            #    width -= 65534
            # convert from hex-string to list of bools
            data = [instream.readline()[:-1] for _ in range(height)]
            bytewidth = len(data[0]) // 2
            fmt = '{:0%db}' % (bytewidth*8,)
            glyphstrs = [fmt.format(int(_row, 16)).ljust(width, '\0')[:width] for _row in data]
            glyph = [[_c == '1' for _c in _row] for _row in glyphstrs]
            # store in dict
            # ENCODING must be single integer or -1 followed by integer
            encvalue = int(meta['ENCODING'].split(' ')[-1])
            glyphs[encvalue] = glyph
            glyph_meta[encvalue] = meta
            if not instream.readline().startswith('ENDCHAR'):
                raise('Expected ENDCHAR')
        #print(comments)
        #print(metadata)
        #print(glyph_meta)
        return glyphs
