"""
monobit.formats.mac.fond - Mac FOND font directory

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..sfnt import MAC_ENCODING, mac_style_name, to_postscript_name
from ...binary import bytes_to_bits, align
from ...struct import bitfield, big_endian as be, sizeof
from ...glyph import Glyph


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
    # reserved for internal use by script management software
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
# > Kerning distance. The kerning distance, in pixels, for the two glyphs
# > at a point size of 1. This is a 16-bit fixed point value, with the
# > integer part in the high-order 4 bits, and the fractional part in
# > the low-order 12 bits. The Font Manager measures the distance in pixels
# > and then multiplies it by the requested point size
_FIXED_TYPE = be.int16

# this leaves open the matter of negative numbers. there are two reasonable conventions
# 1) true value * 2**12 represented as a two's complement 16-bit integer
# 2) sign | 3-bit integer part | 12-bit fractional part
# which agree for positive numbers but are different for negatives.
# of course, both conventions are used:
# Palatino uses convention (2) while Helvetica uses (1).

# according to Adobe's 091.Mac_Fond.pdf (p.8):
# > If the value of this word is 2 or greater, then
# > negative numbers in the FOND resource are kept
# > as 2’s complement; font version 0 and 1 have 1’s
# > complement negative values.
# Palatino (1's complement) has ffVersion=0, Helvetica and Times (2's complement) have ffVersion=3
# mnany have ffVersion=1 but no kerning table

def fixed_to_float(fixed, twos_complement=True):
    # fixed is the input 2's complement 16-bit signed integer
    if not twos_complement:
        # convert back from 2's complement (interpreted by the C struct reader)
        fixed = 0x10000 + fixed
        # unset sign bit
        fixed = 0x7fff & fixed
        # make negative
        fixed = - fixed
    return fixed / 2**12

def _float_to_fixed(flt):
    # using convention (1)
    return int(flt * 2**12)


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
# definitions I.M. p.4-48, 4-98
_WIDTH_TABLE = be.Struct(
    # number of entries -1
    numWidths='int16',
)
_WIDTH_ENTRY = be.Struct(
    # style code
    widStyle='int16',
    # widths: ARRAY[0.n] of Fixed;
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

def string_from_pascal(data, offset):
    """Convert Mac-encoded Pascal string to Python string."""
    length = int(be.uint8.from_bytes(data, offset))
    string = data[offset+1:offset+1+length]
    string = string.decode('mac-roman', 'replace')
    return string, offset+1+length

def string_to_pascal(str):
    """Convert Python string to Mac-encoded Pascal string."""
    return bytes((len(str),)) + str.encode('mac-roman', 'replace')


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

def extract_fond(data, offset):
    """Read a MacOS FOND resource."""
    fond_header = _FOND_HEADER.from_bytes(data, offset)
    # Font Family Tables:
    # Font Association table (mandatory)
    fa_offset = offset + _FOND_HEADER.size
    fa_header = _FA_HEADER.from_bytes(data, fa_offset)
    fa_list = _FA_ENTRY.array(fa_header.numAssoc+1).from_bytes(data, fa_offset + _FA_HEADER.size)
    kerning_table = {}
    encoding_table = {}
    offs_header = None
    offs_list = None
    bbx_header = None
    bbx_list = None
    wtab = ()
    wtables = ()
    stab = ()
    names = ()
    ktab = None
    # check if any optional tables are expected
    # we don't have a field for bounding-box table offset
    if fond_header.ffWTabOff or fond_header.ffKernOff or fond_header.ffStylOff:
        # Offset table (optional, not used by us)
        # > Whenever any table, including the glyph-width, kerning, and
        # > style-mapping tables, is included in the resource data, an offset table is included.
        # > The offset table contains a long integer offset value for each table that follows it
        offs_offset = fa_offset + _FA_HEADER.size + _FA_ENTRY.size * (fa_header.numAssoc+1)
        offs_header = _OFFS_HEADER.from_bytes(data, offs_offset)
        # max_entry==-1 if the table is absent?
        offs_list = _OFFS_ENTRY.array(offs_header.max_entry+1).from_bytes(
            data, offs_offset + _OFFS_HEADER.size
        )
        # Bounding-box table (optional, not used by us)
        # no offset given in font record. should use the Offset Table to find it?
        # here we just assume it is the first table after the offset table
        # is BBX table effectively mandatory if more tables follow?
        bbx_offset = offs_offset + _OFFS_HEADER.size + _OFFS_ENTRY.size * (offs_header.max_entry+1)
        bbx_header = _BBX_HEADER.from_bytes(data, bbx_offset)
        bbx_list = _BBX_ENTRY.array(bbx_header.max_entry+1).from_bytes(
            data, bbx_offset + _BBX_HEADER.size
        )
        # Family glyph-width table (optional, not used by us)
        # use offset given in FOND header
        if fond_header.ffWTabOff:
            wtab_offset = offset + fond_header.ffWTabOff
            wtab = _WIDTH_TABLE.from_bytes(data, wtab_offset)
            # number of characters in each width table - one more than in NFNT.
            # poorly documented, but consistent with Classic Mac system resource
            # and FONDU/FontForge
            num_chars = fond_header.ffLastChar - fond_header.ffFirstChar + 3
            wtables = []
            wtab_offset += _WIDTH_TABLE.size
            # numWidths is the number of width tables, i.e. the number of styles.- 1
            for style in range(wtab.numWidths+1):
                wentry = _WIDTH_ENTRY.from_bytes(data, wtab_offset)
                widths = _FIXED_TYPE.array(num_chars).from_bytes(
                    data, wtab_offset + _WIDTH_ENTRY.size
                )
                wtab_offset += (
                    _WIDTH_ENTRY.size + _FIXED_TYPE.size * num_chars
                )
                wtables.append((wentry, widths))
        # Style-mapping table (optional)
        if fond_header.ffStylOff:
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
                string, offs = string_from_pascal(data, offs)
                names.append(string)
            # glyph-name encoding subtable
            etab_offset = offs
            etab = _ENC_TABLE.from_bytes(data, etab_offset)
            offs += _ENC_TABLE.size
            # encoding table - this is based on description in the docs
            # but does not appear to work correctly for built in mac Palatino font
            # which has a table that's just three nulls but stringCount=3
            for i in range(etab.stringCount):
                codepoint = be.uint8.from_bytes(data, offs)
                string, offs = string_from_pascal(data, offs+1)
                encoding_table[codepoint] = string
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
        fa_header=fa_header, fa_list=fa_list,
        offs_header=offs_header, offs_list=offs_list,
        bbx_header=bbx_header, bbx_list=bbx_list,
        width_header=wtab, width_list=wtables,
        style_header=stab, name_list=names,
        # do not include encoding table as I don't understand how it is structured
        #encoding_table=encoding_table,
        kerning_header=ktab, kerning_table=kerning_table,
    )


def convert_fond(
        name, fond_header, fa_list,
        kerning_table, encoding_table=None,
        **kwargs
    ):
    """Partially convert FOND properties to monobit properties."""
    # Inside Macintosh: Text 6-22
    # > Fonts with IDs below 16384 ($4000) are all Roman; starting with
    # > 16384 each non-Roman script system has a range of 512 ($200) font IDs available
    encoding = MAC_ENCODING.get(max(0, 1 + (fond_header.ffFamID - 16384) // 512))
    info = {
        # rsrc_id
        fa_entry.fontID: {
            # monobit properties
            'family': name,
            'style': mac_style_name(fa_entry.fontStyle),
            'point_size': fa_entry.fontSize,
            #'spacing': 'monospace' if fond_header.ffFlags.fixed_width else 'proportional',
            'encoding': encoding,
            # for use by NFNT parser
            'kerning-table': kerning_table.get(fa_entry.fontStyle, ()),
            'encoding-table': encoding_table,
            'twos-complement': fond_header.ffVersion >= 2,
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


###############################################################################
# FOND writer

def create_fond(style_groups, family_id):
    """
    Convert monobit properties to FOND.
    Requires NFNT data structure for largest font.
    """
    # use last (largest) font in first group as representative sample
    largest_per_style = tuple(
        (_style_code, _font)
        for _style_code, (*_, _font) in style_groups
    )
    _, sample_font = largest_per_style[0]
    # list of (style_id, list of fonts)
    # following FONDU/FontForge: 0x9000 for fixed, 0x1000 for proportional
    ff_flags = _FFLAGS(
        fixed_width=sample_font.spacing in ('character-cell', 'monospace'),
        # bit 14: This bit is set to 1 if the family fractional-width table is not used, and is cleared
        #         to 0 if the table is used.
        frac_width_unused=0,
        # bit 13: This bit is set to 1 if the font family should use integer extra width for stylistic
        #         variations. If not set, the font family should compute the fixed-point extra width
        #         from the family style-mapping table, but only if the FractEnable global variable
        #         has a value of TRUE.
        use_int_extra_width=0,
        # bit 12: This bit is set to 1 if the font family ignores the value of the FractEnable global
        #         variable when deciding whether to use fixed-point values for stylistic variations;
        #         the value of bit 13 is then the deciding factor. The value of the FractEnable global
        #         variable is set by the SetFractEnable procedure.
        ignore_global_fract_enable=1,
        # bit 1: This bit is set to 1 if the resource contains a glyph-width table.
        # has_width_table=1,
    )
    fond_header = _FOND_HEADER(
        # {flags for family}
        ffFlags=ff_flags,
        # {family ID number}
        ffFamID=family_id,
        # {ASCII code of first character}
        ffFirstChar=int(min(sample_font.get_codepoints())),
        # {ASCII code of last character}
        ffLastChar=int(max(sample_font.get_codepoints())),
        # {maximum ascent for 1-pt font}
        ffAscent=_float_to_fixed(sample_font.ink_bounds.top / sample_font.bounding_box.y),
        # {maximum descent for 1-pt font}
        ffDescent=_float_to_fixed(sample_font.ink_bounds.bottom / sample_font.bounding_box.y),
        # {maximum leading for 1-pt font}
        ffLeading=_float_to_fixed(sample_font.line_height / sample_font.bounding_box.y - 1),
        # {maximum glyph width for 1-pt font}
        ffWidMax=_float_to_fixed(sample_font.max_width / sample_font.bounding_box.y),
        # {style properties info}
        # extra width for text styles (fixed point value) - currently left at all 0s
        #ffProperty=be.uint16 * 9,
        # {version number}
        # An integer value that specifies the version number of the font family resource, which indicates whether certain tables are available. This value is represented by the ffVersion field in the FamRec data type. Because this field has been used inconsistently in the system software, it is better to analyze the data in the resource itself instead of relying on the version number. The possible values are as follows:
        # Value	Meaning
        # $0000	Created by the Macintosh system software. The font family resource will not have the glyph-width tables and the fields will contain 0.
        # $0001	Original format as designed by the font developer. This font family record probably has the width tables and most of the fields are filled.
        # $0002	This record may contain the offset and bounding-box tables.
        # $0003	This record definitely contains the offset and bounding-box tables.
        # Adobe docs 0091.Mac_Fond.pdf:
        # > If the value of this word is 2 or greater, then negative numbers in
        # > the FOND resource are kept as 2’s complement;
        # > font version 0 and 1 have 1’s complement negative values.
        ffVersion=2,
    )
    fa_list = tuple(
        _FA_ENTRY(
            fontSize=_font.point_size,
            fontStyle=_style,
            # fontID=family_id+_i,
        )
        for _style, _group in style_groups
        for _font in _group
    )
    # following FONDU, just increment from the family id.
    # not sure if/how this avoids ID collisions
    # NOTE this is calculated separately for NFNT's rsrc id
    for i, entry in enumerate(fa_list):
        entry.fontID = family_id + i
    fa_list = (_FA_ENTRY * len(fa_list))(*fa_list)
    fa_header = _FA_HEADER(numAssoc=len(fa_list)-1)
    # get contiguous vector of glyphs, add missing glyph and one extra with 1-em width
    # the latter is described as 'Unused Word' in Adobe docs
    style_groups = tuple(
        (
            _style_id,
            tuple(
                _font.modify(glyphs=(
                    [
                        _font.get_glyph(_cp, missing='empty')
                        for _cp in range(fond_header.ffFirstChar, fond_header.ffLastChar+1)
                    ]
                    + [_font.glyphs[-1], Glyph(scalable_width=_font.bounding_box.y)]
                ))
                for _font in _group
            )
        )
        for _style_id, _group in style_groups
    )
    # optional tables
    bbx_bytes = _create_bbx_table(style_groups)
    wtab_bytes = _create_width_table(style_groups)
    stab_bytes = _create_style_table(style_groups)
    ktab_bytes = _create_kerning_table(style_groups)
    optional_tables = (bbx_bytes, wtab_bytes, stab_bytes, ktab_bytes)
    # # Offset table (mandatory if optional tables are present)
    # one entry for each table, with its offsets
    # offset from the start of the offset table
    num_tables = len(optional_tables)
    offset_table_size = _OFFS_HEADER.size + num_tables*_OFFS_ENTRY.size
    # > the number of bytes from the start of the offset table to the start of the table.
    table_offsets = tuple(accumulate(
        (len(_t) for _t in optional_tables),
        initial=offset_table_size
    ))
    bbx_offset, wtab_offset, stab_offset, ktab_offset, _ = table_offsets
    table_offsets = (_OFFS_ENTRY * num_tables)(*(
        _OFFS_ENTRY(offset=_ofs) for _ofs in table_offsets[:-1]
    ))
    offs_header = _OFFS_HEADER(max_entry=num_tables-1)
    offs_bytes = bytes(offs_header) + bytes(table_offsets)
    # offset fields in header
    # > The offset to the family glyph-width table from the beginning of
    # > the font family resource to the beginning of the table, in bytes.
    header_size = _FOND_HEADER.size + _FA_HEADER.size + sizeof(fa_list)
    fond_header.ffWTabOff = wtab_offset + header_size
    fond_header.ffStylOff = stab_offset + header_size
    fond_header.ffKernOff = ktab_offset + header_size
    return (
        bytes(fond_header) + bytes(fa_header) + bytes(fa_list)
        + offs_bytes + b''.join(optional_tables)
    )


def _create_bbx_table(style_groups):
    """Bounding-box table (optional, but no clear way to indicate if it's present)"""
    bbx_header = _BBX_HEADER(max_entry=len(style_groups)-1,)
    # we need one bounding box entry per style
    # metrics are scalable given as fixed-point fraction for a 1pt font
    # N.B. FONDU seems to just put integer pixel values here
    bbx_list = tuple(
        _BBX_ENTRY(
            style=_style_code,
            left=_float_to_fixed(_font.ink_bounds.left / _font.point_size),
            bottom=_float_to_fixed(_font.ink_bounds.bottom / _font.point_size),
            right=_float_to_fixed(_font.ink_bounds.right / _font.point_size),
            top=_float_to_fixed(_font.ink_bounds.top / _font.point_size),
        )
        # use last (largest) font for each style
        for _style_code, (*_, _font) in style_groups
    )
    bbx_entries = (_BBX_ENTRY * len(bbx_list))(*bbx_list)
    bbx_bytes = bytes(bbx_header) + bytes(bbx_entries)
    return bbx_bytes


def _create_width_table(style_groups):
    """Family glyph-width table (optional)"""
    wtab = _WIDTH_TABLE(numWidths=len(style_groups)-1)
    wtables = tuple(
        (
            _WIDTH_ENTRY(widStyle=_style_id),
            _FIXED_TYPE.array(len(_group[-1].glyphs))(*(
                _float_to_fixed(_g.scalable_width / _group[-1].bounding_box.y)
                for _g in _group[-1].glyphs
            ))
        )
        for _style_id, _group in style_groups
    )
    wtab_bytes = bytes(wtab) + b''.join(
        bytes(_t) for _pair in wtables for _t in _pair
    )
    return wtab_bytes


def _create_style_table(style_groups):
    """Style-mapping table (optional). This maps printer fonts to screen fonts."""
    # # font name suffix subtable
    suffixes = ('-',) + tuple(sorted(set(
        to_postscript_name(_suffix)
        for _, _group in style_groups
        for _suffix in _group[-1].subfamily.split()
    )))
    used_suffixes_per_style = tuple(
        tuple(
            suffixes.index(_suffix)
            for _suffix in _group[-1].subfamily.split()
        )
        for _, _group in style_groups
    )
    used_style_ids = tuple(_id for _id, _ in style_groups)
    suffix_subtable = (
        # this is the encoding of the postscript name for a given style
        # [number of name parts] followed by pointer to name parts in this table,
        # counting from 1, with element 1 (the family name) implicit
        chr(len(_used_suffixes)+1) + ''.join(chr(2+_x) for _x in _used_suffixes)
        for _used_suffixes in used_suffixes_per_style
    )
    stringtable = (
        to_postscript_name(style_groups[-1][1][-1].family),
        *suffix_subtable,
        *suffixes
    )
    # convert to P-strings
    stringtable = tuple(string_to_pascal(_str) for _str in stringtable)
    ntab = _NAME_TABLE(stringCount=len(stringtable))
    # indexes in the style name table count from 1, for some reason (Adobe docs):
    # > Because the Suffix List is part of the Style Name Table, these indexes count
    # > from the beginning of the Style Name Table. In particular, note that the
    # > number of strings counts as an entry and has index value 0.
    style_ids = (
        _style_mapping_to_style_id(_mapping_value)
        for _mapping_value in range(48)
    )
    indexes = []
    for id in style_ids:
        try:
            indexes.append(1 + used_style_ids.index(id))
        except ValueError:
            # we repeat the last index for unused entries. Adobe docs seem to suggest
            # these could be 0 but that crashes FontForge
            # FontForge treats repeated values as a not-in-use sentinel.
            indexes.append(indexes[-1] if indexes else 0)
    # # glyph-name encoding subtable
    # generate empty encoding table - I don't know how to construct correctly
    # and FontForge code comments suggest that FontManager rejects fonts that have this table.
    etab = _ENC_TABLE(stringCount=0)
    # bit field holding rendering hints - see I.M. p 4-101
    # > 0 This bit is set to 1 if the font name needs coordinating.
    # following FONDU, allow simulated style if not explicitly defined
    font_class = 1<<0
    if any('outline' in _f.decoration for _, _group in style_groups for _f in _group):
        font_class &= 1<<3
    if any(_f.weight == 'bold' for _, _group in style_groups for _f in _group):
        font_class &= 1<<4
    if any(_f.slant == 'italic' for _, _group in style_groups for _f in _group):
        font_class &= 1<<6
    if any(_f.setwidth == 'condensed' for _, _group in style_groups for _f in _group):
        font_class &= 1<<7
    if any(_f.setwidth == 'expanded' for _, _group in style_groups for _f in _group):
        font_class &= 1<<8
    # putting together the style-mapping table
    stab = _STYLE_TABLE(
        fontClass=font_class,
        # offset from the start of this table to the glyph-encoding subtable component
        offset=_STYLE_TABLE.size + sizeof(ntab) + sum(len(_s) for _s in stringtable),
        # indexes into the font suffix name table that follows this table
        # "This is an array of 48 integer index values"
        # note C summary has 47 but Pascal summary has 0..47 inclusive
        indexes=(be.int8 * 48)(*indexes),
    )
    stab_bytes = bytes(stab) + bytes(ntab) + b''.join(stringtable) + bytes(etab)
    return stab_bytes


def _style_mapping_to_style_id(mapping_value):
    """Convert Mac style id to Style Mapping used for postscript table."""
    # mapping removes bit 2, underline
    # see 0091.Mac_Fond.pdf p13 table 2
    return ((mapping_value & 0b111100) << 1) + (mapping_value & 0b11)



def _create_kerning_table(style_groups):
    """Kerning table (optional).
    """
    num_styles = len(style_groups)
    ktab = _KERN_TABLE(numKerns=num_styles-1)
    ktab_bytes = bytearray(bytes(ktab))
    for style_id, group in style_groups:
        # NOTE that the format assumes one kerning table per style,
        # which is linearly scaled by bounding_box.y
        sample_font = group[-1]
        kerning_pairs = [
            _KERN_PAIR(
                kernFirst=int(_g.codepoint),
                kernSecond=int(sample_font.get_glyph(_label).codepoint),
                # kerning value in 1pt fixed format
                kernWidth=_float_to_fixed(_value / sample_font.bounding_box.y),
            )
            for _g in sample_font.glyphs
            for _label, _value in _g.right_kerning.items()
        ] + [
            _KERN_PAIR(
                kernFirst=int(sample_font.get_glyph(_label).codepoint),
                kernSecond=int(_g.codepoint),
                # kerning value in 1pt fixed format
                kernWidth=_float_to_fixed(_value / sample_font.bounding_box.y),
            )
            for _g in sample_font.glyphs
            for _label, _value in _g.left_kerning.items()
        ]
        # number of entries - 1
        ke = _KERN_ENTRY(
            kernStyle=style_id,
            kernLength=len(kerning_pairs),
        )
        kpairs = (_KERN_PAIR * len(kerning_pairs))(*kerning_pairs)
        ktab_bytes += bytes(ke) + bytes(kpairs)
    return bytes(ktab_bytes)
