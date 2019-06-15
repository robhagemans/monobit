"""
monobit.mac - MacOS suitcases and resources

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .binary import friendlystruct, bytes_to_bits
from .typeface import Typeface
from .font import Font, Glyph


##############################################################################
# AppleSingle/AppleDouble
# see https://web.archive.org/web/20160304101440/http://kaiser-edv.de/documents/Applesingle_AppleDouble_v1.html

_APPLE_HEADER = friendlystruct(
    'be',
    magic='uint32',
    version='uint32',
    home_fs='16s',
    number_entities='uint16',
)
_APPLE_ENTRY = friendlystruct(
    'be',
    entry_id='uint32',
    offset='uint32',
    length='uint32',
)

_APPLESINGLE_MAGIC = 0x00051600
_APPLEDOUBLE_MAGIC = 0x00051607

# Entry IDs
# Data fork       1       standard Macintosh data fork
# Resource fork   2       standard Macintosh resource fork
# Real name       3       file's name in its home file system
# Comment         4       standard Macintosh comments
# Icon, B&W       5       standard Macintosh black-and-white icon
# Icon, color     6       Macintosh color icon
# file info       7       file information: attributes and so on
# Finder info     9       standard Macintosh Finder information
_ID_RESOURCE = 2

##############################################################################
# resource fork/dfont format
# see https://developer.apple.com/library/archive/documentation/mac/pdf/MoreMacintoshToolbox.pdf

# Page 1-122 Figure 1-12 Format of a resource header in a resource fork
_RSRC_HEADER = friendlystruct(
    'be',
    data_offset='uint32',
    map_offset='uint32',
    data_length='uint32',
    map_length='uint32',
    # header is padded with zeros to 256 bytes
    # https://github.com/fontforge/fontforge/blob/master/fontforge/macbinary.c
    reserved='240s',
)

# Figure 1-13 Format of resource data for a single resource
_DATA_HEADER = friendlystruct(
    'be',
    length='uint32',
    # followed by `length` bytes of data
)

# Figure 1-14 Format of the resource map in a resource fork
_MAP_HEADER = friendlystruct(
    'be',
    reserved_header='16s',
    reserved_handle='4s',
    reserved_fileref='2s',
    attributes='uint16',
    type_list_offset='uint16',
    name_list_offset='uint16',
    # number of types minus 1
    last_type='uint16',
    # followed by:
    # type list
    # reference lists
    # name list
)
# Figure 1-15 Format of an item in a resource type list
_TYPE_ENTRY = friendlystruct(
    'be',
    rsrc_type='4s',
    # number of resources minus 1
    last_rsrc='uint16',
    ref_list_offset='uint16',
)

# Figure 1-16 Format of an entry in the reference list for a resource type
_REF_ENTRY = friendlystruct(
    'be',
    rsrc_id='uint16',
    name_offset='uint16',
    attributes='uint8',
    # we need a 3-byte offset, will have to construct ourselves...
    data_offset_hi='uint8',
    data_offset='uint16',
    reserved_handle='4s',
)

# Figure 1-17 Format of an item in a resource name list
# 1-byte length followed by bytes


##############################################################################
# NFNT/FONT resource

# the header of the NFNT is a FontRec
# https://developer.apple.com/library/archive/documentation/mac/Text/Text-214.html
_NFNT_HEADER = friendlystruct(
    'be',
    #    {font type}
    fontType='uint16',
    #    {character code of first glyph}
    firstChar='uint16',
    #    {character code of last glyph}
    lastChar='uint16',
    #    {maximum glyph width}
    widMax='uint16',
    #    {maximum glyph kern}
    kernMax='uint16',
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
_LOC_ENTRY = friendlystruct(
    'be',
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
_WO_ENTRY = friendlystruct(
    'be',
    offset='uint8',
    width='uint8',
)
# glyph width table entry
_WIDTH_ENTRY = friendlystruct(
    'be',
    width='uint16',
)
# height table entry
# Image height table. For every glyph in the font, this table contains a word that specifies the
# image height of the glyph, in pixels. The image height is the height of the glyph image and is
# less than or equal to the font height. QuickDraw uses the image height for improved character
# plotting, because it only draws the visible part of the glyph. The high-order byte of the word is
# the offset from the top of the font rectangle of the first non-blank (or nonwhite) row in the
# glyph, and the low-order byte is the number of rows that must be drawn. The Font Manager creates
# this table.
_HEIGHT_ENTRY = friendlystruct(
    'be',
    offset='uint8',
    height='uint8',
)

##############################################################################

@Typeface.loads('dfont', 'suit', name='MacOS resource fork', binary=True)
def load(instream):
    """Load a MacOS suitcase."""
    data = instream.read()
    return _parse_resource_fork(data)

@Typeface.loads('apple', name='AppleSingle/AppleDouble', binary=True)
def load(instream):
    """Load an AppleSingle or AppleDouble file."""
    data = instream.read()
    return _parse_apple(data)

##############################################################################

def _parse_apple(data):
    """Parse an AppleSingle or AppleDouble file."""
    header = _APPLE_HEADER.from_bytes(data)
    if header.magic not in (_APPLESINGLE_MAGIC, _APPLEDOUBLE_MAGIC):
        raise ValueError('Not an AppleSingle or AppleDouble file.')
    entry_array = _APPLE_ENTRY * header.number_entities
    entries = entry_array.from_buffer_copy(data, _APPLE_HEADER.size)
    for entry in entries:
        if entry.entry_id == _ID_RESOURCE:
            fork_data = data[entry.offset:entry.offset+entry.length]
            return _parse_resource_fork(fork_data)
    raise ValueError('No resource fork found.')


def _parse_resource_fork(data):
    """Parse a MacOS resource fork."""
    rsrc_header = _RSRC_HEADER.from_bytes(data)
    map_header = _MAP_HEADER.from_bytes(data, rsrc_header.map_offset)
    type_array = _TYPE_ENTRY * (map_header.last_type + 1)
    # +2 because the length field is considered part of the type list
    type_list_offset = rsrc_header.map_offset + map_header.type_list_offset + 2
    type_list = type_array.from_buffer_copy(data, type_list_offset)
    fonts = []
    for type_entry in type_list:
        ref_array = _REF_ENTRY * (type_entry.last_rsrc + 1)
        ref_list = ref_array.from_buffer_copy(
            data, type_list_offset -2 + type_entry.ref_list_offset
        )
        # TODO: FOND
        if type_entry.rsrc_type in (b'FONT', b'NFNT'):
            for ref_entry in ref_list:
                # TODO: get name from name list
                # construct the 3-byte integer
                data_offset = ref_entry.data_offset_hi * 0x10000 + ref_entry.data_offset
                try:
                    fonts.append(_parse_nfnt(
                        data, rsrc_header.data_offset + _DATA_HEADER.size
                        + data_offset
                    ))
                except ValueError as e:
                    logging.error('Could not load font: %s', e)
    return Typeface(fonts)

def _parse_nfnt(data, offset):
    """Parse a MacOS NFNT or FONT resource."""
    fontrec = _NFNT_HEADER.from_bytes(data, offset)
    if not fontrec.rowWords:
        raise ValueError('Empty NFNT resource.')
    # extract bit fields
    has_height_table = bool(fontrec.fontType & 0x1)
    has_width_table = bool(fontrec.fontType & 0x2)
    # 1-bit 2-bit 4-bit 8-bit depth
    depth = (fontrec.fontType & 0xc) >> 2
    has_ftcb = bool(fontrec.fontType & 0x80)
    if depth or has_ftcb:
        raise ValueError('Anti-aliased or colour fonts not supported.')
    # bit 13: is fixed-width; ignored by Font Manager (and us)
    # table offsets
    strike_offset = offset + _NFNT_HEADER.size
    loc_offset = offset + _NFNT_HEADER.size + fontrec.fRectHeight * fontrec.rowWords * 2
    # bitmap strike
    strike = data[strike_offset:loc_offset]
    # location table
    n_chars = fontrec.lastChar - fontrec.firstChar + 1
    # loc table should have one extra entry to be able to determine widths
    loc_table = (_LOC_ENTRY * (n_chars+1)).from_buffer_copy(data, loc_offset)
    # width offset table
    # https://developer.apple.com/library/archive/documentation/mac/Text/Text-252.html
    if fontrec.nDescent > 0:
        wo_offset = fontrec.nDescent << 16 + fontrec.owTLoc
    else:
        wo_offset = fontrec.owTLoc
    wo_table = (_WO_ENTRY * n_chars).from_buffer_copy(data, wo_offset)
    width_offset = wo_offset + _WO_ENTRY.size * n_chars
    if has_width_table:
        width_table = (_WIDTH_ENTRY * n_chars).from_buffer_copy(data, width_offset)
        height_offset = width_offset + _WIDTH_ENTRY.size * n_chars
    else:
        # FIXME: get width table from the "font family glyph-width table" (?)
        height_offset = width_offset
    if has_height_table:
        height_table = (_HEIGHT_ENTRY * n_chars).from_buffer_copy(data, height_offset)
    # parse bitmap strike
    bitmap_strike = bytes_to_bits(strike)
    rows = [
        bitmap_strike[_offs:_offs+fontrec.rowWords*16]
        for _offs in range(0, len(bitmap_strike), fontrec.rowWords*16)
    ]
    # extract width from width/offset table
    # (do we need to consider the width table, if defined?)
    offsets = [_loc.offset for _loc in loc_table]
    glyphs = [
        Glyph([_row[_offs:_next] for _row in rows])
        for _offs, _next in zip(offsets[:-1], offsets[1:])
    ]
    # ordinal labels
    labels = {_l: _i for _i, _l in enumerate(range(fontrec.firstChar, fontrec.lastChar+1))}
    # TODO: parse the width/offset table
    # TODO: store properties
    return Font(glyphs, labels, comments=(), properties=())
