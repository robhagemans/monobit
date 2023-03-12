"""
monobit.formats.hurt - read Hershey fonts in Jim Hurt's format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..struct import big_endian as be, bitfield
from ..properties import Props
from ..vector import StrokePath


@loaders.register(
    name='hurt',
    patterns=('*.jhf',),
)
def load_hurt(
        instream,
        baseline:int=9, top:int=-12, bottom:int=16,
        renumber:bool=False,
    ):
    """
    Load a stroke font in Jim Hurt's format for Hershey's fonts.

    top: y-coordinate of top line (default: -12)
    baseline: y-coordinate of baseline (default: 9)
    bottom: y-coordinate of bottom (default: 16)
    renumber: set codepoint to ordinal value in file
    """
    jhf_data = _read_hurt(instream, renumber)
    font = _convert_hurt(jhf_data, baseline, top, bottom)
    return font


###############################################################################
# the distribution format is described in the accompanying usenet messages
# https://web.mit.edu/ghostscript/www/Hershey.htm
# the format brings too mind FORTRAN77 and punch cards
# https://hackaday.com/2021/03/30/hershey-fonts-not-chocolate-the-origin-of-vector-lettering/
# the *original* NTIS format seems to have been spelled-out numbers in a book


_LINEHEADER = be.Struct(
    number='5s',
    datasize='3s',
    left_margin='uint8',
    right_margin='uint8',
)

def _read_hurt(instream, renumber=False):
    """Read a stroke font in James Hurt's format ('R' format)."""
    text = instream.text
    glyphdata = []
    data = b''
    count = 0
    for line in text:
        data += line.encode('ascii', 'replace').rstrip()
        if not data:
            continue
        header = _LINEHEADER.from_bytes(data)
        if len(data) - _LINEHEADER.size < 2 * int(header.datasize) - 2:
            continue
        code = tuple(_b - ord(b'R') for _b in data[_LINEHEADER.size:])
        glyphdata.append(Props(
            number=count if renumber else int(header.number),
            left_margin=header.left_margin - ord(b'R'),
            right_margin=header.right_margin - ord(b'R'),
            code=code,
        ))
        data = b''
        count += 1
    return glyphdata


def _convert_hurt(glyphdata, baseline, top, bottom):
    """Convert JHF font data to monobit Font."""
    glyphs = []
    minx, miny = 0, 0
    maxx, maxy = 0, 0
    # Hershey glyph definitions start at a central point of the glyph
    # coordinates are left-to-right top-to-bottom
    starty = -top
    for glyphrec in glyphdata:
        cx, cy = 0, 0
        # first point given is always a move, not a line
        ink = StrokePath.MOVE
        # move from top left to Hershey's origin
        path = [(ink, -glyphrec.left_margin, starty)]
        for x, y in zip(glyphrec.code[::2], glyphrec.code[1::2]):
            if (x, y) == (-50, 0):
                # code ' R'
                ink = StrokePath.MOVE
                continue
            path.append((ink, x-cx, y-cy))
            cx, cy = x, y
            minx, miny = min(minx, cx), min(miny, cy)
            maxx, maxy = max(maxx, cx), max(maxy, cy)
            ink = StrokePath.LINE
        # convert from top-left to bottom-left coordinates
        path = StrokePath(path).flip().shift(0, baseline-top)
        glyphs.append(Glyph.from_path(
            path, codepoint=glyphrec.number,
            advance_width=glyphrec.right_margin-glyphrec.left_margin,
        ))
    return Font(
        glyphs, ascent=-top+baseline, descent=-baseline+bottom,
    )
