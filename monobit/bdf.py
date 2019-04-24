"""
monobit.hexdraw - read and write .bdf files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging
import binascii

from .base import Font, ensure_stream


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

def _read_bdf_characters(instream):
    """Read character section."""
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
    return glyphs, glyph_meta

def _read_bdf_global(instream):
    """Read global section of BDF file."""
    # read global section
    bdf_props = {}
    x_props = {}
    comments = []
    parsing_x = False
    while True:
        line = instream.readline()[:-1]
        if not line:
            continue
        elif line.startswith('COMMENT'):
            comments.append(line[8:])
        elif line.startswith('STARTPROPERTIES'):
            parsing_x = True
        elif line.startswith('ENDPROPERTIES'):
            parsing_x = False
        else:
            keyword, values = line.split(' ', 1)
            values = values.strip()
            if keyword == 'CHARS':
                # value equals number of chars
                # ignore number of chars, we'll know it when we've read them all
                # this signals the end of the global section though.
                break
            elif parsing_x:
                x_props[keyword] = values
            else:
                # record all keywords in the same metadata table
                bdf_props[keyword] = values
    return comments, bdf_props, x_props


@Font.loads('bdf')
def load(infile):
    """Load font from a .bdf file."""
    with ensure_stream(infile, 'r') as instream:
        comments, bdf_props, x_props = _read_bdf_global(instream)
        glyphs, glyph_props = _read_bdf_characters(instream)
        # parse meaningful metadata
        # converter-supplied metadata
        properties = {
            'source-format': 'BDF {}'.format(bdf_props['STARTFONT']),
            'source-name': os.path.basename(instream.name),
        }
        if 'DEFAULTCHAR' in x_props:
            defaultchar = x_props['DEFAULTCHAR']
            # if the number doesn't occur, no default is set.
            if int(defaultchar) in glyphs:
                properties['default_glyph'] = defaultchar
        # FIXME: parse per-glyph geometry ... we need BBX and the offsets in swidth (I think)
        # modify glyphs if necessary to get to one global offset value
        # TODO: get metadata (foundry, name, ..) from xlfd or x props
        return Font(glyphs, comments, properties)
