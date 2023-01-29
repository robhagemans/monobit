"""
monobit.formats.mac.fond - Mac FOND font directory

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..sfnt import MAC_ENCODING, mac_style_name
from ...binary import bytes_to_bits, align
from ...struct import bitfield, big_endian as be


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
    encoding = MAC_ENCODING.get(max(0, 1 + (fond_header.ffFamID - 16384) // 512))
    info = {
        # rsrc_id
        fa_entry.fontID: {
            'family': name,
            'style': mac_style_name(fa_entry.fontStyle),
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
            'Kerning table not preserved '
            f'for style {style:#0x} ({mac_style_name(style)})'
        )
        logging.debug(kerning_table[style])
    return info
