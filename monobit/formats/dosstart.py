"""
monobit.dosstart - DosStart! format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string
from io import StringIO

from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster


@loaders.register('dsf', name='dosstart', magic=(b'DosStartFont',))
def load_dosstart(instream, where=None):
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
        x, y = 0, 0
        pixels = []
        offset = 0
        ink = True
        move = True
        width, height = 0, 0
        while True:
            try:
                cmd = code[offset]
            except IndexError:
                break
            offset += 1
            if cmd == 'b':
                ink = False
                continue
            if cmd == 'n':
                move = False
                continue
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
            if num:
                step = int(''.join(num))
            else:
                step = 1
            nx, ny = x, y
            for _ in range(step):
                if ink:
                    pixels.append((nx, ny))
                height = max(height, ny)
                width = max(width, nx)
                if cmd in ('u', 'e', 'h'):
                    ny += 1
                if cmd in ('r', 'e', 'f'):
                    nx += 1
                if cmd in ('d', 'f', 'g'):
                    ny -= 1
                if cmd in ('l', 'g', 'h'):
                    nx -= 1
            if ink:
                pixels.append((nx, ny))
            height = max(height, ny)
            width = max(width, nx)
            if move:
                x, y = nx, ny
            ink = True
            move = True
        raster = tuple(
            ''.join(
                '1' if (_x, _y) in pixels else '0'
                for _x in range(width+1)
            )
            for _y in reversed(range(height+1))
        )
        glyph = Glyph(
            raster, _0='0', _1='1',
            right_bearing=advance-width,
            codepoint=0x20+i,
        )
        # print(code)
        # print(glyph)
        glyphs.append(glyph)
    return glyphs
