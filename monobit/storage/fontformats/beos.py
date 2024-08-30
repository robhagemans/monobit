"""
monobit.storage.fontformats.beos - BeOS Bitmap Font

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from monobit.base.binary import ceildiv
from monobit.base.struct import big_endian as be
from monobit.storage import loaders, savers
from monobit.core import Font, Glyph

from monobit.storage.utils.limitations import ensure_single


# http://www.eonet.ne.jp/~hirotsu/bin/bmf_format.txt

_HEADER = be.Struct(
    mark='4s',
    # > total size
    size='uint32',
    # > font-family-name size (not including the trailing null)
    ffnSize='uint16',
    # > font-style-name size (not including the trailing null)
    fsnSize='uint16',
    padding_0='10s',
    # > The number of characters that can be stored in the location-table -1
    ltMax='uint16',
    # > font-point (Bitmap fonts are enabled at this point number)
    point='uint16',
    # > 0x0300 (unknown)
    unknown_768='uint16',
    # unknown and differs per font; ProFont has it all null so that is valid?
    unknown='8s',
)

_LOCATION_ENTRY = be.Struct(
    pointer='uint32',
    code='uint16',
    reserved='uint16',
)

_GLYPH_DATA = be.Struct(
    unknown_0x4996b438 = 'uint32',
    unknown_0x4996b440 = 'uint32',
    left='int16',
    top='int16',
    right='int16',
    bottom='int16',
    width='float',
    maybe_height='float',
)

_BEOS_MAGIC = b'|Be;'


@loaders.register(
    name='beos',
    magic=(_BEOS_MAGIC,)
)
def load_beos(instream):
    """Load font from Be Bitmap Font file."""
    header = _HEADER.read_from(instream)
    familyName = instream.read(header.ffnSize+1)[:-1].decode('latin-1')
    styleName = instream.read(header.fsnSize+1)[:-1].decode('latin-1')
    logging.debug('header: %s', header)
    logging.debug('family: %s', familyName)
    logging.debug('style: %s', styleName)
    # hash table of pointers to glyphs, hashed by unicode codepoint
    location_table = (_LOCATION_ENTRY * (header.ltMax+1)).read_from(instream)
    location_dict = {_e.pointer: _e.code for _e in location_table}
    glyphs = []
    while instream.tell() < header.size:
        pointer = instream.tell()
        code = location_dict.get(pointer, None)
        glyph_data = _GLYPH_DATA.read_from(instream)
        # bitmap dimensions
        width = glyph_data.right - glyph_data.left + 1
        height = glyph_data.bottom - glyph_data.top + 1
        # 4 bits per pixel
        bytewidth = ceildiv(width * 4, 8)
        glyph_bytes = instream.read(height*bytewidth)
        glyphs.append(
            Glyph.from_bytes(
                glyph_bytes, width=width, height=height, bits_per_pixel=4,
                char=chr(code) if code is not None else code,
                right_bearing=round(glyph_data.width)-width-glyph_data.left,
                left_bearing=glyph_data.left,
                shift_up=-1-glyph_data.bottom,
                scalable_width=glyph_data.width,
            )
        )
    return Font(
        glyphs,
        encoding='unicode',
        family=familyName,
        subfamily=styleName,
        point_size=header.point,
    )


@savers.register(linked=load_beos)
def save_beos(fonts, outstream):
    """Save font to BeOS file."""
    font = ensure_single(fonts)
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
    glyph_bytes = tuple(_g.as_bytes(bits_per_pixel=4) for _g in glyphs)
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
