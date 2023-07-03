"""
monobit.formats.mac.iigs - Apple IIgs font file

(c) 2023 Kelvin Sherlock
licence: https://opensource.org/licenses/MIT

modifications (c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging

from ...binary import bytes_to_bits, align
from ...struct import bitfield, little_endian as le
from ... import struct
from ...storage import loaders, savers
from ...font import Font, Coord
from ...glyph import Glyph, KernTable
from ...magic import FileFormatError

from .nfnt import convert_nfnt, extract_nfnt, create_nfnt
from .dfont import NON_ROMAN_NAMES


# IIgs font file is essentially a little-endian MacOS FONT resource,
# without the resource, plus an extra header.
# Documented in the Apple IIgs Toolbox Reference Volume II, chapter 16-41
# https://archive.org/details/AppleIIGSToolboxReferenceVolume2/


# font style:
_STYLE_TYPE = le.Struct(
    # bit 0 = bold
    bold=bitfield('uint16', 1),
    # bit 1 = italic
    italic=bitfield('uint16', 1),
    # bit 2 = underline
    underline=bitfield('uint16', 1),
    # bit 3 = outline
    outline=bitfield('uint16', 1),
    # bit 4 = shadow
    shadow=bitfield('uint16', 1),
)

_IIGS_HEADER = le.Struct(
    offset='uint16',
    family='uint16',
    style=_STYLE_TYPE,
    pointSize='uint16',
    version='uint16',
    fbrExtent='uint16',
)

# the extended header is defined in Apple IIgs Toolbox Reference Volume III, ch. 43-5
# https://archive.org/details/Apple_IIGS_Toolbox_Reference_vol_3/page/n459/
_EXTENDED_HEADER = le.Struct(
    #   {high bits of owTLoc -- optional }
    owTLocHigh='uint16',
)


def _load_iigs(instream):
    """Load a IIgs font."""
    data = instream.read()
    # p-string name
    offset = data[0] + 1
    name = data[1:offset].decode('mac-roman')
    header = _IIGS_HEADER.from_bytes(data, offset)
    logging.debug('IIgs header: %s', header)
    # offset given in 16-bit words
    extra = data[offset+_IIGS_HEADER.size : offset + header.offset*2]
    offset += header.offset * 2
    # extended header for IIgs
    if header.version >= 0x0105: #  and len(extra) >= 2:
        eh = _EXTENDED_HEADER.from_bytes(extra)
        logging.debug('extended header: %s', eh)
    else:
        eh = _EXTENDED_HEADER()
    # read IIgs-style NFNT resource
    fontdata = extract_nfnt(
        data, offset, endian='little',
        owt_loc_high=eh.owTLocHigh, font_type=b'\0\0'
    )
    return _convert_iigs(**fontdata, header=header, name=name)


def _convert_iigs(glyphs, fontrec, header, name):
    """Convert IIgs font data to monobit font."""
    font = convert_nfnt({}, glyphs, fontrec)
    # properties from IIgs header
    properties = {
        'family': name,
        'point_size': header.pointSize,
        'source_format': 'IIgs v{}.{}'.format(*divmod(header.version, 256)),
        'iigs.family_id': header.family,
    }
    if name not in NON_ROMAN_NAMES:
        properties['encoding'] = 'mac-roman'
    # decode style field
    if header.style.bold:
        properties['weight'] = 'bold'
    if header.style.italic:
        properties['slant'] = 'italic'
    decoration = []
    if header.style.underline:
        decoration.append('underline')
    if header.style.outline:
        decoration.append('outline')
    if header.style.shadow:
        decoration.append('shadow')
    properties['decoration'] = ' '.join(decoration);
    return font.modify(**properties).label()


def _save_iigs(outstream, font, version=None):
    """Save an Apple IIgs font file."""
    nfnt, owt_loc_high, fbr_extent = create_nfnt(
        font, endian='little', ndescent_is_high=False,
        create_width_table=False, create_height_table=False,
    )
    # if offset > 32 bits, need to use iigs format v1.05
    if version is None:
        if owt_loc_high:
            version = 0x0105
        else:
            version = 0x0101
    # generate IIgs header
    # note that this only includes font metadata
    # so no need for the subsetted font that NFNT stored
    header = _IIGS_HEADER(
        # include 1 word for extended header if used
        offset=_IIGS_HEADER.size // 2 + (version >= 0x105),
        family=int(font.get_property('iigs.family-id') or '0', 10),
        style=_STYLE_TYPE(
            bold=font.weight in ('bold', 'extra-bold', 'ultrabold', 'heavy'),
            italic=font.slant in ('italic', 'oblique'),
            underline='underline' in font.decoration,
            outline='outline' in font.decoration,
            shadow='shadow' in font.decoration,
        ),
        # font format version
        version=version,
        # fbr = max width from origin (including whitespace) and right kerned pixels
        fbrExtent=fbr_extent,
        pointSize=font.point_size,
    )
    if version == 0x0105:
        # extended header comes before fontrec
        # so no need to increase owTLoc by 1 word because of its existence
        extra = _EXTENDED_HEADER(owTLocHigh=owt_loc_high)
    else:
        extra = b''
        if owt_loc_high:
            raise FileFormatError(
                'Bitmap strike too large for IIgs v1.1, use v1.5 instead.'
            )
    # write out name field, headers and NFNT
    name = font.family.encode('mac-roman', errors='replace')
    outstream.write(b''.join((
        bytes((len(name),)), name,
        bytes(header),
        bytes(extra),
    )))
    outstream.write(nfnt)
