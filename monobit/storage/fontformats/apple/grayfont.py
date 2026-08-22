"""
monobit.storage.fontformats.apple.grayfont - Palm GrayFont font resources

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be, little_endian as le, bitfield
from monobit.base import Props, UnsupportedError
from monobit.core import Font, Glyph, Raster
from monobit.storage import loaders, savers


# GrFn resource
# =============

# see GrayFormat.txt in the FontConv for Palm OS source tree
# https://sourceforge.net/projects/palmfontconv/files/Font%20Converters%20for%20PalmOS%20Dev/1.63/FontConvForPalmOS163full.zip/download

def gray_font_type_struct(base):
    return base.Struct(
        # > The fontVersion is currently 0x0002.
        # I've seen 0x0003 and 0x0004, those will need to be reverse engineered
        fontVersion='uint16',
        firstChar='uint16',
        lastChar='uint16',
        # > maximum advance value for a glyph.
        fRectWidth='uint16',
        # fRectHeight: pixel height of font.
        fRectHeight='uint16',
        # > length of ascender part of font
        ascent='int16',
        # > length of descender part of font
        descent='int16',
        # > pixels of line spacing
        leading='int16',
        # > the number of GXYZ resources of any given XYZ type needed for
        # > the font's glyphs.  If a font has multiple types of GXYZ
        # > resources, e.g., both GU24 and GU34 resources, the number
        # > of resources for both types must be the same, and must be equal
        # > to numberOfBitmapResources.  A small font will have only
        # > one resource, but Palm limits will force larger ones to have
        # > their glyphs split between multiple GXYZ resources.
        numberOfBitmapResources='uint16',
        # > byte offset from beginning of GrayScaleFontType header to
        # > a table of type GrayFontBitmapsInfo[] of length
        # > numberOfBitmapResources.
        bitmapResourceTableOffset='uint16',
        # > byte offset from begining of GrayScaleFontType header to a
        # > table of type GrayFontGlyphInfo[] of length lastChar-firstChar+1.
        glyphInfoTableOffset='uint16',
        # the following entries are
        # > not included in version 0x0001 fonts, should be taken as zero from such fonts
        #
        # > Negative or zero integer indicating the smallest value of
        # > leftKerning in the font.
        minLeftKerning='int16',
        # > Maximum value of bitmapWidth + leftKerning - advance.
        maxRightOverhang='int16',
        reserved=be.uint16*4,
    )



# > The GrayFontBitmapsInfo[] and GrayFontGlyphInfo[] tables can follow in any order
# > anywhere in the GrFn resource, aligned on an address divisible by four.

def gray_font_bitmaps_info_struct(base):
    return base.Struct(
        # > first glyph found in resource
        firstGlyph='uint16',
        # > last glyph found in resource
        lastGlyph='uint16',
        # > the ID of the resource
        resourceID='uint16',
        # > should be zero for now
        reserved='uint16',
    )

def gray_font_glyph_info_struct(base):
    return base.Struct(
        # > This is glyph number glyphNumber.  The numbers must be sequential, but
        # > skipping is permitted.   The bitmap has width bitmapWidth.  If the cursor
        # > position is x before the character is drawn, the renderer draws a bitmap of
        # > width bitmapWidth at x + leftKerning.  It then moves the cursor position to x +
        # > advance.  leftKerning can be zero or negative.  advance must not exceed
        # > bitmapWidth + leftKerning.
        leftKerning='int16',
        advance='int16',
        bitmapWidth='uint16',
        # > the sequential number in the GrayFontBitmapsInfo[] table of the GXYZ resource in
        # > which the bitmap is to be found, ranging from 1 to numberOfBitmapResources:
        # > one needs to look in GrayFontBitmapsInfo[ resourceNumber - 1 ] then.
        # > A zero indicates a missing glyph.
        resourceNumber='uint16',
        # > the index of the bitmap in the GrayFontResourceIndexEntry[] table at the
        # > beginning of the GXYZ resource.
        positionInResourceIndex='uint16',
        # > should be zero for now
        reserved='uint16',
    )


def extract_grayfont(instream, endian):
    """Read a Palm OS GrFn resource."""
    base = {'b': be, 'l': le}[endian[:1].lower()]
    anchor = instream.tell()
    header = gray_font_type_struct(base).read_from(instream)
    instream.seek(anchor + header.bitmapResourceTableOffset)
    bitmap_res_table = gray_font_bitmaps_info_struct(base).array(
        header.numberOfBitmapResources
    ).read_from(instream)
    instream.seek(anchor + header.glyphInfoTableOffset)
    glyph_info_table = gray_font_glyph_info_struct(base).array(
        header.lastChar - header.firstChar + 1
    ).read_from(instream)
    return Props(
        header=header,
        bitmaps_info=bitmap_res_table,
        glyph_info=glyph_info_table,
    )


###############################################################################

# GXYZ resource
# =============
#
# > Bitmaps are stored in resources labeled:
# >     GXYZ
# > Where:
# > X can take the values:
# >     U: upright
# >     L: 90 degrees left (counterclockwise)
# >     R: 90 degrees right.
# > Y indicates the version number of the bitmap, currently either 1 or 3.
# > Z indicates the bit-depth of the bitmaps, currently only 4 being supported.


# > [...] the GXYZ resources start with a table of entries for the glyphs
# > found in the resource, plus one.  Each entry is of type:

def gray_font_resource_index_entry(base):
    return base.Struct(
        # > byte offset from the start of the resource to the bitmap.
        # > The offset must be 32-bit aligned.
        offset='uint16',
        # > length of bitmap.
        length='uint16',
    )

# > The entries should be in order of glyph number, with missing glyphs being
# > filled in with zero offset and zero length.
#
# > And finally come the bitmaps in the GXYZ resource, each 32-bit aligned.
# > These are standard Palm version 1 or 3 bitmaps, with no transparency,
# > no color map, with optional scanline compression (no other compression types
# > are legal).

def bitmap_flags_type(base):
    return base.Struct(
        compressed=bitfield('uint16', 1),
        hasColorTable=bitfield('uint16', 1),
        hasTransparency=bitfield('uint16', 1),
        indirect=bitfield('uint16', 1),
        forScreen=bitfield('uint16', 1),
        directColor=bitfield('uint16', 1),
        indirectColorTable=bitfield('uint16', 1),
        noDither=bitfield('uint16', 1),
        reserved=bitfield('uint16', 8),
    )


def bitmap_type_common_struct(base):
    return base.Struct(
        width='int16',
        height='int16',
        rowBytes='uint16',
        flags=bitmap_flags_type(base),
        pixelSize='uint8',
        version='uint8',
    )

def bitmap_type_v1_ext_struct(base):
    return base.Struct(
        nextDepthOffset='uint16',
        reserved=base.uint16 * 2,
    )


def bitmap_type_v3_ext_struct(base):
    return base.Struct(
        size='uint8',
        pixelFormat='uint8',
        unused='uint8',
        compressionType='uint8',
        density='uint16',
        transparentValue='uint32',
        nextBitmapOffset='uint32',
    )


def read_decompress_scanline(instream, header, base):
    """Decode scanline compression."""
    # see NetPBM source, palmtopnm.c
    # https://sourceforge.net/p/netpbm/code/HEAD/tree/super_stable/converter/other/pnmtopalm/palmtopnm.c
    # > By Bryan Henderson, San Jose, California, June 2004.
    # > Bryan's work is contributed to the public domain by its author.
    if header.version >= 3:
        compressed_size = int(base.uint32.read_from(instream))
    else:
        compressed_size = int(base.uint16.read_from(instream))
    # from readSccanlineRow()
    strike = []
    for row in range(header.height):
        strikerow = []
        for j in range(0, header.rowBytes, 8):
            diffmask = ord(instream.read(1))
            byte_count = min(header.rowBytes - j, 8)
            for k in range(byte_count):
                if (row == 0) or (diffmask & (1 << (7 - k)) != 0):
                    strikerow.append(ord(instream.read(1)))
                else:
                    strikerow.append(strike[-1][j+k])
        strike.append(bytes(strikerow))
    return b''.join(strike)


def extract_gxyz(instream):
    """Read a Palm OS GXYZ resource."""
    anchor = instream.tell()
    magic = instream.peek(2)[:2]
    # determine endianness - this is a poor heuristic as the "magic" is an offset
    if magic[0] > 3:
        base = le
    else:
        base = be
    # there's no number of glyphs given, so keep reading
    # until we hit the first bitmap offset
    first_bitmap = int(base.uint16.from_bytes(magic))
    GrayFontResourceIndexEntry = gray_font_resource_index_entry(base)
    n_entries = first_bitmap // GrayFontResourceIndexEntry.size
    entries = (GrayFontResourceIndexEntry * n_entries).read_from(instream)
    rasters = []
    for i, entry in enumerate(entries):
        instream.seek(anchor + entry.offset)
        header = bitmap_type_common_struct(base).read_from(instream)
        logging.debug(header)
        if header.version == 1:
            ext = bitmap_type_v1_ext_struct(base).read_from(instream)
        elif header.version == 3:
            ext = bitmap_type_v3_ext_struct(base).read_from(instream)
        else:
            logging.error(
                'Only Palm OS bitmap versions 1 and 3 are supported'
                f', not {header.version}'
            )
            continue
        logging.debug(ext)
        if header.flags.compressed:
            # only scanline compression is allowed
            strike = read_decompress_scanline(instream, header, base)
        else:
            strike = instream.read(header.rowBytes * header.height)
        raster = Raster.from_bytes(
            # we can't rely on width as the stride isn't width * bitsperpixel (and rowbytes includes the mask ?)
            # so rely on height instead
            strike, height=header.height, bits_per_pixel=header.pixelSize or 1
        )
        rasters.append(raster)
    return rasters


def convert_grayfont(grfn, records):
    """Combine resources for Grayfonts referenced in one GrFn resource."""
    types = (_rec.type for _rec in records.values())
    gxyz_types = set(
        _type for _type in types
        if _type[:2] in ('GU', 'GL', 'GR') and _type[2:] in ('14', '34')
    )
    fonts = []
    # extract the given glyphs from each type of strike available
    for gxyz_type in gxyz_types:
        glyphs = []
        for cp, glyph_info in enumerate(grfn.data.glyph_info):
            try:
                bm_info = grfn.data.bitmaps_info[glyph_info.resourceNumber-1]
                gxyz = records[(gxyz_type, bm_info.resourceID)]
                glyphs.append(
                    Glyph(
                        gxyz.data[glyph_info.positionInResourceIndex],
                        # TODO metrics
                        codepoint=cp,
                    )
                )
            except (KeyError, IndexError):
                logging.warning('Could not find %s-strike for glyph %d', gxyz_type, cp)
        # TODO font metrics & metadata
        fonts.append(Font(glyphs, source_format=f'grayfont ({gxyz_type})'))
    return fonts
