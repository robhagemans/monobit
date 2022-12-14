"""
monobit.formats.daisydot - Daisy Dot II/III NLQ format

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..struct import big_endian as be
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError
from ..binary import bytes_to_bits


_DD2_MAGIC = b'DAISY-DOT NLQ FONT\x9b'
_DD3_MAGIC = b'3\x9b'

_DD_RANGE = tuple(_c for _c in range(32, 125) if _c not in (96, 123))


@loaders.register('nlq', name='daisy', magic=(_DD2_MAGIC, _DD3_MAGIC))
def load_daisy(instream, where=None):
    """Load font from fontx file."""
    props, glyphs = _read_daisy(instream)
    # logging.info('daisy properties:')
    # for line in str(props).splitlines():
    #     logging.info('    ' + line)
    props = _convert_from_daisy(props)
    return Font(glyphs, **props)


################################################################################
# daisy-dot II and III binary formats

# https://archive.org/stream/daisydotiiii/Daisy%20Dot%20III_djvu.txt

_DD3_FINAL = be.Struct(
    height='uint8',
    underline='uint8',
    space_width='uint8',
)

def _read_daisy(instream):
    """Read daisy-dot binary file and return glyphs."""
    data = instream.read()
    if data.startswith(_DD2_MAGIC):
        return _parse_daisy2(data)
    elif data.startswith(_DD3_MAGIC):
        return _parse_daisy3(data)
    raise FileFormatError(
        'Not a Daisy-Dot file: magic does not match either version'
    )

def _parse_daisy2(data):
    """Read daisy-dot II binary file and return glyphs."""
    ofs = len(_DD2_MAGIC)
    glyphs = []
    for cp in _DD_RANGE:
        width = data[ofs]
        pass0 = bytes_to_bits(data[ofs+1:ofs+width+1])
        pass1 = bytes_to_bits(data[ofs+width+1:ofs+2*width+1])
        bits = tuple(_b for _pair in zip(pass0, pass1) for _b in _pair)
        glyphs.append(
            Glyph.from_vector(bits, stride=16, codepoint=cp)
            .transpose(adjust_metrics=False)
        )
        # separated by a \x9b
        ofs += 2*width + 2
    props = {}
    return props, glyphs

def _convert_from_daisy(props):
    if not props:
        # daisy-dot 2
        return dict(
            right_bearing=1,
            line_height=17,
        )
