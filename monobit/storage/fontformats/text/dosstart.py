"""
monobit.storage.formats.text.dosstart - DosStart! format

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from io import StringIO

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph, Raster, StrokePath
from monobit.storage.utils.limitations import ensure_single, make_contiguous


_DOSSTART_SIG = 'DosStartFont'

@loaders.register(
    name='dosstart',
    magic=(_DOSSTART_SIG.encode('ascii'),),
    patterns=('*.dsf',),
    text=True,
)
def load_dosstart(instream):
    """Load font from DosStart! .DSF file."""
    instream = instream.text
    if instream.readline().rstrip('\r\n') != _DOSSTART_SIG:
        raise FileFormatError('Not a DosStart! font.')
    props = dict(
        name=instream.readline().rstrip('\r\n'),
    )
    try:
        format, _, ascent = instream.readline().rstrip('\r\n').partition(',')
        format = int(format)
        ascent = int(ascent)
    except ValueError as e:
        raise FileFormatError('Not a well-formed DosStart! file.')
    if format == 0:
        # ignore ascent value in format-0, shift-up is deduced from path start
        glyphs = _read_dsf_format_0(instream)
    elif format == 1:
        glyphs = _read_dsf_format_1(instream, ascent)
    else:
        raise FileFormatError(f'Unknown DosStart font format {format}')
    return Font(glyphs, **props).label(char_from='ascii')


@savers.register(linked=load_dosstart)
def save_dosstart(fonts, outstream):
    """Save font to DosStart! .DSF file (format 1 only)."""
    font = ensure_single(fonts)
    _write_dsf_format_1(font, outstream)


###############################################################################
# DosStart! Format 1: bitmap format

def _read_dsf_format_1(instream, ascent):
    """DosStart simple bitmap format reader."""
    glyphs = []
    for i, line in enumerate(instream):
        code, _, advance = line.rstrip('\r\n').upper().partition(',')
        advance = int(advance)
        width = int(code[:3])
        height = int(code[3:6])
        raster = Raster.from_vector(
            code[6:].strip(), stride=width, _0='G', _1='H'
        )
        # sample file has short bit string
        raster = raster.expand(top=height-raster.height)
        glyphs.append(Glyph(
            raster, right_bearing=advance-width,
            codepoint=0x20+i, shift_up=ascent-height,
        ))
    return glyphs


def _write_dsf_format_1(font, outstream):
    """DosStart simple bitmap format writer."""
    font = font.resample(codepoints=range(0x20, 0x80), missing='empty')
    outstream.write(_DOSSTART_SIG.encode('ascii') + b'\r\n')
    outstream.write(font.name.encode('ascii', 'replace') + b'\r\n')
    outstream.write((b'1, %d' % (font.ascent,)) + b'\r\n')
    for glyph in font.glyphs:
        # code
        outstream.write(b'%03d%03d' % (glyph.width, glyph.height))
        # glyph def
        outstream.write(b''.join(glyph.as_vector(ink=b'H', paper=b'G')))
        # advance
        outstream.write(b', %d \r\n' % (glyph.advance_width,))


###############################################################################
# DosStart! Format 0: stroke format

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