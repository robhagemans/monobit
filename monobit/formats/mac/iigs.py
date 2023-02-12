"""
monobit.formats.mac.iigs - Apple IIgs font file

Kelvin Sherlock 2023
licence: https://opensource.org/licenses/MIT
"""

import io
import logging

from ...binary import bytes_to_bits, align
from ...struct import bitfield, little_endian as le
from ... import struct
from ...storage import loaders, savers
from ...font import Font, Coord
from ...glyph import Glyph, KernTable
from ...magic import FileFormatError

from itertools import chain, accumulate


# IIgs font file is essentially a little-endian MacOS FONT resource,
# without the resource, plus an extra header.
# Documented in the Apple IIgs Toolbox Reference Volume II, chapter 16-41
# https://archive.org/details/AppleIIGSToolboxReferenceVolume2/mode/2up?view=theater


_NFNT_HEADER = le.Struct(
    #    {font type -- ignored!}
    fontType='uint16',
    #    {character code of first glyph}
    firstChar='uint16',
    #    {character code of last glyph}
    lastChar='uint16',
    #    {maximum glyph width}
    widMax='uint16',
    #    {maximum glyph kern}
    kernMax='int16',
    #    {negative of descent}
    nDescent='int16',
    #    {width of font rectangle}
    fRectWidth='uint16',
    #    {height of font rectangle}
    fRectHeight='uint16',
    #    {offset to width/offset table}
    owTLoc='uint16',
    #    {maximum ascent measurement}
    ascent='uint16',
    #    {maximum descent measurement}
    descent='uint16',
    #    {leading measurement}
    leading='uint16',
    #    {row width of bit image in 16-bit wds}
    rowWords='uint16',
    # followed by:
    # bit image table
    # bitmap location table
    # width offset table
)

_EXTENDED_HEADER = le.Struct(
    #   {high bits of owTLoc -- optional }
    owTLocHigh='uint16',
)

# location table entry
_LOC_ENTRY = le.Struct(
    offset='uint16',
)
# width/offset table entry
# Width/offset table. For every glyph in the font, this table contains a word with the glyph offset
# in the high-order byte and the glyph's width, in integer form, in the low-order byte. The value of
# the offset, when added to the maximum kerning  value for the font, determines the horizontal
# distance from the glyph origin to the left edge of the bit image of the glyph, in pixels. If this
# sum is negative, the glyph origin  is to the right of the glyph image's left edge, meaning the
# glyph kerns to the left.  If the sum is positive, the origin is to the left of the image's left
# edge. If the sum equals zero, the glyph origin corresponds with the left edge of the bit image.
# Missing glyphs are represented by a word value of -1. The last word of this table is also -1,
# representing the end.
_WO_ENTRY = le.Struct(
    width='uint8',
    offset='uint8',
)
# glyph width table entry
_WIDTH_ENTRY = le.Struct(
    width='uint16',
)


_IIGS_HEADER = le.Struct(
    offset='uint16',
    family='uint16',
    style='uint16',
    pointSize='uint16',
    version='uint16',
    fbrExtent='uint16'
)

#
# font style:
# bit 0 = bold
# bit 1 = italic
# bit 2 = underline
# bit 3 = outline
# bit 4 = shadow
#
_STYLE_MAP = {
    0: 'bold',
    1: 'italic',
    2: 'underline',
    3: 'outline',
    4: 'shadow',
}

# Apple IIgs Technote #41, Font Family Numbers
_FONT_NAMES = {
    2: 'New York',
    3: 'Geneva',
    4: 'Monaco',
    5: 'Venice',
    6: 'London',
    7: 'Athens',
    8: 'San Francisco',
    9: 'Toronto',
    11: 'Cairo',
    12: 'Los Angeles',
    13: 'Zapf Dingbats',
    14: 'Bookman',
    15: 'Helvetica Narrow',
    16: 'Palatino',
    18: 'Zapf Chancery',
    20: 'Times',
    21: 'Helvetica',
    22: 'Courier',
    23: 'Symbol',
    24: 'Taliesin',
    33: 'Avant Garde',
    65533: 'Chicago',
    65534: 'Shaston',
}

_NON_ROMAN_NAMES = {
    'Symbol': '',
    'Cairo': '',
    'Taliesin': '',
    'Zapf Dingbats': '',
}


def _bits_to_bytes(iter):
    # output is padded to 16-bits
    rv = []
    i = 7
    scratch = 0
    for b in iter:
        scratch |= b << i
        i -= 1
        if i < 0:
            rv.append(scratch)
            i = 7
            scratch = 0
    if i != 7:
        rv.append(scratch)
    if len(rv) & 0x01:
        rv.append(0)
    return bytes(rv)

def _load_iigs(instream):

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

    # n.b. -- this differs slightly from macintosh
    if header.version >= 0x0105 and len(extra.length) >= 2:
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

    #
    # see mac._convert_nfnt
    #
    if not glyphs:
        return Font()

    glyphs = tuple(
        _glyph.modify(
            left_bearing=_glyph.wo_offset + fontrec.kernMax,
            right_bearing=(
                _glyph.wo_width - _glyph.width
                - (_glyph.wo_offset + fontrec.kernMax)
            )
        )
        if _glyph.wo_width != 0xff and _glyph.wo_offset != 0xff else _glyph
        for _glyph in glyphs
    )

    # codepoint labels
    labelled = [
        _glyph.modify(codepoint=(_codepoint,))
        for _codepoint, _glyph in enumerate(glyphs[:-1], start=fontrec.firstChar)
    ]
    # last glyph is the "missing" glyph
    labelled.append(glyphs[-1].modify(tag='missing'))
    # drop undefined glyphs & their labels, so long as they're empty
    glyphs = tuple(
        _glyph for _glyph in labelled
        if (_glyph.wo_width != 0xff and _glyph.wo_offset != 0xff) or (_glyph.width and _glyph.height)
    )
    # drop mac glyph metrics
    # keep scalable_width
    glyphs = tuple(_glyph.drop('wo_offset', 'wo_width') for _glyph in glyphs)
    # n.b. no kerning table.
    # n.b. no encoding table.

    # store properties

    style = ' '.join(
        _tag for _bit, _tag in _STYLE_MAP.items() if header.style & (1 << _bit)
    )


    properties = {
        'family': name,
        'style': style,
        'source-format': 'IIgs v{}.{}'.format(*divmod(header.version, 256)),
        'point-size': header.pointSize,
        'default-char': 'missing',
        'ascent': fontrec.ascent,
        'descent': fontrec.descent,
        'leading': fontrec.leading,
        'line-height': fontrec.ascent + fontrec.descent + fontrec.leading,
        'shift-up': -fontrec.descent,
        'iigs.family-id': header.family,
    }
    if name not in _NON_ROMAN_NAMES: properties['encoding'] = 'mac-roman'

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

    return Font(glyphs, **properties).label()


def _subset(font):
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
            font.get_glyph(char=str(bytes([_chr]),encoding="mac-roman"), missing=None)
            for _chr in range(0, 256)
        ]

    if not glyphs:
        raise FileFormatError('No suitable characters for IIgs font.')

    glyphs = [_g.modify(codepoint=_ix) for _ix, _g in enumerate(glyphs) if _g]

    glyphs.append(font.get_default_glyph())

    font = font.modify(glyphs, encoding=None)
    return font

# trim the horizontal and expand the vertical
# in preparation for generating the font strike data
def _normalize_glyph(g, ascent, descent):
    if not g: return None
    g = g.reduce() # shrink to fit
    shift = g.shift_up
    height = g.height
    if shift == -descent and height == ascent + descent : return g
    return g.expand(bottom = shift + descent, top = ascent - height - shift)



def _normalize_metrics(font):
    # recalculate ascent/descent.

    bounds = font.ink_bounds
    ascent = font.ascent
    descent = font.descent

    if ascent != bounds.top:
        logging.info("Ascent = %d ; calculated ascent = %d", ascent, bounds.top)
        ascent = max(ascent, bounds.top)
    if descent != -bounds.bottom:
        logging.info("Descent = %d ; calculated descent = %d", descent, -bounds.bottom)
        descent = max(descent, -bounds.bottom)


    glyphs = font.glyphs
    glyphs = tuple(_normalize_glyph(_g, ascent, descent) for _g in glyphs)

    # calculate kerning.  only negative kerning is handled
    kern = min( _g.left_bearing for _g in glyphs)
    if kern < 0 : kern = -kern
    else: kern = 0

    glyphs = tuple(_g.modify(wo_offset = _g.left_bearing + kern, wo_width = _g.advance_width) for _g in glyphs)

    if any(_g for _g in glyphs if _g.wo_width >= 255):
        raise FileFormatError('IIgs character width must be < 255')

    if any(_g for _g in glyphs if _g.wo_offset >= 255):
        raise FileFormatError('IIgs character offset must be < 255')


    font = font.modify(glyphs, ascent=ascent, descent=descent, kern=kern)
    return font

def _save_iigs(outstream, font):

    font = _subset(font)
    font = _normalize_metrics(font)

    glyphs = font.glyphs
    firstChar = int(glyphs[0].codepoint)
    lastChar = int(glyphs[-2].codepoint)
    missing = glyphs[-1]

    rowbits = sum( _g.width for _g in glyphs)
    rowbits = (rowbits + 0x0f) & ~0x0f


    # build the font-strike data
    mm = (_g.as_matrix() for _g in glyphs)

    fontStrike = b''.join(
        _bits_to_bytes(chain(*_row))
        for _row in zip(*mm)
    )


    # build the location table
    empty = Glyph(wo_offset=255,wo_width=255)
    glyph_table = [font.get_glyph(codepoint=_code, missing=empty) for _code in range(firstChar, lastChar+1)]
    glyph_table.append(missing)


    # empty entry needed at the end.
    wo_table = b''.join(
        bytes(_WO_ENTRY(width = _g.wo_width, offset = _g.wo_offset))
        for _g in chain(glyph_table, [empty])
    )

    loc_table = b''.join(
        bytes(_LOC_ENTRY(offset = _offset))
        for _offset in accumulate( (_g.width for _g in glyph_table), initial=0)
    )


    header = _IIGS_HEADER()
    fontrec = _NFNT_HEADER()

    extra = bytes()

    fontrec.fontType = 0
    fontrec.firstChar = firstChar
    fontrec.lastChar = lastChar

    ascent = font.ascent
    descent = font.descent
    kern = font.kern

    fontrec.widMax = max(_g.advance_width for _g in glyphs)
    fontrec.kernMax = -kern
    fontrec.nDescent = -descent
    fontrec.fRectWidth = max(_g.width + _g.left_bearing + kern for _g in glyphs)
    fontrec.fRectHeight = ascent + descent
    fontrec.ascent = ascent
    fontrec.descent = descent
    fontrec.leading = font.leading

    fontrec.rowWords = rowbits >> 4 # / 16

    try:
        family_id = int(font.get_property('iigs.family-id'), 10)
    except Exception as e:
        family_id = 0

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


    # if offset > 32 bits, need to use v 1.05
    offset = (len(fontStrike) + len(loc_table) + 10) >> 1
    if offset > 0xffff:
        header.version = 0x0105
        offset += 1 # account for extra header word.
        extra = _EXTENDED_HEADER(owTLocHigh = offset >> 16)

    fontrec.owTLoc = offset & 0xffff

    logging.debug("Fontrec: %s", fontrec)

    name = font.family.encode('mac-roman', errors='replace')
    data = b''.join([
        bytes([len(name)]), name,
        bytes(header),
        bytes(extra),
        bytes(fontrec),
        fontStrike,
        loc_table,
        wo_table
    ])

    outstream.write(data)
