"""
monobit.mac - MacOS suitcases and resources

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..binary import bytes_to_bits
from ..struct import bitfield, big_endian as be
from .. import struct
from ..storage import loaders, savers
from ..font import Font, Glyph, Coord


##############################################################################
# AppleSingle/AppleDouble
# see https://web.archive.org/web/20160304101440/http://kaiser-edv.de/documents/Applesingle_AppleDouble_v1.html

_APPLE_HEADER = be.Struct(
    magic='uint32',
    version='uint32',
    home_fs='16s',
    number_entities='uint16',
)
_APPLE_ENTRY = be.Struct(
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
_RSRC_HEADER = be.Struct(
    data_offset='uint32',
    map_offset='uint32',
    data_length='uint32',
    map_length='uint32',
    # header is padded with zeros to 256 bytes
    # https://github.com/fontforge/fontforge/blob/master/fontforge/macbinary.c
    reserved='240s',
)

# Figure 1-13 Format of resource data for a single resource
_DATA_HEADER = be.Struct(
    length='uint32',
    # followed by `length` bytes of data
)

# Figure 1-14 Format of the resource map in a resource fork
_MAP_HEADER = be.Struct(
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
_TYPE_ENTRY = be.Struct(
    rsrc_type='4s',
    # number of resources minus 1
    last_rsrc='uint16',
    ref_list_offset='uint16',
)

# Figure 1-16 Format of an entry in the reference list for a resource type
_REF_ENTRY = be.Struct(
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
_NFNT_HEADER = be.Struct(
    #    {font type}
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
_WIDTH_ENTRY = be.Struct(
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
_HEIGHT_ENTRY = be.Struct(
    offset='uint8',
    height='uint8',
)


##############################################################################
# FOND resource
# https://developer.apple.com/library/archive/documentation/mac/Text/Text-269.html#MARKER-2-525

_FFLAGS = be.Struct(
    # bit 15: This bit is set to 1 if the font family describes fixed-width fonts, and is cleared
    #         to 0 if the font describes proportional fonts.
    fixed_width=bitfield('uint16', 1),
    # bit 14: This bit is set to 1 if the family fractional-width table is not used, and is cleared
    #         to 0 if the table is used.
    frac_width_unused=bitfield('uint16', 1),
    # bit 13: This bit is set to 1 if the font family should use integer extra width for stylistic
    #         variations. If not set, the font family should compute the fixed-point extra width
    #         from the family style-mapping table, but only if the FractEnable global variable
    #         has a value of TRUE.
    use_int_extra_width=bitfield('uint16', 1),
    # bit 12: This bit is set to 1 if the font family ignores the value of the FractEnable global
    #         variable when deciding whether to use fixed-point values for stylistic variations;
    #         the value of bit 13 is then the deciding factor. The value of the FractEnable global
    #         variable is set by the SetFractEnable procedure.
    ignore_global_fract_enable=bitfield('uint16', 1),
    # bits 2-11: These bits are reserved by Apple and should be cleared to 0.
    reserved_2_11=bitfield('uint16', 10),
    # bit 1: This bit is set to 1 if the resource contains a glyph-width table.
    has_width_table=bitfield('uint16', 1),
    # bit 0: This bit is reserved by Apple and should be cleared to 0.
    reserved_0=bitfield('uint16', 1),
)

_FOND_HEADER = be.Struct(
   # {flags for family}
   ffFlags=_FFLAGS,
   # {family ID number}
   ffFamID='uint16',
   # {ASCII code of first character}
   ffFirstChar='uint16',
   # {ASCII code of last character}
   ffLastChar='uint16',
   # {maximum ascent for 1-pt font}
   ffAscent='uint16',
   # {maximum descent for 1-pt font}
   ffDescent='uint16',
   # {maximum leading for 1-pt font}
   ffLeading='uint16',
   # {maximum glyph width for 1-pt font}
   ffWidMax='uint16',
   # {offset to family glyph-width table}
   ffWTabOff='uint32',
   # {offset to kerning table}
   ffKernOff='uint32',
   # {offset to style-mapping table}
   ffStylOff='uint32',
   # {style properties info}
   ffProperty=struct.uint16 * 9,
   # {for international use}
   ffIntl=struct.uint16 * 2,
   # {version number}
   ffVersion='uint16',
)

# font association table
_FA_HEADER = be.Struct(
    max_entry='uint16',
)
_FA_ENTRY =  be.Struct(
    point_size='uint16',
    style_code='uint16',
    rsrc_id='uint16',
)

_STYLE_MAP = {
    0: 'bold',
    1: 'italic',
    2: 'underline',
    3: 'outline',
    4: 'shadow',
    5: 'condensed',
    6: 'extended',
}

# based on:
# [1] Apple Technotes (As of 2002)/te/te_02.html
# [2] https://developer.apple.com/library/archive/documentation/mac/Text/Text-367.html#HEADING367-0
_MAC_ENCODING = {
    0: 'mac-roman',
    1: 'mac-japanese',
    2: 'mac-trad-chinese',
    3: 'mac-korean',
    4: 'mac-arabic',
    5: 'mac-hebrew',
    6: 'mac-greek',
    7: 'mac-cyrillic', # [1] russian
    # 8: [2] right-to-left symbols
    9: 'mac-devanagari',
    10: 'mac-gurmukhi',
    11: 'mac-gujarati',
    12: 'mac-oriya',
    13: 'mac-bengali',
    14: 'mac-tamil',
    15: 'mac-telugu',
    16: 'mac-kannada',
    17: 'mac-malayalam',
    18: 'mac-sinhalese',
    19: 'mac-burmese',
    20: 'mac-khmer',
    21: 'mac-thai',
    22: 'mac-laotian',
    23: 'mac-georgian',
    24: 'mac-armenian',
    25: 'mac-simp-chinese', # [1] maldivian
    26: 'mac-tibetan',
    27: 'mac-mongolian',
    28: 'mac-ethiopic', # [2] == geez
    29: 'mac-centraleurope', # [1] non-cyrillic slavic
    30: 'mac-vietnamese',
    31: 'mac-sindhi', # [2] == ext-arabic
    #32: [1] [2] 'uninterpreted symbols'
}

# font names for system fonts in FONT resources
_FONT_NAMES = {
    0: 'Chicago', # system font
    1: 'application font',
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
    16: 'Palatino', # found experimentally
    20: 'Times',
    21: 'Helvetica',
    22: 'Courier',
    23: 'Symbol',
    24: 'Taliesin', # later named Mobile, but it's have a FOND entry then.
}

# fonts which clain mac-roman encoding but aren't
_NON_ROMAN_NAMES = {
    # https://www.unicode.org/Public/MAPPINGS/VENDORS/APPLE/SYMBOL.TXT
    # > The Mac OS Symbol encoding shares the script code smRoman
    # > (0) with the Mac OS Roman encoding. To determine if the Symbol
    # > encoding is being used, you must check if the font name is
    # > "Symbol".
    'Symbol': 'mac-symbol',
    'Cairo': '',
    'Taliesin': '',
    'Mobile': '',
}

##############################################################################

@loaders.register('dfont', 'suit', name='MacOS resource')
def load_dfont(instream, where=None):
    """
    Load font from a MacOS suitcase.
    """
    data = instream.read()
    return _parse_resource_fork(data)

@loaders.register('apple',
    magic=(_APPLESINGLE_MAGIC.to_bytes(4, 'big'), _APPLEDOUBLE_MAGIC.to_bytes(4, 'big')),
    name='MacOS resource (AppleSingle/AppleDouble container)',
)
def load_apple(instream, where=None):
    """
    Load font from an AppleSingle or AppleDouble container.
    """
    data = instream.read()
    return _parse_apple(data)


##############################################################################

def _parse_apple(data):
    """Parse an AppleSingle or AppleDouble file."""
    header = _APPLE_HEADER.from_bytes(data)
    if header.magic == _APPLESINGLE_MAGIC:
        container = 'AppleSingle'
    elif header.magic == _APPLEDOUBLE_MAGIC:
        container = 'AppleDouble'
    else:
        raise ValueError('Not an AppleSingle or AppleDouble file.')
    entry_array = _APPLE_ENTRY.array(header.number_entities)
    entries = entry_array.from_bytes(data, _APPLE_HEADER.size)
    for entry in entries:
        if entry.entry_id == _ID_RESOURCE:
            fork_data = data[entry.offset:entry.offset+entry.length]
            fonts = _parse_resource_fork(fork_data)
            fonts = [
                font.set_properties(
                    source_format=f'MacOS {font.source_format} ({container} container)'
                )
                for font in fonts
            ]
            return fonts
    raise ValueError('No resource fork found.')


def _parse_resource_fork(data):
    """Parse a MacOS resource fork."""
    rsrc_header = _RSRC_HEADER.from_bytes(data)
    map_header = _MAP_HEADER.from_bytes(data, rsrc_header.map_offset)
    type_array = _TYPE_ENTRY.array(map_header.last_type + 1)
    # +2 because the length field is considered part of the type list
    type_list_offset = rsrc_header.map_offset + map_header.type_list_offset + 2
    type_list = type_array.from_bytes(data, type_list_offset)
    resources = []
    for type_entry in type_list:
        ref_array = _REF_ENTRY.array(type_entry.last_rsrc + 1)
        ref_list = ref_array.from_bytes(
            data, type_list_offset -2 + type_entry.ref_list_offset
        )
        for ref_entry in ref_list:
            # get name from name list
            if ref_entry.name_offset == 0xffff:
                name = ''
            else:
                name_offset = (
                    rsrc_header.map_offset + map_header.name_list_offset
                    + ref_entry.name_offset
                )
                name_length = data[name_offset]
                name = data[name_offset+1:name_offset+name_length+1].decode('ascii', 'replace')
            # construct the 3-byte integer
            data_offset = ref_entry.data_offset_hi * 0x10000 + ref_entry.data_offset
            offset = rsrc_header.data_offset + _DATA_HEADER.size + data_offset
            if type_entry.rsrc_type == b'sfnt':
                logging.warning('sfnt resources (vector or bitmap) not supported')
            if type_entry.rsrc_type in (b'FONT', b'NFNT', b'FOND'):
                resources.append((type_entry.rsrc_type, ref_entry.rsrc_id, offset, name))
    # construct directory
    info = {}
    for rsrc_type, rsrc_id, offset, name in resources:
        if rsrc_type == b'FOND':
            info.update(_parse_fond(data, offset, name))
        else:
            if rsrc_type == b'FONT':
                font_number, font_size = divmod(rsrc_id, 128)
                if not font_size:
                    info[font_number] = {
                        'family': name,
                    }
    # parse fonts
    fonts = []
    for rsrc_type, rsrc_id, offset, name in resources:
        if rsrc_type in (b'FONT', b'NFNT'):
            props = {
                'family': name if name else f'{rsrc_id}',
                'source-format': rsrc_type.decode('ascii'),
            }
            if rsrc_type == b'FONT':
                font_number, font_size = divmod(rsrc_id, 128)
                if not font_size:
                    # directory entry only
                    continue
                if font_number in _FONT_NAMES:
                    props['family'] = _FONT_NAMES[font_number]
                else:
                    props['family'] = f'Family {font_number}'
                if font_number in info:
                    props.update({
                        **info[font_number],
                        'point-size': font_size,
                    })
            if rsrc_id in info:
                props.update(info[rsrc_id])
            if 'encoding' not in props or props.get('family', '') in _NON_ROMAN_NAMES:
                props['encoding'] = _NON_ROMAN_NAMES.get(props.get('family', ''), 'mac-roman')
            try:
                font = _parse_nfnt(data, offset, props)
            except ValueError as e:
                logging.error('Could not load font: %s', e)
            else:
                fonts.append(font)
    return fonts


def _parse_fond(data, offset, name):
    """Parse a MacOS FOND resource."""
    family_header = _FOND_HEADER.from_bytes(data, offset)
    # family-flags bitfield 15
    fixed_width = family_header.ffFlags.fixed_width
    # things we will want initially:
    # the script
    # the point size and style (font association table)
    # the postscript glyph name table
    #
    # other stuff:
    # family fractional width table
    # kerning table
    fa_header = _FA_HEADER.from_bytes(data, offset + _FOND_HEADER.size)
    fa_list = _FA_ENTRY.array(fa_header.max_entry+1).from_bytes(
        data, offset + _FOND_HEADER.size + _FA_HEADER.size
    )
    encoding = _MAC_ENCODING.get(max(0, 1 + (family_header.ffFamID - 16384) // 512))
    info = {
        fa_entry.rsrc_id: {
            'family': name,
            'style': ' '.join(
                _tag for _bit, _tag in _STYLE_MAP.items() if fa_entry.style_code & (0 << _bit)
            ),
            'point-size': fa_entry.point_size,
            'spacing': 'monospace' if fixed_width else 'proportional',
            'encoding': encoding,
        }
        for fa_entry in fa_list
    }
    return info


def _parse_nfnt(data, offset, properties):
    """Parse a MacOS NFNT or FONT resource."""
    fontrec = _NFNT_HEADER.from_bytes(data, offset)
    if not (fontrec.rowWords and fontrec.widMax and fontrec.fRectWidth and fontrec.fRectHeight):
        raise ValueError('Empty FONT/NFNT resource.')
    # extract bit fields
    has_height_table = bool(fontrec.fontType & 0x1)
    has_width_table = bool(fontrec.fontType & 0x2)
    # 1-bit 2-bit 4-bit 8-bit depth
    depth = (fontrec.fontType & 0xc) >> 2
    has_ftcb = bool(fontrec.fontType & 0x80)
    if depth or has_ftcb:
        raise ValueError('Anti-aliased or colour fonts not supported.')
    # bit 13: is fixed-width; ignored by Font Manager
    # also seems incorrect for system fonts
    #is_fixed = bool(fontrec.fontType & 1 << 13)
    ###############################################################################################
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
    if has_width_table:
        width_table = _WIDTH_ENTRY.array(n_chars).from_bytes(data, width_offset)
    # image height table: this can be deduced from the bitmaps
    # https://developer.apple.com/library/archive/documentation/mac/Text/Text-250.html#MARKER-9-414
    # > The Font Manager creates this table.
    if has_height_table:
        height_offset = width_offset
        if has_width_table:
            height_offset += _WIDTH_ENTRY.size * n_chars
        height_table = _HEIGHT_ENTRY.array(n_chars).from_bytes(data, height_offset)
    # parse bitmap strike
    bitmap_strike = bytes_to_bits(strike)
    rows = [
        bitmap_strike[_offs:_offs+fontrec.rowWords*16]
        for _offs in range(0, len(bitmap_strike), fontrec.rowWords*16)
    ]
    # extract width from width/offset table
    # (do we need to consider the width table, if defined?)
    locs = [_loc.offset for _loc in loc_table]
    glyphs = [
        Glyph([_row[_offs:_next] for _row in rows])
        for _offs, _next in zip(locs[:-1], locs[1:])
    ]
    # add glyph metrics
    # scalable-width table
    if has_width_table:
        glyphs = tuple(
            _glyph.modify(scalable_width=_we.width)
            for _glyph, _we in zip(glyphs, width_table)
        )
    # image-height table
    if has_height_table:
        glyphs = tuple(
            _glyph.modify(image_height=_he.height, top_offset=_he.offset)
            for _glyph, _he in zip(glyphs, height_table)
        )
    # width & offset
    glyphs = tuple(
        _glyph.modify(wo_offset=_wo.offset, wo_width=_wo.width)
        for _glyph, _wo in zip(glyphs, wo_table)
    )
    ###############################################################################################
    # convert mac glyph metrics to monobit glyph metrics
    #
    # the 'width' in the width/offset table is the pen advance
    # while the 'offset' is the (positive) offset after applying the
    # (positive or negative) 'kernMax' global offset
    #
    # since
    #   (glyph) advance == offset.x + width + tracking
    # after this transformation we should have
    #   (glyph) advance == wo.width
    # which means
    #   (total) advance == wo.width - kernMax
    # since
    #   (total) advance == (font) offset.x + glyph.advance + (font) tracking
    # and (font) offset.x = -kernMax
    glyphs = tuple(
        _glyph.modify(
            offset=(_glyph.wo_offset, 0),
            tracking=_glyph.wo_width - _glyph.width - _glyph.wo_offset
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
    labelled.append(glyphs[-1].modify(tags=['missing']))
    # drop undefined glyphs & their labels, so long as they're empty
    glyphs = tuple(
        _glyph for _glyph in labelled
        if (_glyph.wo_width != 0xff and _glyph.wo_offset != 0xff) or (_glyph.width and _glyph.height)
    )
    # drop mac glyph metrics
    glyphs = tuple(
        _glyph.drop_properties(
            'wo_offset', 'wo_width', 'image_height',
            # not interpreted - keep?
            'top_offset', 'scalable_width'
        )
        for _glyph in glyphs
    )
    # store properties
    properties.update({
        #'spacing': 'monospace' if is_fixed else 'proportional',
        'default-char': 'missing',
        'ascent': fontrec.ascent,
        'descent': fontrec.descent,
        'leading': fontrec.leading,
        'offset': Coord(fontrec.kernMax, -fontrec.descent),
    })
    return Font(glyphs, properties=properties)
