"""
monobit.mac - MacOS suitcases and resources

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .binary import friendlystruct, bytes_to_bits
from .formats import Loaders, Savers
from .typeface import Typeface
from .font import Font, Glyph, Coord


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
# FOND resource

_FOND_HEADER = friendlystruct(
    'be',
   # {flags for family}
   ffFlags='uint16',
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
   ffProperty=friendlystruct.uint16 * 9,
   # {for international use}
   ffIntl=friendlystruct.uint16 * 2,
   # {version number}
   ffVersion='uint16',
)

# font association table
_FA_HEADER = friendlystruct(
    'be',
    max_entry='uint16',
)
_FA_ENTRY =  friendlystruct(
    'be',
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

_MAC_ENCODING = {
    0: 'mac-roman',
    1: 'mac-japanese',
    2: 'mac-trad-chinese',
    3: 'mac-korean',
    4: 'mac-arabic',
    5: 'mac-hebrew',
    6: 'mac-greek',
    7: 'mac-russian',
    # 8: right-to-left symbols
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
    25: 'mac-simp-chinese', # in early docs, maldivian...
    26: 'mac-tibetan',
    27: 'mac-mongolian',
    28: 'mac-ethiopian', # aka geez
    29: 'mac-latin2', # "non-cyrillic slavic", mac-centeuro
    30: 'mac-vietnamese',
    31: 'mac-sindhi', # == extended arabic
    # 32: uninterpreted symbols
}

# font names for system fonts in FONT resources
_FONT_NAMES = {
    0: 'System',
    1: 'Application',
    2: 'New York',
    3: 'Geneva',
    4: 'Monaco',
    5: 'Venice',
    6: 'London',
    7: 'Athens',
    8: 'San Francisco',
    9: 'Totonto',
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
    'Symbol': 'mac-symbol',
    'Cairo': '',
    'Taliesin': '',
    'Mobile': '',
}

##############################################################################

@Loaders.register('dfont', 'suit',
    name='MacOS resource',
    binary=True, multi=True
)
def load_dfont(instream):
    """Load a MacOS suitcase."""
    data = instream.read()
    return Typeface(_parse_resource_fork(data))

@Loaders.register('apple',
    name='MacOS resource (AppleSingle/AppleDouble container)',
    binary=True, multi=True
)
def load_apple(instream):
    """Load an AppleSingle or AppleDouble file."""
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
    entry_array = _APPLE_ENTRY * header.number_entities
    entries = entry_array.from_buffer_copy(data, _APPLE_HEADER.size)
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
            return Typeface(fonts)
    raise ValueError('No resource fork found.')


def _parse_resource_fork(data):
    """Parse a MacOS resource fork."""
    rsrc_header = _RSRC_HEADER.from_bytes(data)
    map_header = _MAP_HEADER.from_bytes(data, rsrc_header.map_offset)
    type_array = _TYPE_ENTRY * (map_header.last_type + 1)
    # +2 because the length field is considered part of the type list
    type_list_offset = rsrc_header.map_offset + map_header.type_list_offset + 2
    type_list = type_array.from_buffer_copy(data, type_list_offset)
    resources = []
    for type_entry in type_list:
        ref_array = _REF_ENTRY * (type_entry.last_rsrc + 1)
        ref_list = ref_array.from_buffer_copy(
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
    # bitfield
    #has_width_table = bool(family_header.ffFlags & (1 << 1))
    #ignore_global_fract_enable = bool(family_header.ffFlags & (1 << 12))
    #use_int_extra_width = bool(family_header.ffFlags & (1 << 13))
    #frac_width_unused = bool(family_header.ffFlags & (1 << 14))
    fixed_width = bool(family_header.ffFlags & (1 << 15))
    # things we will want initially:
    # the script
    # the point size and style (font association table)
    # the postscript glyph name table
    #
    # other stuff:
    # family fractional width table
    # kerning table
    fa_header = _FA_HEADER.from_bytes(data, offset + _FOND_HEADER.size)
    fa_list = (_FA_ENTRY * (fa_header.max_entry+1)).from_buffer_copy(
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
    is_fixed = bool(fontrec.fontType & 1 << 13)
    # table offsets
    strike_offset = offset + _NFNT_HEADER.size
    loc_offset = offset + _NFNT_HEADER.size + fontrec.fRectHeight * fontrec.rowWords * 2
    # bitmap strike
    strike = data[strike_offset:loc_offset]
    # location table
    # number of chars: coded chars plus missing symbol
    n_chars = fontrec.lastChar - fontrec.firstChar + 2
    # loc table should have one extra entry to be able to determine widths
    loc_table = (_LOC_ENTRY * (n_chars+1)).from_buffer_copy(data, loc_offset)
    # width offset table
    # https://developer.apple.com/library/archive/documentation/mac/Text/Text-252.html
    if fontrec.nDescent > 0:
        wo_offset = fontrec.nDescent << 16 + fontrec.owTLoc * 2
    else:
        wo_offset = fontrec.owTLoc * 2
    # owtTLoc is offset "from itself" to table
    wo_table = (_WO_ENTRY * n_chars).from_buffer_copy(data, offset + 16 + wo_offset)
    widths = [_entry.width for _entry in wo_table]
    offsets = [_entry.offset for _entry in wo_table]
    # scalable width table - ignoring for now
    width_offset = wo_offset + _WO_ENTRY.size * n_chars
    if has_width_table:
        width_table = (_WIDTH_ENTRY * n_chars).from_buffer_copy(data, width_offset)
    # image height table: ignore, this can be deduced from the bitmaps
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
    # pad to apply width and offset
    # the 'width' in the width/offset table is the pen advance
    # while the 'offset' is the (positive) offset after applying the
    # (positive or negative) 'kernMax' (==left-bearing) global offset
    # since advance = left-bearing + grid-width + right-bearing
    # after this transformation we should have
    #   grid-width = advance - left-bearing - right-bearing = 'width' - kernMax - right-bearing
    # and it seems we can set right-bearing=0
    glyphs = [
        (
            _glyph.expand(left=_offset, right=(_width-fontrec.kernMax)-(_glyph.width+_offset))
            if _width != 0xff and _offset != 0xff else _glyph
        )
        for _glyph, _width, _offset in zip(glyphs, widths, offsets)
    ]
    # ordinal labels
    labelled = list(zip(range(fontrec.firstChar, fontrec.lastChar+1), glyphs))
    # last glyph is the "missing" glyph
    labelled.append(('missing', glyphs[-1]))
    # drop undefined glyphs & their labels, so long as they're empty
    labelled = [
        _pair for _pair, _width, _offset in zip(labelled, widths, offsets)
        if (_width != 0xff and _offset != 0xff) or (_pair[1].width and _pair[1].height)
    ]
    glyphs = [_g for _, _g in labelled]
    labels = {_l: _i for _i, _l in enumerate(_l for _l, _ in labelled)}
    # store properties
    properties.update({
        'spacing': 'monospace' if is_fixed else 'proportional',
        'default-char': 'missing',
        'ascent': fontrec.ascent,
        'descent': fontrec.descent,
        'leading': fontrec.leading,
        'offset': Coord(fontrec.kernMax, -fontrec.descent),
    })
    return Font(glyphs, labels, comments=(), properties=properties)
