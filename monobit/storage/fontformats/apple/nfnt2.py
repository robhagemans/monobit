"""
monobit.storage.fontformats.apple.nfnt2 - Palm `nfnt` (v2) font resources

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be, little_endian as le
from monobit.core import Font, Glyph, Raster
from monobit.storage import loaders, savers

from monobit.storage.fontformats.apple.nfnt import (
    nfnt_header_struct,
    loc_entry_struct,
    wo_entry_struct,
    convert_nfnt,
)


@loaders.register(
    name='nfnt2',
    magic=(b'\x92\0',),
)
def load_nfnt2(instream, offset:int=0):
    """
    Load font from a bare nfnt (v2) resource.

    offset: starting offset in bytes of the NFNT record in the file (default 0)
    """
    instream.seek(offset)
    fontdata_dicts = extract_nfnt2(instream)
    return tuple(
        convert_nfnt(**_fontdata)
        for _fontdata in fontdata_dicts
    )


# FontTypeV2 struct
# https://palm.wiki/development/docs/601/PalmOSReference/Font.html#1000130
# > fontType:
# > A mask providing the general characteristics of the font. When creating
# > an application-defined extended font resource, use the value
# > fntExtendedFormatMask | 0x9000.
# fntExtendedFormatMask = 0x0200

def nfnt2_header_ext_struct(base):
    return base.Struct(
        # these are defined as (signed) Int16 but that doesn't make much sense
        version='uint16',
        densityCount='uint16',
        # densities=_FONT_DENSITY_TYPE*densityCount
    )

def font_density_type(base):
    return base.Struct(
        # > Either kDensityLow, kDensityOneAndAHalf, or kDensityDouble.
        # https://palm.wiki/development/docs/601/PalmOSReference/Bitmap.html#998172
        # > typedef enum {
        # >  kDensityLow = 72,
        # >  kDensityOneAndAHalf = 108,
        # >  kDensityDouble = 144,
        # >  kDensityTriple = 216,
        # >  kDensityQuadruple = 288
        # > } DensityType
        density='int16',
        # > Offset in bytes from the beginning of the font data to the start of
        # > the font image for this density.
        glyphBitsOffset='uint32',
    )

def extract_nfnt2(instream):
    """Read a Palm OS nfnt (v2) resource."""
    # "from the beginning of the font data"
    anchor = instream.tell()
    fontrec = nfnt_header_struct(be).read_from(instream)
    logging.debug('NFNT header: %s', fontrec)
    fontrecv2 = nfnt2_header_ext_struct(be).read_from(instream)
    logging.debug('nfnt2 header extension: %s', fontrecv2)
    densities = (font_density_type(be) * fontrecv2.densityCount).read_from(instream)
    logging.debug('density records: %s', densities)
    # read char tables & bitmaps
    # location table
    # number of chars: coded chars plus missing symbol
    n_chars = fontrec.lastChar - fontrec.firstChar + 2
    # loc table should have one extra entry to be able to determine widths
    loc_table = loc_entry_struct(be).array(n_chars+1).read_from(instream)
    # width offset table
    wo_table = wo_entry_struct(be).array(n_chars).read_from(instream)
    fontdata = []
    # bitmap strikes
    for density_rec in densities:
        instream.seek(anchor + density_rec.glyphBitsOffset)
        # we can have 1.5x density?
        factor = density_rec.density / 72
        # parse bitmap strike
        # TODO: what about 1.5x density? do we need to round? how?
        n_rows = int(fontrec.fRectHeight * factor)
        bytes_per_row = int(fontrec.rowWords * 2 * factor)
        strike_size = n_rows * bytes_per_row
        strike = instream.read(strike_size)
        bitmap_strike = Raster.from_bytes(strike, stride=8*bytes_per_row)
        # extract width from width/offset table
        # (do we need to consider the width table, if defined?)
        locs = tuple(int(_loc.offset*factor) for _loc in loc_table)
        glyphs = tuple(
            Glyph(bitmap_strike.crop(left=_offs, right=bitmap_strike.width-_next))
            for _offs, _next in zip(locs[:-1], locs[1:])
        )
        # metrics: width & offset
        glyphs = tuple(
            _glyph.modify(
                wo_offset=int(factor*_wo.offset),
                wo_width=int(factor*_wo.width),
            )
            for _glyph, _wo in zip(glyphs, wo_table)
        )
        fontdata.append(dict(
            glyphs=glyphs,
            # FIXME - we need to scale characterictics such as ascent, descent, leading, ...
            fontrec=fontrec,
            properties={
                'source_format': 'nfnt2',
                'dpi': density_rec.density,
            }
        ))
    return fontdata



_AFNX_DENSITY_REC = le.Struct(
    density='int16',
    unknown='uint16',
    glyphBitsOffset='uint32',
)

def extract_afnx(instream):
    """Read a Palm OS afnx resource."""
    anchor = instream.tell()
    fontrec = nfnt_header_struct(le).read_from(instream)
    logging.debug('NFNT header: %s', fontrec)
    fontrecv2 = nfnt2_header_ext_struct(le).read_from(instream)
    logging.debug('nfnt2 header extension: %s', fontrecv2)

    unknown = int(le.uint16.read_from(instream))
    logging.debug('unknown uint16: %d', unknown)
    densities = (_AFNX_DENSITY_REC * fontrecv2.densityCount).read_from(instream)
    logging.debug(densities)

    # read char tables & bitmaps
    # location table
    # number of chars: coded chars plus missing symbol
    n_chars = fontrec.lastChar - fontrec.firstChar + 2
    # offset table should have one extra entry to be able to determine widths
    loc_table = loc_entry_struct(le).array(n_chars+1).read_from(instream)
    logging.debug('location table: %s', loc_table)
    # width offset table
    wo_table = wo_entry_struct(le).array(n_chars).read_from(instream)
    logging.debug('width-extent table: %s', wo_table)


    fontdata = []
    # bitmap strikes
    for density_rec in densities:
        instream.seek(anchor + density_rec.glyphBitsOffset)
        # we can have 1.5x density?
        factor = density_rec.density / 72
        # parse bitmap strike
        # TODO: what about 1.5x density? do we need to round? how?
        n_rows = int(fontrec.fRectHeight * factor)
        bytes_per_row = int(fontrec.rowWords * 2 * factor)
        strike_size = n_rows * bytes_per_row
        strike = instream.read(strike_size)
        bitmap_strike = Raster.from_bytes(strike, stride=8*bytes_per_row)
        # extract width from width/offset table
        # (do we need to consider the width table, if defined?)
        locs = tuple(int(_loc.offset*factor) for _loc in loc_table)
        glyphs = tuple(
            Glyph(bitmap_strike.crop(left=_offs, right=bitmap_strike.width-_next))
            for _offs, _next in zip(locs[:-1], locs[1:])
        )
        # metrics: width & offset
        glyphs = tuple(
            _glyph.modify(
                wo_offset=int(factor*_wo.offset),
                wo_width=int(factor*_wo.width),
            )
            for _glyph, _wo in zip(glyphs, wo_table)
        )
        fontdata.append(dict(
            glyphs=glyphs,
            # FIXME - we need to scale characterictics such as ascent, descent, leading, ...
            fontrec=fontrec,
            properties={
                'source_format': 'afnx',
                'dpi': density_rec.density,
            }
        ))
    return fontdata
