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
    _convert_nfnt, _extract_nfnt
)
from .dfont import _FONT_NAMES, _NON_ROMAN_NAMES


# IIgs font file is essentially a little-endian MacOS FONT resource,
# without the resource, plus an extra header.
# Documented in the Apple IIgs Toolbox Reference Volume II, chapter 16-41
# https://archive.org/details/AppleIIGSToolboxReferenceVolume2/


# font style:
_STYLE_TYPE = le.Struct(
    # bit 0 = bold
    bold=bitfield('uint16', 1),
    # bit 1 = italic
    italic=bitfield('uint16', 1),
    # bit 2 = underline
    underline=bitfield('uint16', 1),
    # bit 3 = outline
    outline=bitfield('uint16', 1),
    # bit 4 = shadow
    shadow=bitfield('uint16', 1),
)

_IIGS_HEADER = le.Struct(
    offset='uint16',
    family='uint16',
    style=_STYLE_TYPE,
    pointSize='uint16',
    version='uint16',
    fbrExtent='uint16',
)

# the extended header is defined in Apple IIgs Toolbox Reference Volume III, ch. 43-5
# https://archive.org/details/Apple_IIGS_Toolbox_Reference_vol_3/page/n459/
_EXTENDED_HEADER = le.Struct(
    #   {high bits of owTLoc -- optional }
    owTLocHigh='uint16',
)


# fontType is ignored
# glyph-width table and image-height table not included
_NFNT_HEADER = nfnt_header_struct(le)

_LOC_ENTRY = loc_entry_struct(le)
_WO_ENTRY = wo_entry_struct(le)
_WIDTH_ENTRY = width_entry_struct(le)


def _load_iigs(instream):
    """Load a IIgs font."""
    data = instream.read()
    # p-string name
    offset = data[0] + 1
    name = data[1:offset].decode('mac-roman')
    header = _IIGS_HEADER.from_bytes(data, offset)
    logging.debug('IIgs header: %s', header)
    # offset given in 16-bit words
    extra = data[offset+_IIGS_HEADER.size : offset + header.offset*2]
    offset += header.offset * 2
    # extended header for IIgs
    if header.version >= 0x0105: #  and len(extra) >= 2:
        eh = _EXTENDED_HEADER.from_bytes(extra)
        logging.debug('extended header: %s', eh)
    else:
        eh = _EXTENDED_HEADER()
    # read IIgs-style NFNT resource
    fontdata = _extract_nfnt(
        data, offset, endian='little',
        owt_loc_high=eh.owTLocHigh, font_type=b'\0\0'
    )
    return _convert_iigs(**fontdata, header=header, name=name)


def _convert_iigs(glyphs, fontrec, header, name):
    """Convert IIgs font data to monobit font."""
    font = _convert_nfnt({}, glyphs, fontrec)
    # properties from IIgs header
    properties = {
        'family': name,
        'point-size': header.pointSize,
        'source-format': 'IIgs v{}.{}'.format(*divmod(header.version, 256)),
        'iigs.family-id': header.family,
    }
    if name not in _NON_ROMAN_NAMES:
        properties['encoding'] = 'mac-roman'
    # decode style field
    if header.style.bold:
        properties['weight'] = 'bold'
    if header.style.italic:
        properties['slant'] = 'italic'
    decoration = []
    if header.style.underline:
        decoration.append('underline')
    if header.style.outline:
        decoration.append('outline')
    if header.style.shadow:
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


def _create_iigs_nfnt(font):
    """Create NFNT section of Apple IIgs font file."""
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
    # build the width-offset table
    wo_table = b''.join(
        # glyph.wo_width and .wo_offset set in normalise_metrics
        bytes(_WO_ENTRY(width=_g.wo_width, offset=_g.wo_offset))
        # empty entry needed at the end.
        for _g in chain(glyph_table, [empty])
    )
    # build the location table
    loc_table = b''.join(
        bytes(_LOC_ENTRY(offset=_offset))
        for _offset in accumulate((_g.width for _g in glyph_table), initial=0)
    )
    # owTLoc is the offset from the field itself
    # the remaining size of the header including owTLoc is 5 words
    owt_loc = (len(font_strike) + len(loc_table) + 10) >> 1
    # generate NFNT header
    fontrec = _NFNT_HEADER(
        #fontType=0,
        firstChar=first_char,
        lastChar=last_char,
        widMax=max(_g.advance_width for _g in glyphs),
        kernMax=-kern,
        nDescent=font.ink_bounds.bottom,
        # font rectangle == font bounding box
        #max(_g.width + _g.left_bearing + kern for _g in glyphs),
        fRectWidth=font.bounding_box.x,
        fRectHeight=font.bounding_box.y,
        # word offset to width/offset table
        owTLoc=owt_loc & 0xffff,
        # docs define fRectHeight = ascent + descent
        # and generally suggest ascent and descent equal ink bounds
        # that's also monobit's *default* ascent & descent but is overridable
        ascent=font.ink_bounds.top,
        descent=-font.ink_bounds.bottom,
        # define leading in terms of bounding box, not pixel-height
        leading=font.line_height - font.bounding_box.y,
        rowWords=strike_raster.width // 16,
    )
    owt_loc_high = owt_loc >> 16
    logging.debug('NFNT header: %s', fontrec)
    data = b''.join((
        bytes(fontrec),
        font_strike,
        loc_table,
        wo_table
    ))
    # fbr = max width from origin (including whitespace) and right kerned pixels
    # for IIgs header
    fbr_extent = max(
        _g.width + _g.left_bearing + max(_g.right_bearing, 0)
        for _g in glyphs
    )
    return data, owt_loc_high, fbr_extent


def _save_iigs(outstream, font, version=None):
    """Save an Apple IIgs font file."""
    nfnt, owt_loc_high, fbr_extent = _create_iigs_nfnt(font)
    # if offset > 32 bits, need to use iigs format v1.05
    if version is None:
        if owt_loc_high:
            version = 0x0105
        else:
            version = 0x0101
    # generate IIgs header
    # note that this only includes font metadata
    # so no need for the subsetted font that NFNT stored
    header = _IIGS_HEADER(
        # include 1 word for extended header if used
        offset=_IIGS_HEADER.size // 2 + (version >= 0x105),
        family=int(font.get_property('iigs.family-id') or '0', 10),
        style=_STYLE_TYPE(
            bold=font.weight in ('bold', 'extra-bold', 'ultrabold', 'heavy'),
            italic=font.slant in ('italic', 'oblique'),
            underline='underline' in font.decoration,
            outline='outline' in font.decoration,
            shadow='shadow' in font.decoration,
        ),
        # font format version
        version=version,
        # fbr = max width from origin (including whitespace) and right kerned pixels
        fbrExtent=fbr_extent,
        pointSize=font.point_size,
    )
    if version == 0x0105:
        # extended header comes before fontrec
        # so no need to increase owTLoc by 1 word because of its existence
        extra = _EXTENDED_HEADER(owTLocHigh=owt_loc_high)
    else:
        extra = b''
        if owt_loc_high:
            raise FileFormatError(
                'Bitmap strike too large for IIgs v1.1, use v1.5 instead.'
            )
    # write out name field, headers and NFNT
    name = font.family.encode('mac-roman', errors='replace')
    outstream.write(b''.join((
        bytes((len(name),)), name,
        bytes(header),
        bytes(extra),
    )))
    outstream.write(nfnt)
