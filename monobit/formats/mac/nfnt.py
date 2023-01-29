"""
monobit.formats.mac.nfnt - Mac FONT/NFNT fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...binary import bytes_to_bits
from ...struct import bitfield, big_endian as be
from ...font import Font
from ...glyph import Glyph, KernTable
from ...streams import FileFormatError


##############################################################################
# NFNT/FONT resource

# the Font Type Element
# https://developer.apple.com/library/archive/documentation/mac/Text/Text-251.html#MARKER-9-442
_FONT_TYPE = be.Struct(
    # 15    Reserved. Should be set to 0.
    reserved_15=bitfield('uint16', 1),
    # 14    This bit is set to 1 if the font is not to be expanded to match the screen depth. The
    #       font is for color Macintosh computers only if this bit is set to 1. This is for some
    #       fonts, such as Kanji, which are too large for synthetic fonts to be effective or
    #       meaningful, or bitmapped fonts that are larger than 50 points.
    dont_expand_to_match_screen_depth=bitfield('uint16', 1),
    # 13    This bit is set to 1 if the font describes a fixed-width font, and is set to 0 if the
    #       font describes a proportional font. The Font Manager does not check the setting of this bit.
    fixed_width=bitfield('uint16', 1),
    # 12    Reserved. Should be set to 1.
    reserved_12=bitfield('uint16', 1),
    # 10-11 Reserved. Should be set to 0.
    reserved_10_11=bitfield('uint16', 2),
    # 9     This bit is set to 1 if the font contains colors other than black. This font is for
    #       color Macintosh computers only if this bit is set to 1.
    has_colors=bitfield('uint16', 1),
    # 8     This bit is set to 1 if the font is a synthetic font, created dynamically from the
    #       available font resources in response to a certain color and screen depth combination.
    #       The font is for color Macintosh computers only if this bit is set to 1.
    synthetic=bitfield('uint16', 1),
    # 7     This bit is set to 1 if the font has a font color table ('fctb') resource. The font
    #       is for color Macintosh computers only if this bit is set to 1.
    has_fctb=bitfield('uint16', 1),
    # 4-6   Reserved. Should be set to 0.
    reserved_4_6=bitfield('uint16', 3),
    # 2-3   These two bits define the depth of the font. Each of the four possible values indicates
    #       the number of bits (and therefore, the number of colors) used to represent each pixel
    #       in the glyph images.
    #       Value    Font depth    Number of colors
    #           0    1-bit    1
    #           1    2-bit    4
    #           2    4-bit    16
    #           3    8-bit    256
    #       Normally the font depth is 0 and the glyphs are specified as monochrome images. If
    #       bit 7 of this field is set to 1, a resource of type 'fctb' with the same ID as the font
    #       can optionally be provided to assign RGB colors to specific pixel values.
    #
    # If this font resource is a member of a font family, the settings of bits 8 and 9 of the
    # fontStyle field in this font's association table entry should be the same as the settings of
    # bits 2 and 3 in the fontType field. For more information, see "The Font Association Table"
    # on page 4-89.
    depth=bitfield('uint16', 2),
    # 1    This bit is set to 1 if the font resource contains a glyph-width table.
    has_width_table=bitfield('uint16', 1),
    # 0 This bit is set to 1 if the font resource contains an image height table.
    has_height_table=bitfield('uint16', 1),
)


# the header of the NFNT is a FontRec
# https://developer.apple.com/library/archive/documentation/mac/Text/Text-214.html
_NFNT_HEADER = be.Struct(
    #    {font type}
    fontType=_FONT_TYPE,
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
    # glyph-width table
    # image height table
)

# location table entry
_LOC_ENTRY = be.Struct(
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
_WO_ENTRY = be.Struct(
    offset='uint8',
    width='uint8',
)
# glyph width table entry
# > Glyph-width table. For every glyph in the font, this table contains a word
# > that specifies the glyph's fixed-point glyph width at the given point size
# > and font style, in pixels. The Font Manager gives precedence to the values
# > in this table over those in the font family glyph-width table. There is an
# > unsigned integer in the high-order byte and a fractional part in the
# > low-order byte. This table is optional.
_WIDTH_ENTRY = be.Struct(
    width='uint16', # divide by 256
)
# height table entry
# Image height table. For every glyph in the font, this table contains a word that specifies the
# image height of the glyph, in pixels. The image height is the height of the glyph image and is
# less than or equal to the font height. QuickDraw uses the image height for improved character
# plotting, because it only draws the visible part of the glyph. The high-order byte of the word is
# the offset from the top of the font rectangle of the first non-blank (or nonwhite) row in the
# glyph, and the low-order byte is the number of rows that must be drawn. The Font Manager creates
# this table.
_HEIGHT_ENTRY = be.Struct(
    offset='uint8',
    height='uint8',
)


def _extract_nfnt(data, offset):
    """Read a MacOS NFNT or FONT resource."""
    # this is not in the header documentation but is is mentioned here:
    # https://www.kreativekorp.com/swdownload/lisa/AppleLisaFontFormat.pdf
    compressed = data[offset+1] & 0x80
    if compressed:
        data = _uncompress_nfnt(data, offset)
        offset = 0
    fontrec = _NFNT_HEADER.from_bytes(data, offset)
    if not (fontrec.rowWords and fontrec.widMax and fontrec.fRectWidth and fontrec.fRectHeight):
        logging.debug('Empty FONT/NFNT resource.')
        return dict(glyphs=(), fontrec=fontrec)
    if fontrec.fontType.depth or fontrec.fontType.has_fctb:
        raise FileFormatError('Anti-aliased or colour fonts not supported.')
    # read char tables & bitmaps
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
    # https://developer.apple.com/library/archive/documentation/mac/Text/Text-252.html
    if fontrec.nDescent > 0:
        wo_offset = fontrec.nDescent << 16 + fontrec.owTLoc * 2
    else:
        wo_offset = fontrec.owTLoc * 2
    # owtTLoc is offset "from itself" to table
    wo_table = _WO_ENTRY.array(n_chars).from_bytes(data, offset + 16 + wo_offset)
    # scalable width table
    width_offset = wo_offset + _WO_ENTRY.size * n_chars
    if fontrec.fontType.has_width_table:
        width_table = _WIDTH_ENTRY.array(n_chars).from_bytes(data, width_offset)
    # image height table: this can be deduced from the bitmaps
    # https://developer.apple.com/library/archive/documentation/mac/Text/Text-250.html#MARKER-9-414
    # > The Font Manager creates this table.
    if fontrec.fontType.has_height_table:
        height_offset = width_offset
        if fontrec.fontType.has_width_table:
            height_offset += _WIDTH_ENTRY.size * n_chars
        height_table = _HEIGHT_ENTRY.array(n_chars).from_bytes(data, height_offset)
    # parse bitmap strike
    bitmap_strike = bytes_to_bits(strike)
    rows = [
        bitmap_strike[_offs:_offs+fontrec.rowWords*16]
        for _offs in range(0, len(bitmap_strike), fontrec.rowWords*16)
    ]
    # if the font was compressed, we need to XOR the bitmap rows
    if compressed:
        xoredrows = rows
        rows = [xoredrows[0]]
        for row in xoredrows[1:]:
            rows.append(tuple(_r ^ _p for _r, _p in zip(row, rows[-1])))
    # extract width from width/offset table
    # (do we need to consider the width table, if defined?)
    locs = [_loc.offset for _loc in loc_table]
    glyphs = [
        Glyph([_row[_offs:_next] for _row in rows])
        for _offs, _next in zip(locs[:-1], locs[1:])
    ]
    # add glyph metrics
    # scalable-width table
    if fontrec.fontType.has_width_table:
        glyphs = tuple(
            # fixed-point value, unsigned integer in the high-order byte
            # and a fractional part in the low-order byte
            _glyph.modify(scalable_width=f'{_we.width / 256:.2f}')
            for _glyph, _we in zip(glyphs, width_table)
        )
    # image-height table
    # > The Font Manager creates this table.
    # this appears to mean any stored contents may well be meaningless
    #
    # if fontrec.fontType.has_height_table:
    #     glyphs = tuple(
    #         _glyph.modify(image_height=_he.height, top_offset=_he.offset)
    #         for _glyph, _he in zip(glyphs, height_table)
    #     )
    # width & offset
    glyphs = tuple(
        _glyph.modify(wo_offset=_wo.offset, wo_width=_wo.width)
        for _glyph, _wo in zip(glyphs, wo_table)
    )
    return dict(
        glyphs=glyphs,
        fontrec=fontrec,
    )


# https://www.kreativekorp.com/swdownload/lisa/AppleLisaFontFormat.pdf
_COMPRESSED_HEADER = be.Struct(
    type='uint16',
    compressedLength='uint32',
    decompressedLength='uint32',
)

def _uncompress_nfnt(data, offset):
    """Decompress a compressed FONT/NFNT resource."""
    header = _COMPRESSED_HEADER.from_bytes(data, offset)
    offset += _COMPRESSED_HEADER.size
    payload = data[offset:offset+header.compressedLength]
    iter = reversed(payload)
    output = bytearray()
    for byte in iter:
        for bit in reversed(bytes_to_bits(bytes((byte,)))):
            if bit:
                output.append(0)
            else:
                try:
                    output.append(next(iter))
                except StopIteration:
                    break
    # bitmap rows still need to be XORed afterwards
    return bytes((data[0], data[1] ^ 0x80)) + bytes(reversed(output))


def _convert_nfnt(properties, glyphs, fontrec):
    """Convert mac glyph metrics to monobit glyph metrics."""
    # the 'width' in the width/offset table is the pen advance
    # while the 'offset' is the (positive) offset after applying the
    # (positive or negative) 'kernMax' global offset
    #
    # since
    #   (glyph) advance_width == left_bearing + width + right_bearing
    # after this transformation we should have
    #   (glyph) advance_width == wo.width
    # which means
    #   (total) advance_width == wo.width - kernMax
    # since
    #   (total) advance_width == (font) left_bearing + glyph.advance_width + (font) right_bearing
    # and (font) left_bearing = -kernMax
    # we need to adjust for kernMax on both left and right bearings - it is an
    # offset only, not a tightening of the advance wiidth
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
    # store kerning table
    if properties.get('kerning-table', None):
        kern_table = sorted(
            (
                _entry.kernFirst, _entry.kernSecond,
                _entry.kernWidth * properties['point-size'] / 2**12
            )
            for _entry in properties['kerning-table']
        )
        glyphs = tuple(
            _glyph.modify(right_kerning=KernTable({
                _right: f'{_width:.2f}'
                for _left, _right, _width in kern_table
                if _left == int(_glyph.codepoint)
            }))
            for _glyph in glyphs
        )
    # store glyph-name encoding table
    if properties.get('encoding-table', None):
        tag_table = {
            _entry[:1]: _entry[1:].decode('mac-roman')
            for _entry in properties['encoding-table']
        }
        glyphs = tuple(
            _glyph.modify(tag=tag_table.get(_glyph.codepoint, ''))
            for _glyph in glyphs
        )
    # store properties
    properties.update({
        # not overridable; also seems incorrect for system fonts
        #'spacing': 'monospace' if fontrec.fontType.fixed_width else 'proportional',
        'default-char': 'missing',
        'ascent': fontrec.ascent,
        'descent': fontrec.descent,
        'line-height': fontrec.ascent + fontrec.descent + fontrec.leading,
        'shift-up': -fontrec.descent,
        # remove the kerning table and encoding table now stored in glyphs
        'kerning-table': None,
        'encoding-table': None,
        'source-format': 'NFNT',
    })
    return Font(glyphs, **properties)
