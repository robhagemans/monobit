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


@loaders.register(
    name='prepress',
    patterns=('*.ac',),
)
def load_prepress(instream):
    """Load font from Xerox Alto PrePress .ac file."""
    props, glyphs =  _read_prepress(instream)
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

_BOUNDING_BOX_BLOCK = be.Struct(
    # X offset
    FBBox='uint16',
    # Y offset
    FBBoy='uint16',
    # X width
    FBBdx='uint16',
    # Y width
    FBBdy='uint16',
)

_WIDTH_ENTRY = be.Struct(
    # the entire spacing word will be = (-1) (both bytes =377b)
    # to flag a non-existent character, else the bytes are:
    offset='int8',
    width='int8',
)

def _read_bitblt(instream):
    # @StrikeHeader
    header = _STRIKE_HEADER.read_from(instream)
    if not header.format.oneBit:
        raise FileFormatError('Not a Xerox BITBLT strike')
    if header.format.index:
        raise FileFormatError('StrikeIndex format not supported')
    # @BoundingBoxBlock
    if header.format.kerned:
        bbox = _BOUNDING_BOX_BLOCK.read_from(instream)
    # @StrikeBody
    body = _STRIKE_BODY.read_from(instream)
    height = body.ascent + body.descent
    strikebytes = instream.read(2*body.raster*height)
    # max is the highest included code; max+1 holds the replacement char
    # (if min==max we have 2 glyphs and 3 bounds)
    offsets = (be.uint16 * (header.max+3 - header.min)).read_from(instream)
    # @WidthBody
    if header.format.kerned:
        spacing = (_WIDTH_ENTRY * (header.max+2 - header.min)).read_from(instream)
    strike = Raster.from_bytes(strikebytes, 16*body.raster, height)
    # conversion section
    # convert strike to glyphs
    if header.format.kerned:
        glyphs = [
            Glyph(
                strike.crop(left=_offset, right=max(0, 16*body.raster - _next)),
                codepoint=_cp,
                shift_up=-body.descent,
                left_bearing=_spacing.offset+bbox.FBBox,
                right_bearing=(
                    _spacing.width
                    -(_next-_offset)
                    -(_spacing.offset+bbox.FBBox)
                ),
            )
            for _offset, _next, _spacing, _cp in zip(
                offsets, offsets[1:], spacing, count(header.min)
            )
            if _spacing.width >= 0 and _spacing.offset >= 0
        ]
    else:
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


##############################################################################
# PrePress format

_IX = be.Struct(
    # Various type codes are assigned
    type=bitfield('uint16', 4),
    # Length of entry in words, counting this one
    length=bitfield('uint16', 12),
)

# name-definition index entry
_IXN = be.Struct(
    # Header with type == 1
    ix=_IX,
    # The numeric code
    code='uint16',
    # The number of characters in the name
    nameLength='uint8',
    # Room for the name
    characters='19s',
)

_CHARACTER_INDEX_ENTRY = be.Struct(
    # type = 3 for character index
    ix=_IX,
    # Family name, using a name code
    family='uint8',
    # (if bold then 2 elseif light then 4 else 0) +
    # (if italic then 1 else 0) +
    # (if codensed then 6 elseif expanded then 12 else 0) +
    # (if Xerox then 0 elseif ASCII then 18 else 36)
    face='uint8',
    # Code for the "beginning character"
    bc='uint8',
    # Code for the "ending character"
    ec='uint8',
    # Size of the font segment [in micas == 10 micron units or 1/2540 in]
    size='uint16',
    # Rotation of the font segment
    rotation='uint16',
    # Starting address in file of the font segment
    segmentSA='uint32',
    # Length of the segment
    segmentLength='uint32',
    # Resolution in scan-lines/inch * 10
    resolutionX='uint16',
    # Resolution in bits/inch * 10
    resolutionY='uint16',
)


_CHARACTER_DATA = be.Struct(
    # X Width (scan-lines)
    # fixed-point, divide by 0x10000
    Wx='uint32',
    # Y width (bits)
    # fixed-point, divide by 0x10000
    Wy='uint32',
    # Bounding box offsets
    BBox='int16',
    BBoy='int16',
    # Width of bounding box (scan-lines)
    BBdx='uint16',
    # Height of bounding box (bits) or -1 for not defined
    BBdy='int16',
)

# relFilePos=uint32

_RASTER_DEFN = be.Struct(
    # Height of raster (in words)
    BBdyW=bitfield('uint16', 6),
    # Same as BBdx in CharacterData
    BBdx=bitfield('uint16', 10),
    # followed by raster, BBdyW*BBdx words
)


def _read_prepress(instream):
    """Read a PrePress file."""
    ixn = _IXN.read_from(instream)
    if ixn.ix.type != 1:
        raise FileFormatError('Not an .ac file: no name index entry')
    cie = _CHARACTER_INDEX_ENTRY.read_from(instream)
    if cie.ix.type != 3:
        raise FileFormatError('Not an .ac file: no character index entry')
    if cie.rotation != 0:
        raise FileFormatError('Nonzero rotation not supported for this format.')
    instream.seek(cie.segmentSA*2)
    nchars = cie.ec - cie.bc + 1
    char_data = (_CHARACTER_DATA * nchars).read_from(instream)
    anchor = instream.tell()
    directory = (be.uint32 * nchars).read_from(instream)
    glyphs = []
    for cp, offset, cd in zip(range(cie.bc, cie.ec+1), directory, char_data):
        if cd.BBdy < 0:
            continue
        instream.seek(anchor+offset*2)
        raster_defn = _RASTER_DEFN.read_from(instream)
        raster = Raster.from_bytes(
            instream.read(2*raster_defn.BBdyW*raster_defn.BBdx),
            width=raster_defn.BBdyW*16,
            height=raster_defn.BBdx,
        ).turn(-1)
        glyphs.append(Glyph(
            raster, codepoint=cp,
            left_bearing=cd.BBox,
            shift_up=cd.BBoy,
            right_bearing=cd.Wx//0x10000-cd.BBox-cd.BBdx,
            # ignoring Wy - vertical advance
        ))
    # decode face number
    encoding = None
    setwidth = 'normal'
    face = cie.face
    if face >= 36:
        face -= 36
    elif face >= 18:
        encoding = 'ascii'
        face -= 18
    else:
        encoding = 'xerox'
    if face >= 12:
        setwidth = 'expanded'
        face -= 12
    elif face >= 6:
        setwidth = 'condensed'
        face -= 6
    weight = ('bold' if face&2 else 'light' if face&4 else 'regular')
    slant = ('italic' if face&1 else 'roman')
    # remaining properties
    props = dict(
        family=ixn.characters.decode('ascii', 'replace'),
        weight=weight,
        slant=slant,
        setwidth=setwidth,
        # encoding flag isn't set right in any of the .ac files seen
        #encoding=encoding,
        dpi=(cie.resolutionX//10, cie.resolutionY//10),
    )
    return props, glyphs
