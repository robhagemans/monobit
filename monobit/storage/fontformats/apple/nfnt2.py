"""
monobit.storage.fontformats.apple.nfnt2 - Palm `nfnt` (v2) font resources

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.struct import big_endian as be, little_endian as le
from monobit.base import Props, UnsupportedError
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
    Load font from a bare Palm nfnt (v2) resource.

    offset: starting offset in bytes of the NFNT record in the file (default 0)
    """
    instream.seek(offset)
    fontdata_dicts = extract_nfnt2(instream, format='nfnt2')
    return tuple(
        convert_nfnt(**_fontdata)
        for _fontdata in fontdata_dicts
    )


@loaders.register(
    name='afnx',
    magic=(b'\0\x92',),
)
def load_afnx(instream, offset:int=0):
    """
    Load font from a bare Palm afnx resource.

    offset: starting offset in bytes of the NFNT record in the file (default 0)
    """
    instream.seek(offset)
    fontdata_dicts = extract_nfnt2(instream, format='afnx')
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

def font_density_type_afnx(base):
    # afnx has an extra word in the middle of the density struct, purpose unknown.
    return base.Struct(
        density='int16',
        unknown='uint16',
        glyphBitsOffset='uint32',
    )


def extract_nfnt2(instream, format='nfnt2'):
    """Read a Palm OS nfnt (v2) or afnx resource."""
    if format == 'nfnt2':
        base = be
        density_type = font_density_type(base)
    elif format == 'afnx':
        base = le
        density_type = font_density_type_afnx(base)
    else:
        raise ValueError(
            f"`format` must be one of 'nfnt2', 'afnx', not '{format}'"
        )
    # "from the beginning of the font data"
    anchor = instream.tell()
    fontrec = nfnt_header_struct(base).read_from(instream)
    logging.debug('NFNT header: %s', fontrec)
    fontrecv2 = nfnt2_header_ext_struct(base).read_from(instream)
    logging.debug('nfnt2 header extension: %s', fontrecv2)
    # afnx has an additional word here, generally 0; purpose unknown
    if format == 'afnx':
        unknown = int(le.uint16.read_from(instream))
        logging.debug('unknown uint16: %d', unknown)
    densities = (density_type * fontrecv2.densityCount).read_from(instream)
    logging.debug('density records: %s', densities)
    # read char tables & bitmaps
    # location table
    # number of chars: coded chars plus missing symbol
    n_chars = fontrec.lastChar - fontrec.firstChar + 2
    # loc table should have one extra entry to be able to determine widths
    loc_table = loc_entry_struct(base).array(n_chars+1).read_from(instream)
    # width offset table
    wo_table = wo_entry_struct(base).array(n_chars).read_from(instream)
    fontdata = []
    # bitmap strikes
    for density_rec in densities:
        instream.seek(anchor + density_rec.glyphBitsOffset)
        factor = density_rec.density / 72
        # in theory, we can have 1.5x density
        # but: rounding not defined; no known samples; not supported
        if factor != int(factor):
            raise UnsupportedError(
                f'Non-integer {factor}x density multiple mot supported'
            )
        factor = int(factor)
        # parse bitmap strike
        n_rows = fontrec.fRectHeight * factor
        bytes_per_row = fontrec.rowWords * 2 * factor
        strike_size = n_rows * bytes_per_row
        strike = instream.read(strike_size)
        bitmap_strike = Raster.from_bytes(strike, stride=8*bytes_per_row)
        # extract width from width/offset table
        # (do we need to consider the width table, if defined?)
        locs = tuple(_loc.offset*factor for _loc in loc_table)
        glyphs = tuple(
            Glyph(bitmap_strike.crop(left=_offs, right=bitmap_strike.width-_next))
            for _offs, _next in zip(locs[:-1], locs[1:])
        )
        # metrics: width & offset
        glyphs = tuple(
            _glyph.modify(
                wo_offset=factor*_wo.offset,
                wo_width=factor*_wo.width,
            )
            for _glyph, _wo in zip(glyphs, wo_table)
        )
        fontdata.append(dict(
            glyphs=glyphs,
            # FIXME - we need to scale characterictics such as ascent, descent, leading, ...
            fontrec=fontrec,
            properties={
                'source_format': format,
                'dpi': density_rec.density,
            }
        ))
    return fontdata
