"""
monobit.formats.os2.gpifont - OS/2 GPI font resource parser

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT


this is mostly ported code from gpifont.c and gpifont.h
- http://www.altsan.org/programming/os2font_src.zip
- https://github.com/altsan/os2-gpi-font-tools

notice for gpifont.c and gpifont.h:
>
>  (C) 2012 Alexander Taylor
>  This code is placed in the public domain.
>
"""

import logging

from ...magic import FileFormatError
from ...glyph import Glyph
from ...font import Font
from ...properties import Props
from ...struct import little_endian as le, bitfield
from ...binary import ceildiv


GPI_MAGIC = b'\xfe\xff\xff\xff'


# Text signatures for standard OS/2 bitmap fonts.
OS2FNT_SIGNATURE = "OS/2 FONT"
OS2FNT2_SIGNATURE = "OS/2 FONT 2"

# Binary signatures for various OS/2 font records.
SIG_OS2FONTSTART = 0xFFFFFFFE
SIG_OS2METRICS = 0x1
SIG_OS2FONTDEF = 0x2
SIG_OS2KERN = 0x3
SIG_OS2ADDMETRICS = 0x4
SIG_OS2FONTEND = 0xFFFFFFFF


# GPI categorizes fonts in 3 types according to character increment definition:
# Type 1 : Fixed-width font
# Type 2 : Proportional-width font with each character increment defined as
#          one value in the character definition.
# Type 3 : Proportional-width font with each character increment defined in
#          terms of: a_space + b_space + c_space
#             Where: a_space = leading space in front of the character
#                    b_space = width of the character glyph
#                    c_space = space following the character
#
# Each type is required to have specific values of flFontDef and flCharDef
# in the font definition header.  These values are defined below.
OS2FONTDEF_FONT1 = 0x47
OS2FONTDEF_FONT2 = 0x42
OS2FONTDEF_FONT3 = 0x42
OS2FONTDEF_CHAR1 = 0x81
OS2FONTDEF_CHAR2 = 0x81
OS2FONTDEF_CHAR3 = 0XB8


# A generic font record structure, mostly used for typecasting.
GENERICRECORD = le.Struct(
    # structure identity code
    Identity='uint32',
    # structure size in bytes
    ulSize='uint32',
)

# A font signature (header) block.
OS2FONTSTART = le.Struct(
    # 0xFFFFFFFE
    Identity='uint32',
    # size of this structure
    ulSize='uint32',
    # string indicating font format
    achSignature='12s',
)

# A font end signature block (identical to the generic record).  The
# Identity field in this case should be 0xFFFFFFFF.
OS2FONTEND = GENERICRECORD


# The font definition header.  Not all of these fields may be used, depending
# on the font type (indicated by the flags in fsFontdef).
OS2FONTDEFHEADER = le.Struct(
    # 0x00000002
    ulIdentity='uint32',
    # size of this structure
    ulSize='uint32',
    # flags indicating which fields are used
    fsFontdef='uint16',
    # flags indicating format of char defs
    fsChardef='uint16',
    # size (in bytes) of each char definition
    usCellSize='uint16',
    # char cell-width in pixels (type 1 only)
    xCellWidth='int16',
    # char cell-height in pixels
    yCellHeight='int16',
    # char increment in pixels (type 1 only)
    xCellIncrement='int16',
    # character a_space (type 3 only)
    xCellA='int16',
    # character b_space (type 3 only)
    xCellB='int16',
    # character c_space (type 3 only)
    xCellC='int16',
    # distance between baseline & top of cell
    pCellBaseOffset='int16',
)


# flag values
# http://cd.textfiles.com/hobbesos29411/LIB/EMX/INCLUDE/OS2EMX.H

#define FATTR_SEL_ITALIC 0x0001
#define FATTR_SEL_UNDERSCORE 0x0002
#define FATTR_SEL_OUTLINE 0x0008
#define FATTR_SEL_STRIKEOUT 0x0010
#define FATTR_SEL_BOLD 0x0020

#define FATTR_TYPE_KERNING 0x0004
#define FATTR_TYPE_MBCS 0x0008
#define FATTR_TYPE_DBCS 0x0010
#define FATTR_TYPE_ANTIALIASED	0x0020

#define FATTR_FONTUSE_NOMIX 0x0002
#define FATTR_FONTUSE_OUTLINE	0x0004
#define FATTR_FONTUSE_TRANSFORMABLE	0x0008

#define FM_TYPE_FIXED 0x0001
#define FM_TYPE_LICENSED 0x0002
#define FM_TYPE_KERNING 0x0004
#define FM_TYPE_DBCS 0x0010
#define FM_TYPE_MBCS 0x0018
#define FM_TYPE_64K  0x8000
#define FM_TYPE_ATOMS 0x4000
#define FM_TYPE_FAMTRUNC 0x2000
#define FM_TYPE_FACETRUNC 0x1000

_TYPE_FLAGS = le.Struct(
    FM_TYPE_FIXED=bitfield('uint16', 1),
    FM_TYPE_LICENSED=bitfield('uint16', 1),
    FM_TYPE_KERNING=bitfield('uint16', 1),
    FM_TYPE_MBCS=bitfield('uint16', 1),
    FM_TYPE_DBCS=bitfield('uint16', 1),
    unknnown=bitfield('uint16', 7),
    FM_TYPE_FACETRUNC=bitfield('uint16', 1),
    FM_TYPE_FAMTRUNC=bitfield('uint16', 1),
    FM_TYPE_ATOMS=bitfield('uint16', 1),
    FM_TYPE_64K=bitfield('uint16', 1),
)

#define FM_DEFN_OUTLINE 0x0001
#define FM_DEFN_IFI 0x0002
#define FM_DEFN_WIN 0x0004
#define FM_DEFN_GENERIC 0x8000

_DEFN_FLAGS = le.Struct(
    FM_DEFN_OUTLINE=bitfield('uint16', 1),
    FM_DEFN_IFI=bitfield('uint16', 1),
    FM_DEFN_WIN=bitfield('uint16', 1),
    unknown=bitfield('uint16', 12),
    FM_DEFN_GENERIC=bitfield('uint16', 1),
)

#define FM_SEL_ITALIC 0x0001
#define FM_SEL_UNDERSCORE 0x0002
#define FM_SEL_NEGATIVE 0x0004
#define FM_SEL_OUTLINE 0x0008
#define FM_SEL_STRIKEOUT 0x0010
#define FM_SEL_BOLD 0x0020
#define FM_SEL_ISO9241_TESTED 0x0040

_SELECTION_FLAGS = le.Struct(
    FM_SEL_ITALIC=bitfield('uint16', 1),
    FM_SEL_UNDERSCORE=bitfield('uint16', 1),
    FM_SEL_NEGATIVE=bitfield('uint16', 1),
    FM_SEL_OUTLINE=bitfield('uint16', 1),
    FM_SEL_STRIKEOUT=bitfield('uint16', 1),
    FM_SEL_BOLD=bitfield('uint16', 1),
    FM_SEL_ISO9241_TESTED=bitfield('uint16', 1),
    unused=bitfield('uint16', 9),
)
#define FM_CAP_NOMIX 0x0001

#define FM_ISO_9518_640 0x01
#define FM_ISO_9515_640 0x02
#define FM_ISO_9515_1024 0x04
#define FM_ISO_9517_640 0x08
#define FM_ISO_9517_1024 0x10


# from gpifont.h

# The font metrics structure ("IBM Font Object Content Architecture" metrics).
OS2FOCAMETRICS = le.Struct(
    # 0x00000001
    ulIdentity='uint32',
    # size of this structure
    ulSize='uint32',
    # font family name (null-terminated)
    szFamilyname='32s',
    # font face name (null-terminated)
    szFacename='32s',
    # the registered font ID number
    usRegistryId='uint16',
    # font encoding (850 indicates PMUGL)
    usCodePage='uint16',
    # height of the em square
    yEmHeight='int16',
    # lowercase x height
    yXHeight='int16',
    # total cell height above baseline
    yMaxAscender='int16',
    # total cell depth below baseline
    yMaxDescender='int16',
    # height (+) of a lowercase ascender
    yLowerCaseAscent='int16',
    # height (+) of a lowercase descender
    yLowerCaseDescent='int16',
    # space above glyph used for accents
    yInternalLeading='int16',
    # extra linespace padding
    yExternalLeading='int16',
    # average character width
    xAveCharWidth='int16',
    # maximum character increment (width)
    xMaxCharInc='int16',
    # width of the em square
    xEmInc='int16',
    # sum of max ascender and descender
    yMaxBaselineExt='int16',
    # nominal character slope in degrees
    sCharSlope='int16',
    # inline text direction in degrees
    sInlineDir='int16',
    # nominal character rotation angle
    sCharRot='int16',
    # font weight class (1000-9000)
    usWeightClass='uint16',
    # font width class (1000-9000)
    usWidthClass='uint16',
    # target horiz. resolution (dpi)
    xDeviceRes='int16',
    # target vert. resolution (dpi)
    yDeviceRes='int16',
    # codepoint of the first character
    usFirstChar='uint16',
    # codepoint offset of the last char
    usLastChar='uint16',
    # codepoint offset of the default char
    usDefaultChar='uint16',
    # codepoint offset of the space char
    usBreakChar='uint16',
    # font's point size multiplied by 10
    usNominalPointSize='uint16',
    # (same as above for bitmap fonts)
    usMinimumPointSize='uint16',
    # (same as above for bitmap fonts)
    usMaximumPointSize='uint16',
    # font type flags
    fsTypeFlags=_TYPE_FLAGS,
    # font definition flags
    fsDefn=_DEFN_FLAGS,
    # font selection flags
    fsSelectionFlags=_SELECTION_FLAGS,
    # font capability flags
    fsCapabilities='uint16',
    # width of subscript characters
    ySubscriptXSize='int16',
    # height of subscript characters
    ySubscriptYSize='int16',
    # x-offset of subscript characters
    ySubscriptXOffset='int16',
    # y-offset of subscript characters
    ySubscriptYOffset='int16',
    # width of superscript characters
    ySuperscriptXSize='int16',
    # height of superscript characters
    ySuperscriptYSize='int16',
    # x-offset of superscript characters
    ySuperscriptXOffset='int16',
    # y-offset of superscript characters
    ySuperscriptYOffset='int16',
    # underscore stroke thickness
    yUnderscoreSize='int16',
    # underscore depth below baseline
    yUnderscorePosition='int16',
    # strikeout stroke thickness
    yStrikeoutSize='int16',
    # strikeout height above baseline
    yStrikeoutPosition='int16',
    # number of kerning pairs defined
    usKerningPairs='uint16',
    # IBM font family class and subclass
    sFamilyClass='int16',
    # device name address (not used)
    reserved='uint32',
)

OS2FONTDIRENTRY = le.Struct(
    # The resource ID of the font
    usIndex='uint16',
    # The font's metrics
    metrics=OS2FOCAMETRICS,
    # The font's PANOSE data
    panose=le.uint8*12,
)

OS2FONTDIRENTRY_SMALL = le.Struct(
    usIndex='uint16',
    metrics=OS2FOCAMETRICS,
)

OS2FONTDIRECTORY = le.Struct(
# The size of this header
    usHeaderSize='uint16',
    # The number of fonts
    usnFonts='uint16',
    # The size of all the metrics
    usiMetrics='uint16',
    # Array of individual font info
    #OS2FONTDIRENTRY fntEntry[ 1 ];
)

# The font kerning-pairs table.  This and the following structure are a bit
# of a mystery.  They are defined here as the specification in the OS/2 GPI
# programming guide describes them.  However, the specification also says
# that the ulSize field should be 10 bytes (not 9), and doesn't describe at
# all what the cFirstpair field does.  The KERNINGPAIRS structure is even more
# problematic, as the standard GPI toolkit headers define a KERNINGPAIRS
# structure which is different from what the documentation describes.
#
# Unfortunately, I cannot find any examples of fonts which actually contain
# kerning information, and the IBM Font Editor doesn't support kerning at
# all... so there's no way to analyze how it really works.  (It's entirely
# possible that kerning support was never actually implemented.)
#
# The good news is that the kerning information is right at the end of the
# font file (except for the PANOSE structure and the font-end signature),
# so even if our kern-table parsing is flawed it shouldn't be fatal.
OS2KERNPAIRTABLE = le.Struct(
    # 0x00000003
    ulIdentity='uint32',
    # must be 10 (??)
    ulSize='uint32',
    # undocumented
    cFirstpair='uint8',
)

OS2KERNINGPAIRS = le.Struct(
    # first character of pair
    sFirstChar='uint16',
    # second character of pair
    sSecondChar='uint16',
    # kerning amount
    sKerningAmount='int16',
)

# The "additional metrics" structure contains the PANOSE table.
OS2ADDMETRICS = le.Struct(
    # 0x00000004
    ulIdentity='uint32',
    # structure size (20 bytes)
    ulSize='uint32',
    # PANOSE table padded to 12 bytes
    panose=le.uint8.array(12),
)

# An individual character definition for a type 1 or 2 font.
OS2CHARDEF1 = le.Struct(
    # offset of glyph bitmap within the font
    ulOffset='uint32',
    # width of the glyph bitmap (in pixels)
    ulWidth='uint16',
)

# An individual character definition for a type 3 font.
OS2CHARDEF3 = le.Struct(
    # offset of glyph bitmap within the font
    ulOffset='uint32',
    # character a_space (in pixels)
    aSpace='int16',
    # character b_space (in pixels)
    bSpace='int16',
    # character c_space (in pixels)
    cSpace='int16',
)


def convert_os2_font_resource(resource):
    """Convert an OS/2 font resource."""
    parsed = parse_os2_font_resource(resource)
    font = Font(
        convert_os2_glyphs(parsed),
        source_format='OS/2 GPI',
        **vars(convert_os2_properties(parsed))
    )
    font = font.label()
    return font


def parse_os2_font_resource(pBuffer):
    """
    Parses a standard GPI-format OS/2 font resource.  Takes as input an
    already-populated memory buffer containing the raw font resource data.
    On successful return, the fields within the OS2FONTRESOURCE structure
    will point to the appropriate structures within the font file data.

    NOTE: Even if this function returns success, the pPanose and pEnd fields
    of the pFont structure may be NULL.  The application must check for this
    if it intends to use these fields.
    """
    # Verify the file format
    pRecord = GENERICRECORD.from_bytes(pBuffer)
    if (
            pRecord.Identity != SIG_OS2FONTSTART
            or pRecord.ulSize != OS2FONTSTART.size
        ):
        raise FileFormatError('Not an OS/2 font resource.')
    # Now set the pointers in our font type to the correct offsets
    pFont = Props()
    pFont.pSignature = OS2FONTSTART.from_bytes(pBuffer)
    ofs = OS2FONTSTART.size
    pFont.pMetrics = OS2FOCAMETRICS.from_bytes(pBuffer, ofs)
    ofs += pFont.pMetrics.ulSize
    pFont.pKerning = None
    pFont.pPanose = None
    pRecord = GENERICRECORD.from_bytes(pBuffer, ofs)
    if pRecord.Identity != SIG_OS2FONTDEF:
        raise FileFormatError('Not an OS/2 font resource')
    pFont.pFontDef = OS2FONTDEFHEADER.from_bytes(pBuffer, ofs)
    if pFont.pMetrics.fsDefn.FM_DEFN_OUTLINE:
        raise FileFormatError('OS/2 outline fonts not supported')
    #
    # read character definitions and bitmaps
    #
    chardef_offset = ofs + OS2FONTDEFHEADER.size
    if pFont.pFontDef.fsChardef == OS2FONTDEF_CHAR3:
        chardeftype = OS2CHARDEF3
    else:
        chardeftype = OS2CHARDEF1
    chardefarray = chardeftype * pFont.pMetrics.usLastChar
    pFont.pChars = chardefarray.from_bytes(pBuffer, chardef_offset)
    if pFont.pFontDef.fsChardef == OS2FONTDEF_CHAR3:
        widths = (_c.bSpace for _c in pFont.pChars)
    else:
        widths = (_c.ulWidth for _c in pFont.pChars)
    usWidths = (ceildiv(_w, 8) for _w in widths)
    cy = pFont.pFontDef.yCellHeight
    pFont.bitmaps = tuple(
        b'' if not _c.ulOffset else pBuffer[_c.ulOffset : _c.ulOffset+_uw*cy]
        for _c, _uw in zip(pFont.pChars, usWidths)
    )
    #
    # read optional tables (kerning, panose)
    #
    ofs += pFont.pFontDef.ulSize
    pRecord = GENERICRECORD.from_bytes(pBuffer, ofs)
    if pFont.pMetrics.usKerningPairs and pRecord.Identity == SIG_OS2KERN:
        pFont.pKerning = OS2KERNPAIRTABLE.from_bytes(pBuffer, ofs)
        # Advance to the next record (whether OS2ADDMETRICS or OS2FONTEND).
        # This is a guess; since the actual format, and thus size, of the
        # kerning information is unclear (see remarks in gpifont.h), there is
        # no guarantee this will work.  Fortunately, we've already parsed the
        # important stuff.
        ofs += (
            OS2KERNPAIRTABLE.size
            + pFont.pMetrics.usKerningPairs * OS2KERNINGPAIRS.size
        )
        pRecord = GENERICRECORD.from_bytes(pBuffer, ofs)
    if pRecord.Identity == SIG_OS2ADDMETRICS:
        pFont.pPanose = OS2ADDMETRICS.from_bytes(pBuffer, ofs)
        ofs += pRecord.ulSize
        pRecord = GENERICRECORD.from_bytes(pBuffer, ofs)
    # We set the pointer to the end signature, but there's really no need to
    # use it for anything.  We check the Identity field to make sure it's
    # valid (if we did miscalculate the kern table size above, then it could
    # well be wrong) before setting the pointer.
    if pRecord.Identity == SIG_OS2FONTEND:
        pFont.pEnd = OS2FONTEND.from_bytes(pBuffer, ofs)
    return pFont


def parse_os2_font_directory(data):
    """
    Parse a font directory resource, return as font directory entries.
    Return an empty tuple if parsing failed.
    """
    logging.debug('Parsing font directory')
    try:
        # If a font directory exists we use that to find the face's
        # resource ID, as in this case it is not guaranteed to have
        # a type of OS2RES_FONTFACE (7).
        fontdir = OS2FONTDIRECTORY.from_bytes(data)
        data = data[OS2FONTDIRECTORY.size:]
        if len(data) >= fontdir.usnFonts * OS2FONTDIRENTRY.size:
            direntry_type = OS2FONTDIRENTRY
        else:
            direntry_type = OS2FONTDIRENTRY_SMALL
        entries = direntry_type.array(fontdir.usnFonts).from_bytes(data)
        return entries
    except ValueError as e:
        logging.debug('Failed to parse font directory: %s', e)
        return ()


def convert_os2_glyphs(font_data):
    """Convert OS/2 glyph definitions and bitmaps to monobit glyphs."""
    glyphs = []
    for codepoint, (chardef, bitmap) in enumerate(
            zip(font_data.pChars, font_data.bitmaps),
            font_data.pMetrics.usFirstChar
        ):
        props = dict(
            codepoint=codepoint,
        )
        if font_data.pFontDef.fsChardef == OS2FONTDEF_CHAR3:
            cx = chardef.bSpace
            props.update(dict(
                left_bearing=chardef.aSpace,
                right_bearing=chardef.cSpace,
            ))
        else:
            cx = chardef.ulWidth
        cy = font_data.pFontDef.yCellHeight
        byte_width = ceildiv(cx, 8)
        # bytewise transpose the bitmap
        # consecutive bytes represent vertical 8-pixel-wide columns
        bitmap = b''.join(
            bitmap[_i::cy]
            for _i in range(cy)
        )
        glyph = Glyph.from_bytes(bitmap, width=cx, **props)
        glyphs.append(glyph)
    return glyphs


_WEIGHT_MAP = {
    0: '',
    1: 'thin',
    2: 'extra-light',
    3: 'light',
    4: 'semi-light',
    5: 'regular',
    6: 'semi-bold',
    7: 'bold',
    8: 'extra-bold',
    9: 'heavy',
}

_SETWIDTH_MAP = {
    0: '',
    1: 'ultra-condensed',
    2: 'extra-condensed',
    3: 'condensed',
    4: 'semi-condensed',
    5: 'medium',
    6: 'semi-expanded',
    7: 'expanded',
    8: 'extra-expanded',
    9: 'ultra-expanded',
}

def convert_os2_properties(font_data):
    """Convert OS/2 font properties to monobit properties."""
    # should we use the information in the fontdefheader?
    metrics = font_data.pMetrics
    # font encoding (850 indicates PMUGL)
    # > usCodePage - This field is the registered code page for which the font was
    # > designed. Often, this field is 0, which means the font can be used with any of
    # > the OS/2 supported code pages. Hence, if this field is 0, you can specify the
    # > code page you want when you create a logical font. (Logical font creation is
    # > discussed later.) When you create a logical font, the font character to code
    # > point mappings will be made for you. If the font contains special symbols
    # > which have no register code page, a value of 65400 is returned in this field.
    # > In this case, you must use the returned code page value during logical font
    # > creation.
    if metrics.usCodePage in (0, 850):
        encoding = 'ibm-ugl'
    elif metrics.usCodePage == 65400:
        encoding = ''
    else:
        encoding = f'ibm-{metrics.usCodePage}'
    # font selection flags
    decoration = []
    if metrics.fsSelectionFlags.FM_SEL_OUTLINE:
        decoration.append('outline')
    if metrics.fsSelectionFlags.FM_SEL_NEGATIVE:
        decoration.append('negative')
    if metrics.fsSelectionFlags.FM_SEL_UNDERSCORE:
        decoration.append('underline')
    if metrics.fsSelectionFlags.FM_SEL_STRIKEOUT:
        decoration.append('strikethrough')
    properties = Props(
        family=metrics.szFamilyname.decode('latin-1'),
        name=metrics.szFacename.decode('latin-1'),
        font_id=metrics.usRegistryId,
        encoding=encoding,
        ascent=metrics.yLowerCaseAscent,
        descent=metrics.yLowerCaseDescent,
        # total cell depth below baseline
        shift_up=-metrics.yMaxDescender,
        line_height=metrics.yMaxBaselineExt + metrics.yExternalLeading,
        dpi=(metrics.xDeviceRes, metrics.yDeviceRes),
        default_char=metrics.usFirstChar + metrics.usDefaultChar,
        word_boundary=metrics.usFirstChar + metrics.usBreakChar,
        point_size=metrics.usNominalPointSize / 10,
        underline_thickness=metrics.yUnderscoreSize,
        underline_descent=metrics.yUnderscorePosition,
        #ySubscriptXSize='int16',
        subscript_size=metrics.ySubscriptYSize,
        subscript_offset=(metrics.ySubscriptXOffset, metrics.ySubscriptYOffset),
        #ySuperscriptXSize='int16',
        superscript_size=metrics.ySuperscriptYSize,
        superscript_offset=(metrics.ySuperscriptXOffset, metrics.ySuperscriptYOffset),
        #also fsSelectionFlags.FL_SEL_BOLD
        weight=_WEIGHT_MAP.get(metrics.usWeightClass, ''),
        setwidth=_SETWIDTH_MAP.get(metrics.usWidthClass, ''),
        slant='italic' if metrics.fsSelectionFlags.FM_SEL_ITALIC else 'roman',
        decoration=' '.join(decoration)
        # # strikeout stroke thickness
        # yStrikeoutSize='int16',
        # # strikeout height above baseline
        # yStrikeoutPosition='int16',
    )
    return properties
