"""
monobit.formats.daisydot - Daisy Dot II/III NLQ format

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..struct import big_endian as be
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..magic import FileFormatError
from ..binary import ceildiv, bytes_to_bits


# Daisy-Dot II
_DD2_MAGIC = b'DAISY-DOT NLQ FONT\x9b'
# Daisy-Dot III
_DD3_MAGIC = b'3\x9b'
# Daisy-Dot III Magnified
_DDM_MAGIC = b'B\x9b'

# controls and codepoints 96, 123 must not be stored
_DD_RANGE = tuple(_c for _c in range(32, 125) if _c not in (96, 123))


@loaders.register(
    name='daisy',
    magic=(_DD2_MAGIC, _DD3_MAGIC, _DDM_MAGIC),
    patterns=('*.nl[q234]',),
)
def load_daisy(instream):
    """Load font from fontx file."""
    version, props, glyphs = _read_daisy(instream)
    # logging.info('daisy properties:')
    # for line in str(props).splitlines():
    #     logging.info('    ' + line)
    props = _convert_from_daisy(props, glyphs, version)
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
    elif data.startswith(_DDM_MAGIC):
        # multi-file format
        return _parse_daisy_mag(data, instream.name, instream.where)
    raise FileFormatError(
        'Not a Daisy-Dot file: magic does not match either version'
    )

def _parse_daisy2(data):
    """Read daisy-dot II binary file and return glyphs."""
    ofs = len(_DD2_MAGIC)
    glyphs = []
    for cp in _DD_RANGE:
        width = data[ofs]
        if width < 1 or width > 19:
            logging.warning('Glyph width outside of allowed values, continuing')
        pass0 = bytes_to_bits(data[ofs+1:ofs+width+1])
        pass1 = bytes_to_bits(data[ofs+width+1:ofs+2*width+1])
        bits = tuple(_b for _pair in zip(pass0, pass1) for _b in _pair)
        glyphs.append(
            Glyph.from_vector(bits, stride=16, codepoint=cp)
            .transpose(adjust_metrics=False)
        )
        # separated by a \x9b
        ofs += 2*width + 2
    props = None
    return 2, props, glyphs


def _parse_daisy3(data):
    """Read daisy-dot III binary file and return glyphs."""
    ofs = len(_DD3_MAGIC)
    glyphs = []
    # dd3 does not store space glyph
    for cp in _DD_RANGE[1:]:
        double, width = divmod(data[ofs], 64)
        ofs += 1
        if width < 1 or width > 32:
            logging.warning('Glyph width outside of allowed values, continuing')
        double = bool(double)
        passes = [
            bytes_to_bits(data[ofs:ofs+width]),
            bytes_to_bits(data[ofs+width:ofs+2*width])
        ]
        bits = tuple(_b for _tup in zip(*passes) for _b in _tup)
        # we transpose, so stride is based on row height which is fixed
        matrix = Raster.from_vector(bits, stride=16).transpose().as_matrix()
        ofs += 2*width
        if double:
            passes = [
                bytes_to_bits(data[ofs:ofs+width]),
                bytes_to_bits(data[ofs+width:ofs+2*width])
            ]
            ofs += 2*width
            bits = tuple(_b for _tup in zip(*passes) for _b in _tup)
            matrix += (
                Raster.from_vector(bits, stride=16).transpose().as_matrix()
            )
        glyphs.append(Glyph(matrix, codepoint=cp))
        # in dd3, not separated by a \x9b
    dd3_props = _DD3_FINAL.from_bytes(data, ofs)
    # extend non-doubled glyphs
    height = max(_g.height for _g in glyphs)
    glyphs = [
        _g.expand(bottom=height-_g.height, adjust_metrics=False)
        for _g in glyphs
    ]
    # create space glyph
    space = Glyph.blank(
        width=dd3_props.space_width, height=height, codepoint=0x20,
    )
    glyphs = [space, *glyphs]
    return 3, dd3_props, glyphs

def _convert_from_daisy(dd3_props, glyphs, version):
    """Convert daisy-dot metrics to monobit."""
    if version == 2:
        # set some sensible defaults for DD2 which has no metrics
        return dict(
            source_format='Daisy-Dot II',
            right_bearing=1,
            line_height=20,
        )
    height = max(_g.height for _g in glyphs)
    pixel_size = dd3_props.height+1
    # we're using the underline as an indicator of where the baseline is
    descent = dd3_props.height-dd3_props.underline+2
    props = dict(
        source_format=(
            'Daisy-Dot III' if version == 3
            else 'Daisy_Dot III Magnified'
        ),
        right_bearing=1,
        # > Each DD3 font can be up to 32 rows high. However, If a font you are
        # > designing Is smaller than that, DD3 allows you to specify the actual
        # > height of the character so line spacing within the main printing
        # > program will match the size of the characters. The height marker can
        # > range from the second row (referred to as row 1) to the last row (row
        # > 31).
        shift_up=pixel_size-height-descent,
        ascent=pixel_size-descent,
        descent=descent,
        underline_descent=1,
        # > In Daisy-Dot III, line spacing is the vertical space, measured in units
        # > of 1/72", from the bottom of one line to the top of the next. Note that
        # > this is different from line spacing's typical definition, the space from
        # > the top of one line to the top of the next. The default line spacing is
        # > 4.
        line_height=pixel_size+4,
    )
    return props


def _parse_daisy_mag(data, name, container):
    """Read daisy-dot III magnified binary file and return glyphs."""
    _, dd3_props, glyphs = _parse_daisy3(data)
    # > total # of files = integer value of (height + l)/32. Add 1 if the
    # > division leaves a remainder.
    n_files = ceildiv(dd3_props.height+1, 32)
    path = Path(name).parent
    for count in range(2, n_files+1):
        stream_name = f'{name[:-1]}{count}'
        stream = container.open(path / stream_name, 'r')
        data = stream.read()
        _, _, new_glyphs = _parse_daisy3(data)
        glyphs = tuple(
            Glyph(
               # _g1.transpose().as_matrix() + _g2.transpose().as_matrix(),
               _g1.as_matrix() + _g2.as_matrix(),
                codepoint=_g1.codepoint
            )
            #.transpose(adjust_metrics=False)
            for _g1, _g2 in zip(glyphs, new_glyphs)
        )
    return 'M', dd3_props, glyphs
