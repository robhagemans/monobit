"""
monobit.formats.mac - MacOS suitcases and resources

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging

from ..binary import bytes_to_bits, align
from ..struct import bitfield, big_endian as be
from ..storage import loaders, savers
from ..font import Font, Coord
from ..glyph import Glyph, KernTable
from ..streams import FileFormatError

from .sfnt import (
    load_sfnt, mac_style_name as _style_name, MAC_ENCODING as _MAC_ENCODING
)

# the magic is optional - a 'maybe magic'
# .rsrc is what we use as a 'filename' for resources inside containers
@loaders.register('dfont', 'suit', 'rsrc', name='mac', magic=(b'\0\0\1\0\0',))
def load_mac_dfont(instream, where=None):
    """Load font from a MacOS suitcase."""
    data = instream.read()
    return _parse_mac_resource(data)

@loaders.register('nfnt', name='nfnt')
def load_nfnt(instream, where=None, offset:int=0):
    """
    Load font from a bare FONT/NFNT resource.

    offset: starting offset in bytes of the NFNT record in the file (default 0)
    """
    instream.seek(offset)
    data = instream.read()
    fontdata = _extract_nfnt(data, 0)
    return _convert_nfnt({}, **fontdata)


##############################################################################
# encoding constants

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


def _parse_mac_resource(data, formatstr=''):
    """Parse a bare resource and convert to fonts."""
    resource_table = _extract_resource_fork_header(data)
    rsrc = _extract_resources(data, resource_table)
    directory = _construct_directory(rsrc)
    fonts = _convert_mac_font(rsrc, directory, formatstr)
    return fonts


def _extract_resource_fork_header(data):
    """Read a Classic MacOS resource fork header."""
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
                # should be ascii, but use mac-roman just in case
                name = data[name_offset+1:name_offset+name_length+1].decode('mac-roman')
            # construct the 3-byte integer
            data_offset = ref_entry.data_offset_hi * 0x10000 + ref_entry.data_offset
            offset = rsrc_header.data_offset + _DATA_HEADER.size + data_offset
            resources.append((type_entry.rsrc_type, ref_entry.rsrc_id, offset, name))
    return resources


def _extract_resources(data, resources):
    """Extract resources."""
    parsed_rsrc = []
    for rsrc_type, rsrc_id, offset, name in resources:
        if rsrc_type == b'FOND':
            logging.debug(
                'Font family resource #%d: type FOND name `%s`', rsrc_id, name
            )
            parsed_rsrc.append((
                rsrc_type, rsrc_id, dict(
                    name=name, **_extract_fond(data, offset)
                )
            ))
        elif rsrc_type == b'FONT' and name and not (rsrc_id % 128):
            # rsrc_id % 128 is the point size
            logging.debug(
                'Name entry #%d: type FONT name `%s`',
                rsrc_id, name
            )
            # inside macintosh:
            # > Since 0 is not a valid font size, the resource ID having
            # > 0 in the size field is used to provide only the name of
            # > the font: The name of the resource is the font name. For
            # > example, for a font named Griffin and numbered 200, the
            # > resource naming the font would have a resource ID of 25600
            # > and the resource name 'Griffin'. Size 10 of that font would
            # > be stored in a resource numbered 25610.
            # keep the name in the directory table
            parsed_rsrc.append((
                b'', rsrc_id, dict(name=name),
            ))
        elif rsrc_type in (b'NFNT', b'FONT'):
            logging.debug(
                'Bitmapped font resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
            parsed_rsrc.append((
                rsrc_type, rsrc_id, _extract_nfnt(data, offset)
            ))
        elif rsrc_type == b'sfnt':
            logging.debug(
                'TrueType font resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
            bytesio = io.BytesIO(data[offset:])
            fonts = load_sfnt(bytesio)
            parsed_rsrc.append((
                rsrc_type, rsrc_id, dict(fonts=fonts)
            ))
        else:
            logging.debug(
                'Skipped resource #%d: type %s name `%s`',
                rsrc_id, rsrc_type.decode('mac-roman'), name
            )
    return parsed_rsrc


def _construct_directory(parsed_rsrc):
    """Construct font family directory."""
    info = {}
    for rsrc_type, rsrc_id, kwargs in parsed_rsrc:
        # new-style directory entries
        if rsrc_type == b'FOND':
            props = _convert_fond(**kwargs)
            info.update(props)
        # old-style name-only FONT resources (font_size 0)
        elif rsrc_type == b'':
            font_number = rsrc_id // 128
            info[font_number] = {'family': kwargs['name']}
    return info


def _convert_mac_font(parsed_rsrc, info, formatstr):
    """convert properties and glyphs."""
    fonts = []
    for rsrc_type, rsrc_id, kwargs in parsed_rsrc:
        if rsrc_type == b'sfnt':
            rsrc_fonts = kwargs['fonts']
            rsrc_fonts = (
                _font.modify(
                    source_format = f'MacOS {_font.source_format}',
                )
                for _font in rsrc_fonts
            )
            fonts.extend(rsrc_fonts)
        elif rsrc_type in (b'FONT', b'NFNT'):
            format = ''.join((
                rsrc_type.decode('mac-roman'),
                f' in {formatstr}' if formatstr else ''
            ))
            props = {
                'family': kwargs.get('name', '') or f'{rsrc_id}',
                'source-format': f'MacOS {format}',
            }
            if rsrc_type == b'FONT':
                # get name and size info from resource ID
                # https://developer.apple.com/library/archive/documentation/mac/Text/Text-191.html#HEADING191-0
                # > The resource ID of the font must equal the number produced by
                # > concatenating the font ID times 128 with the font size.
                # > Remember that fonts stored in 'FONT' resources are restricted
                # > to a point size of less than 128 and to a font ID in the range
                # > 0 to 255. The resource ID is computed by the following formula:
                # >     resourceID := (font ID * 128) + font size;
                font_number, font_size = divmod(rsrc_id, 128)
                # we've already filtered out the case font_size == 0
                props.update({
                    'point-size': font_size,
                    'family': _FONT_NAMES.get(font_number, str(font_number))
                })
                # prefer directory info to info inferred from resource ID
                # (in so far provided by FOND or directory FONT)
                props.update(info.get(rsrc_id, info.get(font_number, {})))
            else:
                # update properties with directory info
                props.update(info.get(rsrc_id, {}))
            if 'encoding' not in props or props.get('family', '') in _NON_ROMAN_NAMES:
                props['encoding'] = _NON_ROMAN_NAMES.get(props.get('family', ''), 'mac-roman')
            font = _convert_nfnt(props, **kwargs)
            if font.glyphs:
                font = font.label()
                fonts.append(font)
    return fonts


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

# p1-110
# actually these are all signed??
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
   ffProperty=be.uint16 * 9,
   # {for international use}
   ffIntl=be.uint16 * 2,
   # {version number}
   ffVersion='uint16',
)

# font association table
# definitions I.M. p4-110
# signed??
_FA_HEADER = be.Struct(
    # number of entries - 1
    numAssoc='uint16',
)
# record - p4-111
_FA_ENTRY =  be.Struct(
    fontSize='uint16',
    fontStyle='uint16',
    fontID='uint16',
)

# offset table
# Fig 4-15, I. M.: Text p. 4-96
# will max_entry be -1 for an empty table?
_OFFS_HEADER = be.Struct(
    max_entry='int16',
)
# followed by array of uint32 offsets
_OFFS_ENTRY = be.Struct(
    offset='uint32',
)

# p. 4-99
# > Each width is in 16-bit fixed-point format, with the integer part
# > in the high-order 4 bits and the fractional part in the low-order 12 bits.
_FIXED_TYPE = be.int16
# remember to divide by 2**12...

# bounding-box table
# Fig. 4.26
_BBX_HEADER = _OFFS_HEADER
_BBX_ENTRY = be.Struct(
    # _STYLE_MAP bitfield
    style='uint16',
    left=_FIXED_TYPE,
    bottom=_FIXED_TYPE,
    right=_FIXED_TYPE,
    top=_FIXED_TYPE,
)

# Family glyph width table
# definitions I.M. p.4-109 / p.4-115
# handle; elsewhere 4 bytes
_HANDLE = be.uint32
# guess
_BOOLEAN = be.uint8
# Point data type; 4 bytes e.g. I.M. C-29
# 4-29 "two integers: vertical, horizontal"
_POINT = be.Struct(
    vert='int16',
    horiz='int16',
)
_WIDTH_TABLE = be.Struct(
    tabData=_FIXED_TYPE*256,
    tabFont=_HANDLE,
    # extra line spacing
    sExtra='int32',
    # extra line spacing due to style
    style='int32',
    # font family ID
    fID='int16',
    # font size request
    fSize='int16',
    # style (face) request
    face='int16',
    # device requested
    device='int16',
    # scale factors requested
    inNumer=_POINT,
    inDenom=_POINT,
    # actual font family ID for table
    aFID='int16',
    # family record used to build up table
    fHand=_HANDLE,
    # used fixed-point family widths
    usedFam=_BOOLEAN,
    # actual face produced
    aFace='uint8',
    # vertical scale output value
    vOutput='int16',
    # horizontal scale output value
    hOutput='int16',
    # vertical scale output value
    vFactor='int16',
    # horizontal scale output value
    hFactor='int16',
    # actual size of font used
    aSize='int16',
    # total size of table
    tabSize='int16',
)

# Style-mapping table
# I.M.:Text p. 4-99
# > The font name suffix subtable and the glyph-encoding subtable that are part of the style-mapping
# > table immediately follow it in the resource data. The font name suffix subtable contains the
# > base font name and the suffixes that can be added to the font family’s name to produce a real
# > PostScript name (one that is recognized by the PostScript LaserWriter printer driver). The
# > style-mapping table uses the suffix table to build a font name for a PostScript printer. The
# > glyph-encoding table allows character codes to be mapped to PostScript glyph names.
_STYLE_TABLE = be.Struct(
    # bit field holding rendering hints - see I.M. p 4-101
    fontClass='int16',
    # offset from the start of this table to the glyph-encoding subtable component
    offset='int32',
    reserved='int32',
    # indexes into the font suffix name table that follows this table
    # "This is an array of 48 integer index values"
    # note C summary has 47 but Pascal summary has 0..47 inclusive
    indexes=be.int8 * 48,
)
# https://www6.uniovi.es/cscene/CS5/CS5-04.html
# > In Pascal, on the other hand, the first character of the string is the length of the
# > string, and the string is stored in the 255 characters that follow
# > On the Mac, there is a predefined type for Pascal strings, namely, Str255.
_STR255 = be.Struct(
    length='uint8',
    string=be.char * 255, #*length
)
_NAME_TABLE = be.Struct(
    stringCount='int16',
    #baseFontName=_STR255,
)

def string_from_bytes(data, offset):
    length = int(be.uint8.from_bytes(data, offset))
    string = data[offset+1:offset+1+length]
    return string, offset+1+length

# glyph encoding subtable
_ENC_TABLE = be.Struct(
    stringCount='int16',
)
_ENC_ENTRY = be.Struct(
    char='uint8',
    name=be.char * 255,
)

# Kerning table
_KERN_TABLE = be.Struct(
    # number of entries - 1
    numKerns='int16',
)
_KERN_ENTRY = be.Struct(
    kernStyle='uint16',
    kernLength='uint16',
)
_KERN_PAIR = be.Struct(
    kernFirst='uint8',
    kernSecond='uint8',
    # kerning value in 1pt fixed format
    kernWidth=_FIXED_TYPE,
)

def _extract_fond(data, offset):
    """Read a MacOS FOND resource."""
    fond_header = _FOND_HEADER.from_bytes(data, offset)
    # Font Family Tables:
    # Font Association table (mandatory)
    fa_offset = offset + _FOND_HEADER.size
    fa_header = _FA_HEADER.from_bytes(data, fa_offset)
    fa_list = _FA_ENTRY.array(fa_header.numAssoc+1).from_bytes(data, fa_offset + _FA_HEADER.size)
    kerning_table = {}
    encoding_table = []
    # check if any optional tables are expected
    # we don't have a field for bounding-box table offset
    if fond_header.ffWTabOff or fond_header.ffKernOff or fond_header.ffStylOff:
        # Offset table (optional)
        # > Whenever any table, including the glyph-width, kerning, and
        # > style-mapping tables, is included in the resource data, an offset table is included.
        # > The offset table contains a long integer offset value for each table that follows it
        offs_offset = fa_offset + _FA_HEADER.size + _FA_ENTRY.size * (fa_header.numAssoc+1)
        offs_header = _OFFS_HEADER.from_bytes(data, offs_offset)
        # max_entry==-1 if the table is absent?
        offs_list = _OFFS_ENTRY.array(offs_header.max_entry+1).from_bytes(
            data, offs_offset + _OFFS_HEADER.size
        )
        # we already have the offsets we need so no need to use the Offset Table
        # Bounding-box table (optional)
        bbx_offset = offs_offset + _OFFS_HEADER.size + _OFFS_ENTRY.size * (offs_header.max_entry+1)
        bbx_header = _BBX_HEADER.from_bytes(data, bbx_offset)
        bbx_list = _BBX_ENTRY.array(bbx_header.max_entry+1).from_bytes(
            data, bbx_offset + _BBX_HEADER.size
        )
        # Family glyph-width table (optional)
        # use offset given in FOND header
        # this could also be determined from current position ,or from offset table
        if not fond_header.ffWTabOff:
            wtab = ()
        else:
            wtab_offset = offset + fond_header.ffWTabOff
            wtab = _WIDTH_TABLE.from_bytes(data, wtab_offset)
        # Style-mapping table (optional)
        if not fond_header.ffStylOff:
            stab = ()
            names = ()
        else:
            stab_offset = offset + fond_header.ffStylOff
            stab = _STYLE_TABLE.from_bytes(data, stab_offset)
            # font name suffix subtable
            ntab_offset = stab_offset + _STYLE_TABLE.size
            ntab = _NAME_TABLE.from_bytes(data, ntab_offset)
            names = []
            offs = ntab_offset + _NAME_TABLE.size
            # count + 1 as we take the base font name as well?
            # but using that leads to incorrect encoding table
            for i in range(ntab.stringCount):
                string, offs = string_from_bytes(data, offs)
                names.append(string)
            if names:
                logging.debug('Font family name suffix table found')
            # glyph-name encoding subtable
            etab_offset = offs
            etab = _ENC_TABLE.from_bytes(data, etab_offset)
            offs += _ENC_TABLE.size
            for i in range(etab.stringCount):
                string, offs = string_from_bytes(data, offs)
                encoding_table.append(string)
            if encoding_table:
                logging.debug('Glyph-name encoding table found')
        # Kerning table (optional)
        if fond_header.ffKernOff:
            ktab_offset = offset + fond_header.ffKernOff
            ktab = _KERN_TABLE.from_bytes(data, ktab_offset)
            offs = ktab_offset + _KERN_TABLE.size
            kerning_table = {}
            for entry in range(ktab.numKerns+1):
                ke = _KERN_ENTRY.from_bytes(data, offs)
                # This is an integer value that specifies
                # the number of bytes in this kerning subtable
                pair_array = _KERN_PAIR.array(ke.kernLength)
                kerning_table[ke.kernStyle] = tuple(
                    pair_array.from_bytes(data, offs + _KERN_ENTRY.size)
                )
                offs += _KERN_ENTRY.size + pair_array.size
    return dict(
        fond_header=fond_header,
        fa_list=fa_list,
        kerning_table=kerning_table,
        encoding_table=encoding_table,
    )


def _convert_fond(name, fond_header, fa_list, kerning_table, encoding_table):
    """Partially convert FOND properties to monobit peroperties."""
    # Inside Macintosh: Text 6-22
    # > Fonts with IDs below 16384 ($4000) are all Roman; starting with
    # > 16384 each non-Roman script system has a range of 512 ($200) font IDs available
    encoding = _MAC_ENCODING.get(max(0, 1 + (fond_header.ffFamID - 16384) // 512))
    info = {
        # rsrc_id
        fa_entry.fontID: {
            'family': name,
            'style': _style_name(fa_entry.fontStyle),
            'point-size': fa_entry.fontSize,
            #'spacing': 'monospace' if fond_header.ffFlags.fixed_width else 'proportional',
            'encoding': encoding,
            'kerning-table': kerning_table.get(fa_entry.fontStyle, ()),
            'encoding-table': encoding_table,
        }
        for fa_entry in fa_list
    }
    # check if we're losing kerning tables
    styles = set(fa_entry.fontStyle for fa_entry in fa_list)
    dropped_styles = tuple(
        _style for _style in kerning_table
        if _style not in styles
    )
    for style in dropped_styles:
        logging.warning(
            f'Kerning table for style {style:#0x} ({_style_name(style)}) not preserved.'
        )
        logging.debug(kerning_table[style])
    return info




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
    24: 'Taliesin', # later named Mobile, but it has a FOND entry then.
}


def _extract_nfnt(data, offset):
    """Read a MacOS NFNT or FONT resource."""
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
    })
    return Font(glyphs, **properties)
