"""
monobit.storage.formats.dosstart - DosStart! format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from io import StringIO

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph, Raster, StrokePath


@loaders.register(
    name='dosstart',
    magic=(b'DosStartFont',),
    patterns=('*.dsf',),
)
def load_dosstart(instream):
    """Load font from DosStart! .DSF file."""
    return _load_dsf(instream.text)


##############################################################################
# loader

def _load_dsf(instream):
    """Load font from a .dsf file."""
    if instream.readline().rstrip('\r\n') != 'DosStartFont':
        raise FileFormatError('Not a DosStart! font.')
    props = dict(
        name=instream.readline().rstrip('\r\n'),
    )
    format, _, ascent = instream.readline().rstrip('\r\n').partition(',')
    if int(format) == 0:
        glyphs = _read_dsf_format_0(instream)
    elif int(format) == 1:
        glyphs = _read_dsf_format_1(instream)
    else:
        raise FileFormatError(f'Unknown DosStart font format {format}')
    return Font(glyphs, **props)


def _read_dsf_format_1(instream):
    """DosStart simple bitmap format."""
    glyphs = []
    for i, line in enumerate(instream):
        code, _, advance = line.rstrip('\r\n').upper().partition(',')
        advance = int(advance)
        width = int(code[:3])
        height = int(code[3:6])
        raster = Raster.from_vector(
            code[6:].strip(), stride=width, _0='G', _1='H'
        )
        glyphs.append(Glyph(
            raster, right_bearing=advance-width,
            codepoint=0x20+i
        ))
    return glyphs


def _read_dsf_format_0(instream):
    """DosStart turtle graphics format."""
    glyphs = []
    for i, line in enumerate(instream):
        line = line.rstrip('\r\n')
        if not line:
            continue
        code, _, advance = line.lower().partition(',')
        advance = int(advance)
        path = []
        offset = 0
        width, height = 0, 0
        while True:
            mode, direction, offset = _read_command(code, offset)
            if not direction:
                break
            ink = mode != 'b'
            move = mode != 'n'
            step, offset = _read_stepsize(code, offset)
            dx, dy = _move_turtle(direction, step)
            pathmove = StrokePath.LINE if ink else StrokePath.MOVE
            path.append((pathmove, dx, dy))
            if not move:
                path.append((StrokePath.MOVE, -dx, -dy))
        # turtle moves to next origin, therefore raster includes this column
        glyph = Glyph.from_path(
            StrokePath(path), advance_width=advance, codepoint=0x20+i,
        )
        # remove extra column generated by path going to next origin
        glyph = glyph.crop(right=1)
        glyphs.append(glyph)
    return glyphs

def _read_command(code, offset):
    """Read mode and command characer."""
    try:
        cmd = code[offset]
    except IndexError:
        return '', '', offset
    offset += 1
    if cmd not in ('b', 'n'):
        return '', cmd, offset
    mode = cmd
    try:
        cmd = code[offset]
    except IndexError:
        cmd = ''
    offset += 1
    return mode, cmd, offset

def _read_stepsize(code, offset):
    """Read step size."""
    num = []
    while True:
        try:
            d = code[offset]
        except IndexError:
            break
        if not d.isdigit():
            break
        offset += 1
        num.append(d)
    if not num:
        return 1, offset
    return int(''.join(num)), offset

def _move_turtle(cmd, step):
    """Move the turtle one step in the given direction."""
    dx, dy = 0, 0
    if cmd in ('u', 'e', 'h'):
        dy += 1
    if cmd in ('r', 'e', 'f'):
        dx += 1
    if cmd in ('d', 'f', 'g'):
        dy -= 1
    if cmd in ('l', 'g', 'h'):
        dx -= 1
    return dx*step, dy*step
