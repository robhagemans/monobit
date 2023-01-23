"""
monobit.formats.os2 - read OS/2 bitmap fonts and LX containers

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT


this implementation leans heavily on os2font_src/gpifont.c
- http://www.altsan.org/programming/os2font_src.zip
- https://github.com/altsan/os2-gpi-font-tools

notice for gpifont.c:
>
>  (C) 2012 Alexander Taylor
>
>  This code is placed in the public domain.
>
"""

import logging

from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..properties import Props
from ..struct import little_endian as le
from ..binary import ceildiv


@loaders.register(
    #'fon',
    name='os2',
)
def load_os2(
        instream, where=None,
    ):
    """Load an OS/2 font file."""
    resources = _read_os2_font(instream)
    parsed = (
        _parse_os2_font_resource(_data)
        for _data in resources
    )
    # TODO: convert font metrics
    fonts = tuple(
        Font(_convert_os2_glyphs(_pfont))
        for _pfont in parsed
    )
    return fonts


# from os2res.h

# 0x5A4D "MZ": DOS/old-style executable header
MAGIC_MZ = b'MZ'
# 0x454E "NE": 16-bit OS/2 executable header
MAGIC_NE = b'NE'
# 0x584C "LX": 32-bit OS/2 executable header
MAGIC_LX = b'LX'

# Location of the 'real' exe header offset
EH_OFFSET_ADDRESS = 0x3C

# OS/2 resource types that we're interested in.
OS2RES_FONTDIR = 6
OS2RES_FONTFACE = 7

# Values of interest for flags field of LXOPMENTRY (LX object page map entry).
# Normal unpacked data
OP32_VALID = 0x0000
# Data in EXEPACK1 format
OP32_ITERDATA = 0x0001
# Data in EXEPACK2 format
OP32_ITERDATA2 = 0x0005


# based on ReadOS2FontResource from gpifont.c
def _read_os2_font(instream):
    """Read an OS/2 .FON file."""
    magic = instream.read(2)
    if magic == MAGIC_MZ:
        # Locate the new-type executable header
        instream.seek(EH_OFFSET_ADDRESS)
        addr = int(le.uint32.read_from(instream))
        # Read the 2-byte magic number from this address
        instream.seek(addr)
        magic = instream.read(2)
        # Now back up to the start of the new-type header again
        instream.seek(addr)
    elif magic in (MAGIC_LX, MAGIC_NE):
        # No stub header, just start at the beginning of the file
        addr = 0;
        instream.seek(addr)
    else:
        # Not a compiled (exe) font module
        raise FileFormatError('Not an OS/2 FON file.')
    # Identify the executable type and parse the resource data accordingly
    if magic == MAGIC_LX:
        return _read_lx(instream)
    else:
        # plug in ne reader from Windows here, allowing for an OS/2 font resource
        raise NotImplementedError()


# 32-bit EXE header
LXHEADER = le.Struct(
    # 0x4C58 ("LX")
    magic='2s',
    # various unnecessary fields
    unused1=le.uint8.array(42),
    # page alignment shift
    pageshift='uint32',
    # various unnecessary fields
    unused2=le.uint8.array(8),
    # loader section size
    ldrsize='uint32',
    # loader section checksum
    ldrsum='uint32',
    # offset to object table
    obj_tbl='uint32',
    # various unnecessary fields
    unused3=le.uint8.array(4),
    # offset to object page map
    objmap='uint32',
    # various unnecessary fields
    unused4=le.uint8.array(4),
    # offset to resource table
    res_tbl='uint32',
    # number of resource entries
    cres='uint32',
    # offset to resident-names table
    rnam_tbl='uint32',
    # various unnecessary fields
    unused5=le.uint8.array(36),
    # offset to data pages
    datapage='uint32',
    # 64 bytes of various unnecessary fields follow
)

# Resource table entry
LXRTENTRY = le.Struct(
    type='uint16',
    name='uint16',
    cb='uint32',
    obj='uint16',
    offset='uint32',
)

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
    fsTypeFlags='uint16',
    # font definition flags
    fsDefn='uint16',
    # font selection flags
    fsSelectionFlags='uint16',
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

def _read_lx(instream):
    """Read font resources from an LX container."""
    resources = []
    ulAddr = instream.tell()
    lx_hd = LXHEADER.read_from(instream)
    # Make sure the file actually contains resources...
    if not lx_hd.cres:
        raise FileFormatError('No resources found in LX file.')
    # Now look for font resources
    cb_rte = LXRTENTRY.size
    ulResID = ()
    for i in range(lx_hd.cres):
        cbInc = cb_rte * i
        instream.seek(ulAddr + lx_hd.res_tbl + cbInc)
        lx_rte = LXRTENTRY.read_from(instream)
        logging.debug(
            'Found resource of type %d with id %d',
            lx_rte.type, lx_rte.name
        )
        # don't insist on the type being 7 if the id matches the font directory
        if (
                lx_rte.type not in (OS2RES_FONTFACE, OS2RES_FONTDIR)
                and lx_rte.name not in ulResID
            ):
            continue
        # This is either our target font, or else a font directory
        pBuf = _lx_extract_resource(instream, lx_hd, lx_rte, ulAddr)
        if lx_rte.type == OS2RES_FONTDIR:
            # If a font directory exists we use that to find the face's
            # resource ID, as in this case it is not guaranteed to have
            # a type of OS2RES_FONTFACE (7).
            pFD = OS2FONTDIRECTORY.from_bytes(pBuf, lx_rte.offset)
            ulFaceCount = pFD.usnFonts
            fntEntry = OS2FONTDIRENTRY.array(ulFaceCount).from_bytes(
                pBuf, lx_rte.offset + OS2FONTDIRECTORY.size
            )
            # Set ulResID to the ID of the requested font number, then
            # continue scanning the resource table.
            ulResID = tuple(_fe.usIndex for _fe in fntEntry)
        else:
            # pBuf contains our font, so parse it.
            resources.append(pBuf)
    return resources


# Object table entry
LXOTENTRY = le.Struct(
    size='uint32',
    base='uint32',
    flags='uint32',
    pagemap='uint32',
    mapsize='uint32',
    reserved='uint32',
)

# Object page-map entry
LXOPMENTRY = le.Struct(
    dataoffset='uint32',
    size='uint16',
    flags='uint16',
)

def _lx_extract_resource(instream, lx_hd, lx_rte, ulBase):
    """
    Extracts a binary resource from an LX-format (32-bit OS/2) module.  The
    function takes a pointer to a buffer which will receive the extracted
    data of the object containing the resource.  It is up to the caller to
    locate the actual resource data within this buffer (this should be
    lx_rte.offset bytes from the start of the buffer).  The buffer is
    allocated by this function on successful return, and must be freed once
    no longer needed.

    This routine is based on information made available by Martin Lafaix,
    Veit Kannegieser and Max Alekseyev.

    ARGUMENTS:
      FILE      *pf      : Pointer to the open file.                      (I)
      LXHEADER   lx_hd   : LX-format executable header                    (I)
      LXRTENTRY  lx_rte  : Resource-table entry of the requested resource (I)
      ULONG      ulBase  : File offset of the LX-format header            (I)
    """
    cb_obj = LXOTENTRY.size
    cb_pme = LXOPMENTRY.size
    # Locate & read the object table entry for this resource
    instream.seek(ulBase + lx_hd.obj_tbl + cb_obj * (lx_rte.obj-1))
    lx_obj = LXOTENTRY.read_from(instream)
    # Locate & read the object page table entries for this object
    cbData = 0
    # - go to the first indicated entry in the pagemap
    instream.seek(ulBase + lx_hd.objmap + cb_pme * (lx_obj.pagemap-1))
    # - read the indicated number of pages from this point
    plxpages = []
    for _ in range(lx_obj.mapsize):
        lx_opm = LXOPMENTRY.read_from(instream)
        if lx_opm.flags in (OP32_ITERDATA, OP32_ITERDATA2):
            cbData += 4096
        else:
            cbData += lx_opm.size
        plxpages.append(lx_opm)
    if cbData >= lx_rte.offset + lx_rte.cb - 1:
        # Now read each page from its indicated location into our buffer
        pBuf = bytearray()
        for plxpage in plxpages:
            cbPageAddr = lx_hd.datapage + (plxpage.dataoffset << lx_hd.pageshift)
            instream.seek(cbPageAddr)
            data = instream.read(plxpage.size)
            if plxpage.flags == OP32_ITERDATA:
                pBuf.extend(_lx_unpack1(data))
            elif plxpage.flags == OP32_ITERDATA2:
                pBuf.extend(_lx_unpack2(data))
            elif plxpage.flags == OP32_VALID:
                pBuf.extend(data)
            else:
                continue
    return bytes(pBuf)

def _lx_unpack1(pBuf):
    """
    Unpacks a (max 4096-byte) page which has been compressed using the OS/2
    /EXEPACK1 method (a simple form of run-length encoding).

    This algorithm was derived from public-domain Pascal code by Veit
    Kannegieser (based on previous work by Max Alekseyev).
    """
    cbPage = len(pBuf)
    if cbPage > 4096:
        return pBuf
    ofIn  = 0;
    abOut = bytearray()
    while True:
        usReps = pBuf[ofIn] | (pBuf[ofIn+1] << 8)
        if not usReps:
            break
        ofIn += 2
        usLen = pBuf[ofIn] | (pBuf[ofIn+1] << 8)
        ofIn += 2
        if ofOut + usReps * usLen > 4096:
            break
        while usReps:
            abOut.extend(pBuf[ofIn:ofIn+usLen])
            usReps -= 1
        ofIn += usLen
        if ofIn > cbPage:
            break
    return bytes(abOut)


def _lx_unpack2(pBuf):
    """
    Unpacks a (max 4096-byte) page which has been compressed using the OS/2
    /EXEPACK2 method (which is apparently a modified Lempel-Ziv algorithm).

    This algorithm was derived from public-domain Pascal-and-x86-assembly
    code by Veit Kannegieser (based on previous work by Max Alekseyev).
    """
    cbPage = len(pBuf)
    if cbPage > 4096:
        return pBuf
    ofIn  = 0
    abOut = bytearray()
    while True:
        ulControl = int(le.uint16.from_bytes(pBuf, ofIn))
        # Bits 1 & 0 hold the case flag (0-3); the interpretation of the
        # remaining bits depend on the flag value.
        case_flag = ulControl & 0x3
        if case_flag == 0:
            # bits 15..8  = length2
            # bits  7..2  = length1
            if ulControl & 0xff == 0:
                # When length1 == 0, fill (length2) bytes with the byte
                # value following ulControl; if length2 is 0 we're done.
                ulLen = ulControl >> 8
                if not ulLen:
                    break
                # memset( abOut + ofOut, *(pBuf + ofIn + 2), ulLen );
                abOut.extend([pBuf[ofIn + 2]] * ulLen)
                ofIn += 3
            else:
                # block copy (length1) bytes from after ulControl
                ulLen = (ulControl & 0xff) >> 2
                # memcpy( abOut + ofOut, pBuf + ofIn + 1, ulLen );
                abOut.extend(pBuf[ofIn+1:ofIn+1+ulLen])
                ofIn  += ulLen + 1
        elif case_flag == 1:
            # bits 15..7     = backwards reference
            # bits  6..4  +3 = length2
            # bits  3..2     = length1
            # copy length1 bytes following ulControl
            ulLen = (ulControl >> 2) & 0x3;
            # memcpy( abOut + ofOut, pBuf + ofIn + 2, ulLen );
            abOut.extend(pBuf[ofIn+2:ofIn+2+ulLen])
            ofIn += ulLen + 2
            # get length2 from what's been unpacked already
            ulLen = (( ulControl >> 4 ) & 0x7 ) + 3
            _copy_byte_seq(abOut, -((ulControl >> 7) & 0x1FF), ulLen)
        elif case_flag == 2:
            # bits 15.. 4     = backwards reference
            # bits  3.. 2  +3 = length
            ulLen = (( ulControl >> 2 ) & 0x3 ) + 3
            _copy_byte_seq(abOut, -((ulControl >> 4) & 0xFFF), ulLen)
            ofIn  += 2
        elif case_flag == 3:
            ulControl = int(le.uint32.from_bytes(pBuf, ofIn))
            # bits 23..21  = ?
            # bits 20..12  = backwards reference
            # bits 11.. 6  = length2
            # bits  5.. 2  = length1
            # block copy (length1) bytes
            ulLen = (ulControl >> 2) & 0xF
            # memcpy( abOut + ofOut, pBuf + ofIn + 3, ulLen );
            abOut.extend(pBuf[ofIn+3 : ofIn+3+ulLen])
            ofIn  += ulLen + 3
            # copy (length2) bytes from previously-unpacked data
            ulLen = (ulControl >> 6) & 0x3F
            _copy_byte_seq(abOut, -((ulControl >> 12) & 0xFFF), ulLen)
        if ofIn >= cbPage:
            break
    # It seems that the unpacked data will always be 4096 bytes, except for
    # the final page (which will be taken care of when the caller uses the
    # total object length to read the concatenated buffer).
    return bytes(abOut)


def _copy_byte_seq(target, source_offset, count):
    """
    Perform a byte-over-byte iterative copy from one byte array into another,
    or from one point to another within the same array.  Used by LXUnpack2().
    Note that memcpy() does not work for this purpose, because the source and
    target address spaces could overlap - that is, the end of the source
    sequence could extend into the start of the target sequence, thus copying
    bytes that were previously written by the same call to this function.
    """
    for _ in range(count):
        target.append(target[source_offset])


###############################################################################
# font resource parser

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


def _parse_os2_font_resource(pBuffer):
    """
    Parses a standard GPI-format OS/2 font resource.  Takes as input an
    already-populated memory buffer containing the raw font resource data.
    On successful return, the fields within the OS2FONTRESOURCE structure
    will point to the appropriate structures within the font file data.

    NOTE: Even if this function returns success, the pPanose and pEnd fields
    of the pFont structure may be NULL.  The application must check for this
    if it intends to use these fields.
    """
    pFont = Props()
    # Verify the file format
    pRecord = GENERICRECORD.from_bytes(pBuffer)
    if (
            pRecord.Identity != SIG_OS2FONTSTART
            or pRecord.ulSize != OS2FONTSTART.size
        ):
        raise FileFormatError('Not an OS/2 font resource.')
    # Now set the pointers in our font type to the correct offsets
    pFont.pSignature = OS2FONTSTART.from_bytes(pBuffer)
    ofs = OS2FONTSTART.size
    pFont.pMetrics = OS2FOCAMETRICS.from_bytes(pBuffer, ofs)
    ofs += pFont.pMetrics.ulSize
    pFont.pKerning = None
    pFont.pPanose = None
    pRecord = GENERICRECORD.from_bytes(pBuffer, ofs)
    if pRecord.Identity != SIG_OS2FONTDEF:
        raise FileFormatError('Not an OS/2 font resource.')
    pFont.pFontDef = OS2FONTDEFHEADER.from_bytes(pBuffer, ofs)

    logging.debug(pFont.pFontDef)

    chardef_offset = ofs + OS2FONTDEFHEADER.size
    if pFont.pFontDef.fsChardef == OS2FONTDEF_CHAR3:
        chardeftype = OS2CHARDEF3
        cx = 'bSpace'
    else:
        chardeftype = OS2CHARDEF1
        cx = 'ulWidth'

    cy = pFont.pFontDef.yCellHeight

    pFont.pChars = (chardeftype * pFont.pMetrics.usLastChar).from_bytes(pBuffer, chardef_offset)
    if pFont.pFontDef.fsChardef == OS2FONTDEF_CHAR3:
        widths = (_c.bSpace for _c in pFont.pChars)
    else:
        widths = (_c.ulWidth for _c in pFont.pChars)
    usWidths = (ceildiv(_w, 8) for _w in widths)

    pFont.bitmaps = tuple(
        '' if not _c.ulOffset else pBuffer[_c.ulOffset : _c.ulOffset+_uw*cy]
        for _c, _uw in zip(pFont.pChars, usWidths)
    )
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


def _convert_os2_glyphs(pFont):
    """Convert glyph definitions and bitmaps to monobit glyphs."""
    glyphs = []
    for pChar, pBitmap in zip(pFont.pChars, pFont.bitmaps):
        # Find the character data for the given offset
        if pFont.pFontDef.fsChardef == OS2FONTDEF_CHAR3:
            cx = pChar.bSpace
            props = dict(
                left_bearing=pChar.aSpace,
                right_bearing=pChar.cSpace,
            )
        else:
            cx = pChar.ulWidth
            props = {}
        cy = pFont.pFontDef.yCellHeight
        usWidth = ceildiv(cx, 8)
        # consecutive bytes represent vertical 8-pixel-wide columns
        bitmap = tuple(
            pBitmap[i + (cy * j)]
            for i in range(cy)
            for j in range(usWidth)
        )
        glyph = Glyph.from_bytes(bitmap, width=cx, **props)
        glyphs.append(glyph)
    return glyphs
