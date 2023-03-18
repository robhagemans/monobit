"""
monobit.formats.mac.iigs - Apple IIgs font file

Kelvin Sherlock 2023
licence: https://opensource.org/licenses/MIT
"""

import io
import logging
from itertools import chain, accumulate

from ...binary import bytes_to_bits, align
from ...struct import bitfield, little_endian as le
from ... import struct
from ...storage import loaders, savers
from ...font import Font, Coord
from ...glyph import Glyph, KernTable
from ...magic import FileFormatError
from ...raster import Raster

from .nfnt import (
    nfnt_header_struct, loc_entry_struct, wo_entry_struct, width_entry_struct,
    _convert_nfnt,
)
from .dfont import _FONT_NAMES, _NON_ROMAN_NAMES


# IIgs font file is essentially a little-endian MacOS FONT resource,
# without the resource, plus an extra header.
# Documented in the Apple IIgs Toolbox Reference Volume II, chapter 16-41
# https://archive.org/details/AppleIIGSToolboxReferenceVolume2/


# fontType is ignored
# glyph-width table and image-height table not included

_NFNT_HEADER = nfnt_header_struct(le)
_EXTENDED_HEADER = le.Struct(
    #   {high bits of owTLoc -- optional }
    owTLocHigh='uint16',
)

_IIGS_HEADER = le.Struct(
    offset='uint16',
    family='uint16',
    style='uint16',
    pointSize='uint16',
    version='uint16',
    fbrExtent='uint16',
)

_LOC_ENTRY = loc_entry_struct(le)
_WO_ENTRY = wo_entry_struct(le)
_WIDTH_ENTRY = width_entry_struct(le)

# font style:
# bit 0 = bold
# bit 1 = italic
# bit 2 = underline
# bit 3 = outline
# bit 4 = shadow
_STYLE_MAP = {
    0: 'bold',
    1: 'italic',
    2: 'underline',
    3: 'outline',
    4: 'shadow',
}


def _load_iigs(instream):
    """Load a IIgs font."""
    data = instream.read()
    # p-string name
    offset = data[0]
    name = data[1:offset+1]
    name = name.decode('mac-roman')
    offset += 1
    header = _IIGS_HEADER.from_bytes(data, offset)
    header.offset *= 2
    extra = data[offset + 12:header.offset]
    offset += header.offset
    has_extended_header = header.version >= 0x0105 and len(extra.length) >= 2
    if not has_extended_header:
        extra = None
    glyphs, fontrec = _parse_iigs_nfnt(data, offset, extra)
    return _convert_iigs(glyphs, fontrec, header, name)


def _parse_iigs_nfnt(data, offset, extra):
    """Read little-endian NFNT resource."""
    # see mac._extract_nfnt
    fontrec = _NFNT_HEADER.from_bytes(data, offset)
    # table offsets
    strike_offset = offset + _NFNT_HEADER.size
    loc_offset = offset + _NFNT_HEADER.size + fontrec.fRectHeight * fontrec.rowWords * 2
    # bitmap strike
    strike = data[strike_offset:loc_offset]
    # location table
    # number of chars: coded chars plus missing symbol
    n_chars = fontrec.lastChar - fontrec.firstChar + 2
    # loc table should have one extra entry to be able to determine widths
    loc_table = _LOC_ENTRY.array(n_chars+1).from_bytes(data, loc_offset)

    # width offset table
    wo_offset = fontrec.owTLoc * 2
    # extended header for IIgs
    # n.b. -- this differs slightly from macintosh
    if extra:
        eh = _EXTENDED_HEADER.from_bytes(extra)
        wo_offset += eh.owTLocHigh << 32 # << 16 * 2

    # owtTLoc is offset "from itself" to table
    wo_table = _WO_ENTRY.array(n_chars).from_bytes(data, offset + 16 + wo_offset)
    # scalable width table
    width_offset = wo_offset + _WO_ENTRY.size * n_chars

    # n.b. -- fontType field is unused; there is no width or height table.

    # parse bitmap strike
    bitmap_strike = bytes_to_bits(strike)
    rows = [
        bitmap_strike[_offs:_offs+fontrec.rowWords*16]
        for _offs in range(0, len(bitmap_strike), fontrec.rowWords*16)
    ]
    # extract width from width/offset table
    locs = [_loc.offset for _loc in loc_table]
    glyphs = [
        Glyph([_row[_offs:_next] for _row in rows])
        for _offs, _next in zip(locs[:-1], locs[1:])
    ]
    # width & offset
    glyphs = tuple(
        _glyph.modify(wo_offset=_wo.offset, wo_width=_wo.width)
        for _glyph, _wo in zip(glyphs, wo_table)
    )
    return glyphs, fontrec


def _convert_iigs(glyphs, fontrec, header, name):
    font = _convert_nfnt({}, glyphs, fontrec)
    # properties from IIgs header
    style = ' '.join(
        _tag for _bit, _tag in _STYLE_MAP.items() if header.style & (1 << _bit)
    )
    properties = {
        'family': name,
        'style': style,
        'point-size': header.pointSize,
        'source-format': 'IIgs v{}.{}'.format(*divmod(header.version, 256)),
        'iigs.family-id': header.family,
    }
    if name not in _NON_ROMAN_NAMES:
        properties['encoding'] = 'mac-roman'
    # decode style field
    if header.style & 0x01:
        properties['weight'] = 'bold'
    if header.style & 0x02:
        properties['slant'] = 'italic'
    decoration = []
    if header.style & 0x04:
        decoration.append('underline')
    if header.style & 0x08:
        decoration.append('outline')
    if header.style & 0x10:
        decoration.append('shadow')
    properties['decoration'] = ' '.join(decoration);
    return font.modify(**properties).label()


def _subset(font):
    """Subset to glyphs storable in NFNT and append default glyph."""
    font.label(codepoint_from=font.encoding)
    if font.encoding in ('raw', 'mac-roman', '', None):
        glyphs = [
            font.get_glyph(codepoint=_chr, missing=None)
            for _chr in range(0, 256)
        ]
    elif font.encoding == 'ascii':
        glyphs = [
            font.get_glyph(codepoint=_chr, missing=None)
            for _chr in range(0, 128)
        ]
    else:
        glyphs = [
            font.get_glyph(
                char=str(bytes([_chr]), encoding='mac-roman'),
                missing=None
            )
            for _chr in range(0, 256)
        ]
    if not glyphs:
        raise FileFormatError('No suitable characters for IIgs font')
    glyphs = [_g.modify(codepoint=_ix) for _ix, _g in enumerate(glyphs) if _g]
    glyphs.append(font.get_default_glyph())
    font = font.modify(glyphs, encoding=None)
    return font


def _normalize_glyph(g, ink_bounds):
    """
    Trim the horizontal to glyph's ink bounds
    and expand the vertical to font's ink bounds
    in preparation for generating the font strike data
    """
    if not g:
        return None
    # shrink to fit
    g = g.reduce()
    return g.expand(
        bottom=g.shift_up - ink_bounds.bottom,
        top=ink_bounds.top-g.height-g.shift_up
    )


def _normalize_metrics(font):
    """Calculate metrics for Apple IIgs format."""
    # reduce to ink bounds horizontally, font ink bounds vertically
    glyphs = tuple(_normalize_glyph(_g, font.ink_bounds) for _g in font.glyphs)
    # calculate kerning. only negative kerning is handled
    kern = min(_g.left_bearing for _g in glyphs)
    kern = max(0, -kern)
    # add apple metrics to glyphs
    glyphs = tuple(
        _g.modify(wo_offset=_g.left_bearing+kern, wo_width=_g.advance_width)
        for _g in glyphs
    )
    # check that glyph widths and offsets fit
    if any(_g.wo_width >= 255 for _g in glyphs):
        raise FileFormatError('IIgs character width must be < 255')
    if any(_g.wo_offset >= 255 for _g in glyphs):
        raise FileFormatError('IIgs character offset must be < 255')
    font = font.modify(glyphs)
    return font, kern


def _save_iigs(outstream, font):
    """Save an Apple IIgs font file."""
    # subset the font. we need a font structure to calculate ink bounds
    font = _subset(font)
    font, kern = _normalize_metrics(font)
    # build the font-strike data
    strike_raster = Raster.concatenate(*(_g.pixels for _g in font.glyphs))
    # word-align strike
    strike_raster = strike_raster.expand(right=16-(strike_raster.width%16))
    font_strike = strike_raster.as_bytes()
    # get contiguous glyph list
    glyphs = font.glyphs
    first_char = int(glyphs[0].codepoint)
    last_char = int(glyphs[-2].codepoint)
    empty = Glyph(wo_offset=255, wo_width=255)
    glyph_table = [
        font.get_glyph(codepoint=_code, missing=empty)
        for _code in range(first_char, last_char+1)
    ]
    missing = glyphs[-1]
    glyph_table.append(missing)
    # empty entry needed at the end.
    wo_table = b''.join(
        bytes(_WO_ENTRY(width=_g.wo_width, offset=_g.wo_offset))
        for _g in chain(glyph_table, [empty])
    )
    # build the location table
    loc_table = b''.join(
        bytes(_LOC_ENTRY(offset=_offset))
        for _offset in accumulate((_g.width for _g in glyph_table), initial=0)
    )
    # generate NFNT header
    # glyph.wo_width and .wo_offset set in normalise_metrics
    fontrec = _NFNT_HEADER(
        #fontType=0,
        firstChar=first_char,
        lastChar=last_char,
        widMax=max(_g.advance_width for _g in glyphs),
        kernMax=-kern,
        # font rectangle == font bounding box
        #max(_g.width + _g.left_bearing + kern for _g in glyphs),
        fRectWidth=font.bounding_box.x,
        fRectHeight=font.bounding_box.y,
        # docs define fRectHeight = ascent + descent
        # and generally suggest ascent and descent equal ink bounds
        # that's also monobit's *default* ascent & descent but is overridable
        ascent=font.ink_bounds.top,
        descent=-font.ink_bounds.bottom,
        nDescent=font.ink_bounds.bottom,
        # define leading in terms of bounding box, not pixel-height
        leading=font.line_height - font.bounding_box.y,
        rowWords=strike_raster.width // 16,
    )
    # generate IIgs header
    try:
        family_id = int(font.get_property('iigs.family-id'), 10)
    except Exception as e:
        family_id = 0
    header = _IIGS_HEADER()
    header.offset = 6
    header.family = family_id
    header.style = 0
    header.style += 0b00000001 * (font.weight in ('bold', 'extra-bold', 'ultrabold', 'heavy'))
    header.style += 0b00000010 * (font.slant in ('italic', 'oblique'))
    header.style += 0b00000100 * ('underline' in font.decoration)
    header.style += 0b00001000 * ('outline' in font.decoration)
    header.style += 0b00010000 * ('shadow' in font.decoration)
    header.version = 0x0101
    # fbr = max width from origin (including whitespace) and right kerned pixels
    header.fbrExtent = max(
        _g.width + _g.left_bearing + max(_g.right_bearing, 0)
        for _g in glyphs
    )
    header.pointSize = font.point_size
    # font format version
    # if offset > 32 bits, need to use v 1.05
    extra = bytes()
    offset = (len(font_strike) + len(loc_table) + 10) >> 1
    if offset > 0xffff:
        header.version = 0x0105
        # account for extra header word.
        offset += 1
        extra = _EXTENDED_HEADER(owTLocHigh=offset>>16)
    fontrec.owTLoc = offset & 0xffff
    logging.debug("Fontrec: %s", fontrec)
    # write out headers and NFNT
    name = font.family.encode('mac-roman', errors='replace')
    data = b''.join([
        bytes([len(name)]), name,
        bytes(header),
        bytes(extra),
        bytes(fontrec),
        font_strike,
        loc_table,
        wo_table
    ])
    outstream.write(data)
