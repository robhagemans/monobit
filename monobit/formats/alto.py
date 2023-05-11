"""
monobit.formats.alto - Xerox Alto .AL screen font format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import count

from ..struct import bitfield, flag, big_endian as be
from ..storage import loaders, savers
from ..magic import FileFormatError
from ..properties import Props
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..labels import Tag


@loaders.register(
    name='alto',
    patterns=('*.al',),
)
def load_alto(instream):
    """Load font from Xerox Alto screen font file."""
    header, al_glyphs =  _read_alto(instream)
    glyphs = _convert_glyphs(header, al_glyphs)
    return Font(glyphs, line_height=header.height)


@loaders.register(
    name='bitblt',
    patterns=('*.strike',),
)
def load_bitblt(instream):
    """Load font from Xerox Alto .strike file."""
    props, glyphs =  _read_bitblt(instream)
    return Font(glyphs, **props)


##############################################################################
# .AL "CONVERT" format
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


##############################################################################
# "plainstrike" or "BITBLT" format

# a variant with a separate StrikeIndex file (.StrikeX) exists, but:
# > to the best of my knowledge, no one has ever used a StrikeIndex format

_FORMAT_STRUCT = be.Struct(
    # always =1, meaning 'new style'
    oneBit=bitfield('uint16', 1),
    # =1 means StrikeIndex, =0 otherwise
    index=bitfield('uint16', 1),
    # =1 if all characters have same value of Wx, else =0
    fixed=bitfield('uint16', 1),
    # =1 if KernedStrike, =0 if PlainStrike
    kerned=bitfield('uint16', 1),
    blank=bitfield('uint16', 12),
)

_STRIKE_HEADER = be.Struct(
    format=_FORMAT_STRUCT,
    # minimum character code
    min='uint16',
    # maximum character code
    max='uint16',
    # maximum spacing width of any character = max{Wx}
    maxwidth='uint16',
)

_STRIKE_BODY = be.Struct(
    # number of words in the StrikeBody
    length='uint16',
    # number of scan-lines above the baseline
    ascent='uint16',
    # number of scan-lines below the baseline
    descent='uint16',
    # always =0 [used to be used for padding schemes]
    xoffset='uint16',
    # number of words per scan-line in the strike
    raster='uint16',
    # the bit map, where height = ascent + descent
    # bitmap word raster*height
    # pointers into the strike, indexed by code
    # xinsegment ↑ min, max+2 word
)


def _read_bitblt(instream):
    header = _STRIKE_HEADER.read_from(instream)
    if not header.format.oneBit:
        raise FileFormatError('Not a Xerox BITBLT strike')
    if header.format.index:
        raise FileFormatError('StrikeIndex format not supported')
    # TODO
    if header.format.kerned:
        raise FileFormatError('KernedStrike format not supported')
    body = _STRIKE_BODY.read_from(instream)
    height = body.ascent + body.descent
    strikebytes = instream.read(2*body.raster*height)
    strike = Raster.from_bytes(strikebytes, 16*body.raster, height)
    # max is the highest included code; max+1 holds the replacement char
    # (if min==max we have 2 glyphs and 3 bounds)
    offsets = (be.uint16 * (header.max+3 - header.min)).read_from(instream)
    # convert strike to glyphs
    glyphs = [
        Glyph(
            strike.crop(left=_offset, right=max(0, 16*body.raster - _next)),
            codepoint=_cp,
            shift_up=-body.descent,
        )
        for _offset, _next, _cp in zip(offsets, offsets[1:], count(header.min))
        if _offset != _next
    ]
    # last char is replacement char (referred to as "dummy character" in the docs)
    glyphs[-1] = glyphs[-1].modify(codepoint=None, tag='dummy')
    props = dict(
        ascent=body.ascent,
        descent=body.descent,
        default_char=Tag('dummy'),
    )
    return props, glyphs
