"""
monobit.storage.fontformats.beos - BeOS Bitmap Font

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from monobit.base.basetypes import FileFormatError, UnsupportedError
from monobit.base.binary import ceildiv
from monobit.base.struct import big_endian as be
from monobit.core import Font, Glyph
from monobit.storage import loaders, savers
from monobit.storage.streams import Stream
from monobit.storage.utils.limitations import ensure_levels, ensure_single

logger = logging.getLogger(__name__)

# http://www.eonet.ne.jp/~hirotsu/bin/bmf_format.txt

_HEADER = be.Struct(
    mark='4s',
    # total size of the file
    size='uint32',
    # > font-family-name size (not including the trailing null)
    ffnSize='uint16',
    # > font-style-name size (not including the trailing null)
    fsnSize='uint16',
    # rotation and shear angles in radians, 0.0 for upright
    rotation='float',
    shear='float',
    # location-table hash mask; must be a power of two minus one
    hmask='uint32',
    # > font-point (Bitmap fonts are enabled at this point number)
    point='uint16',
    # pixel format: 1 = B/W (RLE), 2 = TV scale, 3 = grayscale (4-bit packed)
    bpp='uint8',
    version='uint8',
    # uninitialised memory in fonts written by BeOS
    reserved='8s',
)

_FC_BLACK_AND_WHITE = 1
_FC_TV_SCALE = 2
_FC_GRAY_SCALE = 3

_LOCATION_ENTRY = be.Struct(
    offset='uint32',
    # utf-16: [char or high surrogate, low surrogate or 0]
    code_0='uint16',
    code_1='uint16',
)

_GLYPH_DATA = be.Struct(
    # ink edges of the scalable glyph, in em units;
    # 1234567.0 in edge_left means 'edges not computed'
    edge_left='float',
    edge_right='float',
    # bitmap bounding box relative to the baseline origin, y down
    left='int16',
    top='int16',
    right='int16',
    bottom='int16',
    # advance vector in (fractional) pixels
    x_escape='float',
    y_escape='float',
)

_EDGE_LEFT_NOT_COMPUTED = 1234567.0
_EDGE_RIGHT_NOT_COMPUTED = 1234568.0

_BEOS_MAGIC = b'|Be;'

def _char_from_codes(code_0: int, code_1: int) -> str:
    """Decode a location-entry utf-16 code unit pair to a character."""
    if 0xd800 <= code_0 < 0xdc00 and 0xdc00 <= code_1 < 0xe000:
        return chr(
            0x10000 + ((code_0 - 0xd800) << 10) + (code_1 - 0xdc00)
        )
    return chr(code_0)


@loaders.register(
    name='beos',
    magic=(_BEOS_MAGIC,)
)
def load_beos(instream: Stream):
    """Load font from Be Bitmap Font file."""
    header = _HEADER.read_from(instream)
    if header.version != 0:
        raise FileFormatError( f'Unknown Be Bitmap Font version {header.version}.' )
    if header.bpp != _FC_GRAY_SCALE:
        raise UnsupportedError('Only grayscale Be Bitmap Fonts are supported.')
    if header.rotation != 0 or header.shear != 0:
        logger.warning('Nonzero rotation or shear angles are ignored.')
    if header.hmask & (header.hmask + 1) or header.hmask < 3:
        # BeOS rejects such files; older monobit versions wrote them
        logger.warning('Location-table mask is not a power of two minus one')
    familyName = instream.read(header.ffnSize+1)[:-1].decode('latin-1')
    styleName = instream.read(header.fsnSize+1)[:-1].decode('latin-1')
    logger.debug('family: %s', familyName)
    logger.debug('style: %s', styleName)

    table_size = _LOCATION_ENTRY.size * (header.hmask+1)
    table_bytes = instream.read(table_size)
    if len(table_bytes) != table_size:
        raise FileFormatError('Location table extends beyond end of file.')
    
    # hash table of pointers to glyphs, hashed by unicode codepoint
    location_table = (_LOCATION_ENTRY * (header.hmask+1)).from_bytes(table_bytes)
    location_dict = {
        _e.offset: _char_from_codes(_e.code_0, _e.code_1)
        for _e in location_table
        # the offset is read as signed by BeOS; empty slots hold -1
        if 0 < _e.offset < 0x80000000
    }

    glyphs = []
    while instream.tell() < header.size:
        pointer = instream.tell()
        glyph_data = _GLYPH_DATA.read_from(instream)
        # TODO: validate glyph geometry?
        # bitmap dimensions
        width = glyph_data.right - glyph_data.left + 1
        height = glyph_data.bottom - glyph_data.top + 1
        bitmap_size = ceildiv(width * 4, 8) * height
        glyph_bytes = instream.read(bitmap_size)
        # TODO sanity check bitmap_size = glyph_bites
        # TODO sanity check legacy_ink
        glyphs.append(
            Glyph.from_bytes(
                glyph_bytes, width=width, height=height, bits_per_pixel=4,
                char=location_dict.get(pointer, None),
                right_bearing=(int(glyph_data.x_escape + .5) - width - glyph_data.left),
                left_bearing=glyph_data.left,
                shift_up=-1-glyph_data.bottom,
                scalable_width=glyph_data.x_escape,
            )
        )
    ## TODO: sanity check overhang

    # TODO: detect legacy_ink?
    return Font(
        glyphs,
        encoding='unicode',
        family=familyName,
        subfamily=styleName,
        point_size=header.point,
        # TODO: verify ppem/dpi=72
    )


@savers.register(linked=load_beos)
def save_beos(fonts, outstream):
    """Save font to BeOS file."""
    font = ensure_single(fonts)
    # 4 bits per pixel
    font = ensure_levels(font, 16)
    font = font.label()
    # drop multi-codepoint sequences and unlabelled glyphs
    glyphs = tuple(_g for _g in font.glyphs if len(_g.char) == 1)
    # create header
    style_name = font.name[len(font.family):].strip()
    header = _HEADER(
        mark=_BEOS_MAGIC,
        # size='uint32',
        ffnSize=len(font.family),
        fsnSize=len(style_name),
        # ltMax is an assumption reproducing the value in my sample font
        ltMax = 2*(len(glyphs)-1)-1,
        point=font.point_size,
        unknown_768=0x300,
    )
    # create glyph table
    glyph_data = tuple(
        bytes(_GLYPH_DATA(
            unknown_0x4996b438 = 0x4996b438,
            unknown_0x4996b440 = 0x4996b440,
            left=_g.left_bearing,
            top=(-1-_g.shift_up) -_g.height + 1,
            right=_g.width + _g.left_bearing - 1,
            bottom=-1-_g.shift_up,
            width=_g.scalable_width,
            # maybe_height='float',
        ))
        for _g in glyphs
    )
    strike_offset = (
        _HEADER.size + header.ffnSize + 1 + header.fsnSize + 1
        + _LOCATION_ENTRY.size * (header.ltMax+1)
    )
    glyph_bytes = tuple(_g.set_bits_per_pixel(4).as_bytes() for _g in glyphs)
    offsets = accumulate(
        (len(_g) + len(_s) for _g, _s in zip(glyph_data, glyph_bytes)),
        initial=strike_offset,
    )
    # create location entries
    loc_entries = tuple(
        _LOCATION_ENTRY(pointer=_offs, code=ord(_g.char))
        for _g, _offs in zip(glyphs, offsets)
    )
    strike = b''.join(
        b''.join((_data, _bytes))
        for _data, _bytes in zip(glyph_data, glyph_bytes)
    )
    header.size = strike_offset + len(strike)
    # create hash table
    hashes = (
        ((ord(_g.char)>>2) ^ (ord(_g.char)<<3)) & header.ltMax
        for _g in glyphs
    )
    location_table = [None] * (header.ltMax+1)
    for entry, hash in zip(loc_entries, hashes):
        while location_table[hash] is not None:
            hash += 1
            if hash > header.ltMax:
                hash = 0
        location_table[hash] = entry
    location_table = (_LOCATION_ENTRY * (header.ltMax+1))(*(
        _entry if _entry else _LOCATION_ENTRY(pointer=0xffffffff)
        for _entry in location_table
    ))
    outstream.write(bytes(header))
    outstream.write(font.family.encode('latin-1', 'replace')+ b'\0')
    outstream.write(style_name.encode('latin-1', 'replace')+ b'\0')
    outstream.write(bytes(location_table))
    outstream.write(bytes(strike))
