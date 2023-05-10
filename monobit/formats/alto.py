"""
monobit.formats.alto - Xerox Alto .AL screen font format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..struct import bitfield, big_endian as be
from ..storage import loaders, savers
from ..magic import FileFormatError
from ..properties import Props
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster


@loaders.register(
    name='alto',
    patterns=('*.al',),
)
def load_alto(instream):
    """Load font from Xerox Alto screen font file."""
    header, al_glyphs =  _read_alto(instream)
    glyphs = _convert_glyphs(header, al_glyphs)
    return Font(glyphs, line_height=header.height)


##############################################################################
# http://www.bitsavers.org/pdf/xerox/alto/printing/AltoFontFormats_Oct1980.pdf

_AL_HEADER = be.Struct(
    height='uint16',
    proportional=bitfield('uint8', 1),
    baseline=bitfield('uint8', 7),
    maxWidth='uint8',
)

_XH_DATA = be.Struct(
    XW='uint16',
    HD='uint8',
    XH='uint8',
)

def _read_alto(instream):
    """Read Xerox Alto screen font file."""
    header = _AL_HEADER.read_from(instream)
    # character pointer table
    # pointers are self-referenced word offsets to the XW value in character structs
    pointers = []
    i = 0
    while True:
        here = instream.tell()
        # beak if we are at the first pointed-to location
        if pointers and here >= min(pointers):
            break
        pointer = be.uint16.read_from(instream)
        # break on null pointer
        if not int(pointer):
            break
        # record absolute position in file
        pointers.append(here + pointer*2)
    al_glyphs = tuple(
        _read_glyph(instream, header, pointer, cp)
        for cp, pointer in enumerate(pointers)
    )
    return header, al_glyphs


def _read_glyph(instream, header, pointer, cp):
    instream.seek(pointer)
    xh_data = _XH_DATA.read_from(instream)
    instream.seek(-_XH_DATA.size - xh_data.XH*2, 1)
    glyph_data = instream.read(xh_data.XH*2)
    return Props(
        pixels=Raster.from_bytes(glyph_data, width=16),
        **vars(xh_data)
    )


def _convert_glyphs(header, al_glyphs):
    glyphs = tuple(
        _convert_glyph(header, props)
        for props in al_glyphs
    )
    final_glyphs = []
    for cp, g in enumerate(glyphs[:256]):
        if g:
            while hasattr(g, 'extension'):
                ext = glyphs[g.extension]
                if g.shift_up > ext.shift_up:
                    g = g.expand(bottom=g.shift_up - ext.shift_up)
                else:
                    ext = ext.expand(bottom=ext.shift_up - g.shift_up)
                if g.height > ext.height:
                    ext = ext.expand(top=g.height - ext.height)
                else:
                    g = g.expand(top=ext.height - g.height)
                g = Glyph(
                    Raster.concatenate(g.pixels, ext.pixels),
                    right_bearing=ext.right_bearing, shift_up=ext.shift_up
                )
            final_glyphs.append(g.modify(codepoint=cp))
    return final_glyphs


def _convert_glyph(header, props):
    if (props.XW % 2):
        advance_width = (props.XW-1) // 2
        extension = None
    else:
        advance_width=16
        # index of extension char
        extension = props.XW // 2
    glyph_props = dict(
        right_bearing=-16 + advance_width,
        shift_up=header.baseline-props.HD-props.XH+1,
        extension=extension,
    )
    if not props.pixels:
        if props.HD or props.XW > 1:
            return Glyph.blank(width=16, height=props.HD, **glyph_props)
    else:
        return Glyph(props.pixels, width=16, **glyph_props)
    return None
