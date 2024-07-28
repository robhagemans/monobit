"""
monobit.storage.formats.pcgeos - PC/GEOS 2.0+ (aka GeoWorks, NewDeal, BreadBox)

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate


from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph
from monobit.base import Props, reverse_dict
from monobit.base.struct import StructError, bitfield, flag, little_endian as le
from monobit.base.binary import ceildiv, align

from monobit.storage.utils.limitations import make_contiguous


_BSWF_SIG = b'BSWF'


_FontFileInfo = le.Struct(
    # > "BSWF"
    FFI_signature='4s',
    # > minor version (0)
    FFI_minorVer='byte',
    # > major version (1)
    FFI_majorVer='byte',
    # > size of font info section
    # i.e. size of FontInfo + PointSizeTable, minus 1  (?)
    FFI_headerSize='word',
)

# typedef ByteFlags FontAttrs;
#define FA_USEFUL       0x80
#define FA_FIXED_WIDTH  0x40
#define FA_ORIENT       0x20
#define FA_OUTLINE      0x10
#define FA_FAMILY       0x0f
#define FA_FAMILY_OFFSET 0

_FontAttrs = le.Struct(
    FA_FAMILY=bitfield('uint8', 4),
    FA_OUTLINE=bitfield('uint8', 1),
    FA_ORIENT=bitfield('uint8', 1),
    FA_FIXED_WIDTH=bitfield('uint8', 1),
    FA_USEFUL=bitfield('uint8', 1),
)


# typedef byte FontFamily;
#define FF_NON_PORTABLE 0x0007
#define FF_SPECIAL 0x0006
#define FF_MONO 0x0005
#define FF_SYMBOL 0x0004
#define FF_ORNAMENT 0x0003
#define FF_SCRIPT 0x0002
#define FF_SANS_SERIF 0x0001
#define FF_SERIF 0x0000
_FAMILY_TO_STYLE = {
    0x0004: 'symbol',
    0x0002: 'script',
    0x0001: 'sans serif',
    0x0000: 'serif',
}
_STYLE_TO_FAMILY = reverse_dict(_FAMILY_TO_STYLE)


_FontInfo = le.Struct(
    # > font ID
    FI_fontID='word',
    # > font manufacturer ID
    # this is more of a "which vendor's format" field - for bitmap it is 0
    FI_maker='word',
    # > font family, etc.
    FI_family=_FontAttrs,
    # > typeface name
    FI_faceName='20s',
    # > start of table of point sizes
    FI_pointSizeTab='word',
    # > end of bitmap faces
    # actually, it's the end of the table of point sizes?
    FI_pointSizeEnd='word',
    # > start of outline table
    FI_outlineTab='word',
    # > end of outline faces
    FI_outlineEnd='word',
    # for "DBCS_PCGEOS" there are *two* byte fields here,
    #     FI_firstChar: char               ;first char included
    #     FI_lastChar: char               ;last char included
    # word-alignment
    unused='byte',
)


# typedef ByteFlags TextStyle;
#define TS_OUTLINE				0x40
#define TS_BOLD 				0x20
#define TS_ITALIC 				0x10
#define TS_SUPERSCRIPT 				0x08
#define TS_SUBSCRIPT 				0x04
#define TS_STRIKE_THRU 				0x02
#define TS_UNDERLINE 				0x01
_TextStyle = le.Struct(
    TS_UNDERLINE=flag,
    TS_STRIKE_THRU=flag,
    TS_SUBSCRIPT=flag,
    TS_SUPERSCRIPT=flag,
    TS_ITALIC=flag,
    TS_BOLD=flag,
    TS_OUTLINE=flag,
    unknown=flag,
)

def _style_to_decoration(style):
    return ' '.join(_deco for _deco in (
        'underline' if style.TS_UNDERLINE else '',
        'strikethrough' if style.TS_STRIKE_THRU else '',
        'subscript' if style.TS_SUBSCRIPT else '',
        'superscript' if style.TS_SUPERSCRIPT else '',
        'outline' if style.TS_OUTLINE else '',
    ) if _deco)


def _to_text_style(font):
    return _TextStyle(
        TS_UNDERLINE='underline' in font.decoration,
        TS_STRIKE_THRU='strikethrough' in font.decoration,
        TS_SUBSCRIPT='subscript' in font.decoration,
        TS_SUPERSCRIPT='superscript' in font.decoration,
        TS_ITALIC=font.slant == 'italic',
        TS_BOLD=font.weight == 'bold',
        TS_OUTLINE='outline' in font.decoration,
    )


_PointSizeEntry = le.Struct(
    # > style of face
    PSE_style=_TextStyle,
    # note that there are different versions of this struct
    # the DBCS_PCGEOS version has this, instead of below WBFixed field
        # PSE_pointSize       sbyte                   ;integer point size <128
        # PSE_charSet         FontCharSet             ;characters in section
    # > point size
    # > PSE_pointSize       WBFixed                 ;point size
    # "WBFixed" format - assume byte fractional part, byte integer part
    # though elsewhere I seem to need byte + word for WBFixed??
    PSE_pointSize_int='int8',
    PSE_pointSize_frac='uint8',
    # > size of data
    PSE_dataSize='word',
    # > position in file
    # PSE_dataPosLo='word',
    # > position in file
    # PSE_dataPosHi='word',
    PSE_dataPos='dword',
    # word-alignment
    unused='byte',
)

_WBFixed = le.Struct(
    frac='byte',
    int='word',
)

def _wbfixed_to_float(wbfixed_value):
    """Convert WBFixed value to float."""
    return wbfixed_value.int + wbfixed_value.frac / 256


def _float_to_wbfixed(float_value):
    """Convert float value to WBFixed."""
    return _WBFixed(
        frac=int((float_value-int(float_value)) * 256),
        int=int(float_value),
    )


# typedef ByteFlags FontBufFlags;
#define FBF_DEFAULT_FONT    0x80
#define FBF_MAPPED_FONT     0x40
#define FBF_IS_OUTLINE      0x10
#define FBF_IS_REGION       0x08
#define FBF_IS_COMPLEX      0x04
#define FBF_IS_INVALID      0x02
_FontBufFlags = le.Struct(
    unknown_0x01=flag,
    FBF_IS_INVALID=flag,
    FBF_IS_COMPLEX=flag,
    FBF_IS_REGION=flag,
    FBF_IS_OUTLINE=flag,
    unknown_0x20=flag,
    FBF_MAPPED_FONT=flag,
    FBF_DEFAULT_FONT=flag,
)


# typedef word FontMaker;
#define FM_PRINTER                              0xf000
#define FM_MICROLOGIC                           0xe000
#define FM_ATECH                                0xd000
#define FM_PUBLIC                               0xc000
#define FM_AGFA                                 0x4000
#define FM_BITSTREAM                            0x3000
#define FM_ADOBE                                0x2000
#define FM_NIMBUSQ                              0x1000
#define FM_BITMAP                               0x0000


_FontBuf = le.Struct(
    # > actual size of data (bytes)
    FB_dataSize='word',
    # > manufacturer ID
    # > FontMaker type
    FB_maker='word',
    # > average character width
    FB_avgwidth=_WBFixed,
    # > width of widest character
    FB_maxwidth=_WBFixed,
    # > offset to top of font box
    FB_heightAdjust=_WBFixed,
    # > height of characters
    FB_height=_WBFixed,
    # > height of accent portion.
    FB_accent=_WBFixed,
    # > top of lower case character boxes.
    FB_mean=_WBFixed,
    # > offset to top of ascent
    FB_baseAdjust=_WBFixed,
    # > position of baseline from top of font
    FB_baselinePos=_WBFixed,
    # > maximum descent (from baseline)
    FB_descent=_WBFixed,
    # > recommended external leading
    FB_extLeading=_WBFixed,
    # >   line spacing = FB_height +
    # >                  FB_extLeading +
    # >                  FB_heightAdjust
    # > number of kerning pairs
    FB_kernCount='word',
    # > offset to kerning pair table
    # > nptr.KernPair
    FB_kernPairPtr='word',
    # > offset to kerning value table
    # > nptr.BBFixed
    FB_kernValuePtr='word',
# if DBCS_PCGEOS
#     FB_firstChar        Chars           ; first char in section
#     FB_lastChar         Chars           ; last char in section
#     FB_defaultChar      Chars           ; default character
# else
    # > first char defined
    FB_firstChar='byte',
    # > last char defined
    FB_lastChar='byte',
    # > default character
    FB_defaultChar='byte',
# endif
    # > underline position (from baseline)
    FB_underPos=_WBFixed,
    # > underline thickness
    FB_underThickness=_WBFixed,
    # > position of the strike-thru
    FB_strikePos=_WBFixed,
    # > maximum above font box
    FB_aboveBox=_WBFixed,
    # > maximum below font box
    FB_belowBox=_WBFixed,
    # > Bounds are signed integers, in device coords, and are
    # > measured from the upper left of the font box where
    # > character drawing starts from.
    #
    # > minimum left side bearing
    FB_minLSB='int16',
    # ; minimum top side bound
    FB_minTSB='int16',
# if not DBCS_PCGEOS
    # > maximum bottom side bound
    FB_maxBSB='int16',
    # ; maximum right side bound
    FB_maxRSB='int16',
# endif
    # > height of font (invalid for rotation)
    FB_pixHeight='word',
    # > special flags
    FB_flags=_FontBufFlags,
    # > usage counter for this font
    FB_heapCount='word',
    # FB_charTable        CharTableEntry <>
)


_CharTableFlags = le.Struct(
    # > pad to a BYTE only
    # . TRUE if negative left-side bearing
    CTF_NEGATIVE_LSB=flag,
    # > TRUE if very tall
    CTF_ABOVE_ASCENT=flag,
    # > TRUE if very low
    CTF_BELOW_DESCENT=flag,
    # > TRUE if no data
    CTF_NO_DATA=flag,
    # > TRUE if first of a kern pair
    CTF_IS_FIRST_KERN=flag,
    # > TRUE if second of a kern pair
    CTF_IS_SECOND_KERN=flag,
    # > TRUE if character normally invisible
    CTF_NOT_VISIBLE=flag,
)

_CharTableEntry = le.Struct(
    # > Offset to data
    # > nptr.CharData
    CTE_dataOffset='word',
    # > character width
    CTE_width=_WBFixed,
    # > flags
    CTE_flags=_CharTableFlags,
    # > LRU count
    CTE_usage='word',
)


_CharData = le.Struct(
    # > width of picture data in bits
    CD_pictureWidth='byte',
    # > number of rows of data
    CD_numRows='byte',
    # > (signed) offset to first row
    CD_yoff='int8',
    # > (signed) offset to first column
    CD_xoff='int8',
    # > data for character
    # CD_data
)


@loaders.register(
    name='pcgeos',
    magic=(_BSWF_SIG,),
    patterns=('*.fnt',),
)
def load_pcgeos(instream):
    """Load a PC/GEOS v2.0+ bitmap font file."""
    font_file_info = _FontFileInfo.read_from(instream)
    logging.debug('FontFileInfo: %s', font_file_info)
    if font_file_info.FFI_signature != _BSWF_SIG:
        if font_file_info.FFI_signature[:2] == b'\xEF\xBE':
            raise FileFormatError('PC/GEOS v1.2 fonts not supported.')
        if font_file_info.FFI_signature[:2] == b'\x80\x10':
            raise FileFormatError('PC/GEOS v1.0 fonts not supported.')
        raise FileformatError('Not a PC-GEOS font file: incorrect signature')
    font_info = _FontInfo.read_from(instream)
    logging.debug('FontInfo: %s', font_info)
    if font_info.FI_maker != 0:
        logging.warning(
            'Non-bitmap PC/GEOS font file; '
            'will try to extract bitmap glyphs, if any.'
        )
    # the +7 offset is strange, as the FFI header is 8 bytes long
    instream.seek(font_info.FI_pointSizeTab + 7)
    n_entries = (font_info.FI_pointSizeEnd - font_info.FI_pointSizeTab) //_PointSizeEntry.size
    point_size_table = (_PointSizeEntry * n_entries).read_from(instream)
    # the first FontBuf actually starts 1 byte earlier than where we are now
    # i.e. it overwrites the unused padding byte in the last entry
    fonts = []
    for point_size_entry in point_size_table:
        logging.debug('PointSizeEntry: %s', point_size_entry)
        instream.seek(point_size_entry.PSE_dataPos)
        font_buf = _FontBuf.read_from(instream)
        logging.debug('FontBuf: %s', font_buf)
        n_chars = font_buf.FB_lastChar - font_buf.FB_firstChar + 1
        char_table = (_CharTableEntry * n_chars).read_from(instream)
        glyphs = []
        for cp, char_table_entry in enumerate(
                char_table, font_buf.FB_firstChar
            ):
            # this appears to be necessary
            if char_table_entry.CTE_dataOffset == 0:
                continue
            # this is usually (?) a no-op at this point
            instream.seek(
                point_size_entry.PSE_dataPos + char_table_entry.CTE_dataOffset
            )
            try:
                char_data = _CharData.read_from(instream)
            except StructError:
                if not glyph:
                    raise
                break
            if char_table_entry.CTE_flags.CTF_NO_DATA:
                charbytes = b''
            else:
                byte_width = ceildiv(char_data.CD_pictureWidth, 8)
                byte_size = char_data.CD_numRows * byte_width
                # blank glyph still has one null row
                byte_size = max(1, byte_size)
                charbytes = instream.read(byte_size)
            glyph = Glyph.from_bytes(
                charbytes, width=char_data.CD_pictureWidth,
                shift_up=(
                    _wbfixed_to_float(font_buf.FB_baselinePos)
                    - (char_data.CD_numRows+char_data.CD_yoff)
                ),
                left_bearing=char_data.CD_xoff,
                right_bearing=(
                    _wbfixed_to_float(char_table_entry.CTE_width)
                    - char_data.CD_pictureWidth
                    - char_data.CD_xoff
                ),
                codepoint=cp,
            )
            glyphs.append(glyph)
        font = Font(
            glyphs,
            family=font_info.FI_faceName.decode('ascii', 'replace'),
            font_id=font_info.FI_fontID,
            point_size=(
                point_size_entry.PSE_pointSize_int +
                point_size_entry.PSE_pointSize_frac / 256
            ),
            average_width=_wbfixed_to_float(font_buf.FB_avgwidth),
            max_width=_wbfixed_to_float(font_buf.FB_maxwidth),
            # FB_heightAdjust=font_buf.FB_heightAdjust,
            x_height=_wbfixed_to_float(font_buf.FB_mean),
            # FB_baseAdjust=font_buf.FB_baseAdjust,
            ascent=(
                _wbfixed_to_float(font_buf.FB_height)
                - _wbfixed_to_float(font_buf.FB_accent)
                - _wbfixed_to_float(font_buf.FB_descent)
            ),
            descent=_wbfixed_to_float(font_buf.FB_descent),
            line_height=(
                _wbfixed_to_float(font_buf.FB_height)
                + _wbfixed_to_float(font_buf.FB_extLeading)
                + _wbfixed_to_float(font_buf.FB_heightAdjust)
            ),
            default_char=font_buf.FB_defaultChar,
            underline_descent=(
                _wbfixed_to_float(font_buf.FB_underPos) - _wbfixed_to_float(font_buf.FB_baselinePos)
            ),
            underline_thickness=_wbfixed_to_float(font_buf.FB_underThickness),
            strikethrough_ascent=(
                _wbfixed_to_float(font_buf.FB_baselinePos)
                - _wbfixed_to_float(font_buf.FB_strikePos) + 1
            ),
            decoration=_style_to_decoration(point_size_entry.PSE_style),
            slant='italic' if point_size_entry.PSE_style.TS_ITALIC else None,
            weight='bold' if point_size_entry.PSE_style.TS_BOLD else None,
            style=_FAMILY_TO_STYLE.get(font_info.FI_family.FA_FAMILY, None),
        )
        font = font.label(char_from='pc-geos')
        fonts.append(font)
    return fonts


@savers.register(linked=load_pcgeos)
def save_pcgeos(fonts, outstream):
    """Save to a PC/GEOS v2.0+ bitmap font file."""
    fonts, common_props = _prepare_pcgeos(fonts)
    fonts = tuple(
        _f.label(codepoint_from=_f.encoding).subset(codepoints=range(256))
        for _f in fonts if _f.glyphs
    )
    n_sizes = len(fonts)
    # FontFileInfo header
    font_file_info = _FontFileInfo(
        FFI_signature=_BSWF_SIG,
        FFI_minorVer=0,
        FFI_majorVer=1,
        FFI_headerSize=_FontInfo.size - 1 + _PointSizeEntry.size * n_sizes,
    )
    # strange 7 byte offset
    point_size_tab_offset = _FontFileInfo.size + _FontInfo.size - 7
    # FontInfo header
    font_info = _FontInfo(
        FI_fontID=int(common_props.font_id),
        FI_maker=0,
        FI_family=_FontAttrs(
            FA_FAMILY=(
                5 if common_props.fixed_width
                else _STYLE_TO_FAMILY.get(common_props.style, 0)
            ),
            FA_FIXED_WIDTH=common_props.fixed_width,
            FA_USEFUL=1,
        ),
        FI_faceName=common_props.family,
        FI_pointSizeTab=point_size_tab_offset,
        FI_pointSizeEnd=point_size_tab_offset + _PointSizeEntry.size * n_sizes,
    )
    # per-font sections
    data_offset = 0
    font_data = []
    point_size_table = []
    for font in fonts:
        data = _create_pcgeos_font_section(font)
        font_data.append(data)
        point_size_table.append(_PointSizeEntry(
            PSE_style=_to_text_style(font),
            PSE_pointSize_int=int(font.point_size),
            PSE_pointSize_frac=int(256*(font.point_size-int(font.point_size))),
            PSE_dataSize=len(data),
            PSE_dataPos=data_offset + (
                _FontFileInfo.size + _FontInfo.size
                # -1 as we will clip off the last byte
                + (_PointSizeEntry * n_sizes).size - 1
            ),
        ))
        data_offset += len(data)
    point_size_table = (_PointSizeEntry * n_sizes)(*point_size_table)
    # write out pcgeos file
    outstream.write(bytes(font_file_info))
    outstream.write(bytes(font_info))
    # note that we clip off the final null byte
    outstream.write(bytes(point_size_table)[:-1])
    for data in font_data:
        outstream.write(data)


def _create_pcgeos_font_section(font):
    """Create pcgeos font section for one font."""
    baseline = font.raster_size.y + min(_g.shift_up for _g in font.glyphs)
    first_char = int(min(font.get_codepoints()))
    last_char = int(max(font.get_codepoints()))
    glyphs = tuple(
        font.get_glyph(_cp, missing=None)
        for _cp in range(first_char, last_char + 1)
    )
    n_chars = len(glyphs)
    glyphbytes = tuple(
        (
            bytes(_CharData(
                CD_pictureWidth=_g.width,
                CD_numRows=_g.height,
                CD_yoff=(baseline - _g.height - _g.shift_up),
                CD_xoff=_g.left_bearing,
            ))
            # empty glyph still stores one byte of zeros
            + (_g.as_bytes() or b'\0')
        ) if _g is not None else (
            # missing glyph omitted altogether, but needs a record in CharTable
            b''
        )
        for _g in glyphs
    )
    glyphdata = b''.join(glyphbytes)
    glyph_offsets = accumulate(
        (len(_b) for _b in glyphbytes[:-1]),
        initial=0
    )
    header_size = _FontBuf.size + (_CharTableEntry * n_chars).size
    font_buf = _FontBuf(
        FB_dataSize=(
            len(glyphdata) + _FontBuf.size
            + (_CharTableEntry * n_chars).size
        ),
        FB_maker=0,
        FB_avgwidth=_float_to_wbfixed(font.average_width),
        FB_maxwidth=_float_to_wbfixed(font.max_width),
        # > offset to top of font box
        # FB_heightAdjust=_WBFixed,
        FB_height=_float_to_wbfixed(font.raster_size.y),
        FB_accent=_float_to_wbfixed(font.raster_size.y - font.pixel_size),
        # > top of lower case character boxes.
        FB_mean=_float_to_wbfixed(font.x_height),
        # > offset to top of ascent
        # FB_baseAdjust=_WBFixed,
        FB_baselinePos=_float_to_wbfixed(baseline),
        FB_descent=_float_to_wbfixed(font.descent),
        FB_extLeading=_float_to_wbfixed(font.line_height - font.raster_size.y),
        # I don't know how kerning works in this format and have no samples
        FB_kernCount=0,
        # pointer values as in Berkeley.fnt
        FB_kernPairPtr=header_size,
        FB_kernValuePtr=header_size,
        FB_firstChar=first_char,
        FB_lastChar=last_char,
        FB_defaultChar=int(font.get_default_glyph().codepoint or first_char),
        FB_underPos=_float_to_wbfixed(baseline + font.underline_descent),
        FB_underThickness=_float_to_wbfixed(font.underline_thickness),
        # > position of the strike-thru
        FB_strikePos=_float_to_wbfixed(baseline - font.strikethrough_ascent + 1),
        # > maximum above font box
        # FB_aboveBox=_WBFixed,
        # > maximum below font box
        # FB_belowBox=_WBFixed,
        FB_minLSB=min(_g.left_bearing for _g in font.glyphs),
        FB_minTSB=0,
        FB_maxBSB=font.raster_size.y,
        FB_maxRSB=max(_g.advance_width for _g in font.glyphs),
        FB_pixHeight=font.raster_size.y,
        # # > special flags
        # FB_flags=_FontBufFlags,
        # this is the value used in font samples - perhaps a sentinel? 666 dec
        FB_heapCount=0x29a,
    )
    char_table = (_CharTableEntry * n_chars)(*(
        _CharTableEntry(
            CTE_dataOffset=0,
            CTE_flags=_CharTableFlags(
                CTF_NO_DATA=True,
            )
        ) if _glyph is None else
        _CharTableEntry(
            CTE_dataOffset=_FontBuf.size + (_CharTableEntry * n_chars).size + _ofs,
            CTE_width=_float_to_wbfixed(_glyph.advance_width),
            CTE_flags=_CharTableFlags(
                CTF_NEGATIVE_LSB=(_glyph.left_bearing < 0),
                # > TRUE if very tall
                # CTF_ABOVE_ASCENT=flag,
                # > TRUE if very low
                # CTF_BELOW_DESCENT=flag,
                # if we set this, omit the 1-byte placeholder for glyph data
                # CTF_NO_DATA=flag,
                CTF_IS_FIRST_KERN=False,
                CTF_IS_SECOND_KERN=False,
                # CTF_NOT_VISIBLE=flag,
            ),
            CTE_usage=0,
        )
        for _glyph, _ofs in zip(glyphs, glyph_offsets)
    ))
    return b''.join((
        bytes(font_buf),
        bytes(char_table),
        glyphdata,
    ))


def _prepare_pcgeos(fonts):
    """Validate fonts for storing in PC-GEOS format; extract metadata."""
    if len(set(_f.family for _f in fonts)) > 1:
        raise FileFormatError(
            'PC-GEOS font file can only store fonts from one family.'
        )
    common_props = _get_metadata(fonts[0])
    return fonts, common_props


def _get_metadata(font):
    try:
        font_id = int(font.font_id)
    except ValueError:
        font_id = 0
    return Props(
        font_id=font_id,
        family=font.family.encode('ascii', 'replace'),
        fixed_width=font.spacing in ('character-cell', 'monospace'),
        style=font.style,
    )
