"""
monobit.storage.fontformats.u8m - U8/M UTF-8 for microcomputers font format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate
from unicodedata import normalize

from monobit.base.binary import ceildiv
from monobit.base.struct import little_endian as le
from monobit.base import Props
from monobit.storage import loaders, savers, Magic
from monobit.core import Font, Glyph, Char, Codepoint

from monobit.storage.utils.limitations import ensure_single, ensure_levels
from monobit.storage.fontformats.common import mac_style_name


_U8M_MAGIC = b'U8/M'


@loaders.register(
    name='u8m',
    patterns=('*.u8m',),
    magic=(Magic.offset(2) + _U8M_MAGIC,)
)
def load_u8m(instream):
    """Load font from U8/M file."""
    u8m = _read_u8m(instream)
    font = _convert_u8m(u8m)
    return font


@savers.register(linked=load_u8m)
def save_u8m(fonts, outstream):
    """Save font to U8/M file."""
    font = ensure_single(fonts)
    font = ensure_levels(font, 2)
    font = font.label().label(codepoint_from=font.encoding)
    u8m = _convert_to_u8m(font)
    _write_u8m(u8m, outstream)


###############################################################################
# U8/M file format
# https://github.com/kreativekorp/u8m

_SELECTION_HEADER = le.Struct(
    magic='4s',
    family_name_length='uint8',
    family_name='118s',
    null_terminator='uint8',
    family_id='uint16',
    style='uint8',
    point_size='uint8',
)

_MASTER_TABLE = le.Struct(
    glyph_table_offset='uint16',
    glyph_count='uint16',
    map_table_offset='uint16',
    map_count='uint16',
    map_index_for_native=le.uint16 * 4,
    map_index_for_low_bmp=le.uint16 * 32,
    map_index_for_high_bmp=le.uint16 * 16,
    map_index_for_astrals=le.uint16 * 6,
    line_ascent='uint8',
    line_descent='uint8',
    line_gap='uint8',
    line_height='uint8',
)

_MAP_HEADER = le.Struct(
    map_offset_byte_address='uint8',
    map_offset_page_address='uint16',
    number_of_entries='uint8',
)

_MAP_ENTRY = le.Struct(
    first_index_value='uint8',
    last_index_value='uint8',
    glyph_submap_index='uint16',
)

_GLYPH_RECORD = le.Struct(
    bitmap_offset_byte_address='uint8',
    bitmap_offset_page_address='uint16',
    advance_width='uint8',
)

_BITMAP_RECORD = le.Struct(
    y_offset='int8',
    x_offset='int8',
    height='uint8',
    width='uint8',
    # bitmap data, max 252 bytes
)


###############################################################################
# U8/M reader/converter

def _read_u8m(instream):
    """Read a U8/M file."""
    # unknown word, usually 160 ? maybe a local dos (e.g. c64) header?
    unknown = le.uint16.read_from(instream)
    anchor = instream.tell()
    u8m = Props()
    u8m.selection_header = _SELECTION_HEADER.read_from(instream)
    if u8m.selection_header.magic != _U8M_MAGIC:
        raise FileFormatError(
            'Not a U8/M file: incorrect file signature '
            f'{u8m.selection_header.magic} != {_U8M_MAGIC}'
        )
    u8m.master_table = _MASTER_TABLE.read_from(instream)
    # read map table
    instream.seek(anchor + 256 * u8m.master_table.map_table_offset)
    u8m.map_headers = (_MAP_HEADER * u8m.master_table.map_count).read_from(instream)
    u8m.map_table = []
    for map_header in u8m.map_headers:
        if bytes(map_header) == bytes(_MAP_HEADER.size):
            # empty array of maps
            map_data = ()
        else:
            instream.seek(
                anchor
                + map_header.map_offset_page_address * 256
                + map_header.map_offset_byte_address
            )
            map_data = (_MAP_ENTRY * map_header.number_of_entries).read_from(instream)
        u8m.map_table.append(map_data)
    # read glyph table
    instream.seek(anchor + 256 * u8m.master_table.glyph_table_offset)
    u8m.glyph_records = (_GLYPH_RECORD * u8m.master_table.glyph_count).read_from(instream)
    u8m.bitmap_records = []
    for glyph_record in u8m.glyph_records:
        if (
                glyph_record.bitmap_offset_page_address == 0
                and glyph_record.bitmap_offset_page_address == 0
            ):
            # empty glyph
            bitmap_record = _BITMAP_RECORD()
            bitmap_data = b''
        else:
            instream.seek(
                anchor
                + glyph_record.bitmap_offset_page_address * 256
                + glyph_record.bitmap_offset_byte_address
            )
            bitmap_record = _BITMAP_RECORD.read_from(instream)
            bitmap_data = instream.read(
                ceildiv(bitmap_record.height * bitmap_record.width, 8)
            )
        u8m.bitmap_records.append(
            Props(**vars(bitmap_record), bitmap_data=bitmap_data)
        )
    return u8m


def _apply_u8m_codepoint_maps(u8m, glyphs):
    """Apply codepoints from nested map tables."""

    def _traverse_map(map_index):
        map_array = u8m.map_table[map_index]
        for map in map_array:
            count = map.last_index_value - map.first_index_value + 1
            for i in range(count):
                codepoint = map.first_index_value + i
                glyph_index = map.glyph_submap_index + i
                yield codepoint, glyph_index

    def _add_label(glyph_index, new_label):
        glyph = glyphs[glyph_index]
        glyphs[glyph_index] = (
            glyph.modify(
                labels=glyph.get_labels() + (new_label,),
            )
        )

    for cp6, map_index in enumerate(u8m.master_table.map_index_for_native):
        for cp0, glyph_index in _traverse_map(map_index):
            cp = (cp6<<6) + cp0
            _add_label(glyph_index, Codepoint(cp))
    for cp6, map_index in enumerate(u8m.master_table.map_index_for_low_bmp):
        for cp0, glyph_index in _traverse_map(map_index):
            cp = (cp6<<6) + cp0
            _add_label(glyph_index, Char(chr(cp)))
    for cp12, map_index in enumerate(u8m.master_table.map_index_for_high_bmp):
        for cp6, submap_index in _traverse_map(map_index):
            for cp0, glyph_index in _traverse_map(submap_index):
                cp = (cp12<<12) + (cp6<<6) + cp0
                _add_label(glyph_index, Char(chr(cp)))
    for cp18, map_index in enumerate(u8m.master_table.map_index_for_astrals):
        for cp12, submap_index in _traverse_map(map_index):
            for cp6, subsubmap_index in _traverse_map(submap_index):
                for cp0, glyph_index in _traverse_map(subsubmap_index):
                    cp = (cp18<<18) + (cp12<<12) + (cp6<<6) + cp0
                    _add_label(glyph_index, Char(chr(cp)))


def _convert_u8m(u8m):
    """Convert U8/M data structure to monobit font."""
    # convert glyphs
    glyphs = [
        Glyph.from_bytes(
            _bm.bitmap_data,
            align='bit',
            width=_bm.width,
            height=_bm.height,
            shift_up=-(_bm.height+_bm.y_offset),
            left_bearing=_bm.x_offset,
            right_bearing=_gr.advance_width-_bm.width-_bm.x_offset,
        )
        for (_gr, _bm) in zip(u8m.glyph_records, u8m.bitmap_records)
    ]
    # apply codepoints from nested map tables
    _apply_u8m_codepoint_maps(u8m, glyphs)
    # convert font metrics and metadata
    # drop "notdef" first glyph, if indeed empty
    if not glyphs[0].pixels and not glyphs[0].advance_width:
        glyphs = glyphs[1:]
    return Font(
        glyphs,
        family=u8m.selection_header.family_name.rstrip(b'\0').decode('utf-8'),
        point_size=u8m.selection_header.point_size,
        ascent=u8m.master_table.line_ascent,
        descent=u8m.master_table.line_descent,
        line_height=u8m.master_table.line_height,
        style=mac_style_name(u8m.selection_header.style),
        # unconverted fields
        **{'u8m.family_id': u8m.selection_header.family_id},
    )


###############################################################################
# U8/M writer

def _convert_to_u8m(font):
    """Convert monobit font to U8/M data structure."""
    u8m = Props()
    family = font.family.encode('utf-8')[:118]
    u8m.selection_header = _SELECTION_HEADER(
        magic=_U8M_MAGIC,
        family_name_length=len(family),
        family_name=family,
        family_id=int(font.get_property('u8m.family_id')) or 0,
        # TODO calculate mac style (see NFNT?)
        style=0,
        point_size=font.point_size,
    )
    # first glyph must be notdef glyph
    glyphs = (Glyph(), *font.glyphs)
    # create codepoint index maps
    (
        u8m.master_table,
        u8m.map_headers,
        u8m.map_data
    ) = _create_u8m_codepoint_maps(glyphs)
    # remaining font metrics
    u8m.master_table.line_ascent = font.ascent
    u8m.master_table.line_descent = font.descent
    u8m.master_table.line_gap = font.leading
    u8m.master_table.line_height = font.line_height
    # convert glyphs
    u8m.bitmap_data = tuple(_g.as_bytes(align='bit') for _g in glyphs)
    u8m.bitmap_records = (_BITMAP_RECORD * len(glyphs))(*(
        _BITMAP_RECORD(
            y_offset=-_g.height-_g.shift_up,
            x_offset=_g.left_bearing,
            height=_g.height,
            width=_g.width,
        )
        for _g in glyphs
    ))
    # arrange bitmaps in pages
    # bitmap record may not cross page boundary
    lengths = tuple(_BITMAP_RECORD.size + len(_bd) for _bd in u8m.bitmap_data)
    glyph_records = []
    # starting file position for bitmap data
    current = (
        u8m.master_table.glyph_table_offset * 256
        + len(glyphs) * _GLYPH_RECORD.size
    )
    for glyph, length in zip(glyphs, lengths):
        page, addr = divmod(current, 256)
        if addr + length <= 256:
            current += length
        else:
            page += 1
            addr = 0
            current = page * 256 + addr + length
        glyph_records.append(
            _GLYPH_RECORD(
                bitmap_offset_byte_address=addr,
                bitmap_offset_page_address=page,
                advance_width=glyph.advance_width,
            )
        )
    u8m.glyph_records = (_GLYPH_RECORD*len(glyph_records))(*glyph_records)
    return u8m


def _create_map(cp_to_index):
    """Create a glyph or submap map based on dictionary."""
    if not cp_to_index or not any(cp_to_index.values()):
        return _MAP_ENTRY.array(0)()
    entries = []
    last_index = None
    for cp in sorted(cp_to_index.keys()):
        index = cp_to_index[cp]
        if not index:
            continue
        if index-1 == last_index and cp-1 == entries[-1].last_index_value:
            entries[-1].last_index_value += 1
            last_index += 1
        else:
            entries.append(_MAP_ENTRY(
                first_index_value=cp,
                last_index_value=cp,
                glyph_submap_index=index,
            ))
            last_index = index
    return (_MAP_ENTRY * len(entries))(*entries)


def _append_map(map_table, map, submap, cp_index):
    """Append a submap to the table and insert its index to a map."""
    if submap:
        map_index = len(map_table)
        map_table.append(submap)
        map[cp_index] = map_index


def _create_u8m_codepoint_maps(glyphs):
    """Construct nested U8/M codepoint maps."""
    # construct unicode to glyph index dict.
    # attempt to preserve multi-char grapheme sequences if 1-char NFC is available
    # but existing 1-char labels take precedence
    chars = {
        ord(_g.char): _i
        for _i, _g in enumerate(glyphs) if len(_g.char) == 1
    }
    multichars = (
        (normalize('NFC', _g.char), _i)
        for _i, _g in enumerate(glyphs) if len(_g.char) > 1
    )
    cp_to_glyphindex = (
        {ord(_c): _i for _c, _i in multichars if len(_c) == 1}
        | chars
    )
    # -- low-bmp map: codepoints 0x000--0x7ff =: cp6<<6 + cp0
    # map 0 must be the empty map
    map_table = [{}]
    #    master table: [cp6 (*32) -> map index]
    #    map table: [map index -> {cp0 -> glyph index}]
    low_bmp_maps = {}
    for cp6 in range(32):
        map = {
            _cp & 0x3f: _glyphindex
            for _cp, _glyphindex in cp_to_glyphindex.items()
            if (_cp>>6) == cp6
        }
        _append_map(map_table, low_bmp_maps, map, cp6)
    # -- high-bmp map: codepoints 0x800 - 0xffff =: cp12<<12 + cp6<<6 + cp0
    #    master table: [cp12 (*16) -> map index]
    #    map table: [map index -> {cp6 -> submap index}]
    #    map table: [submap index -> {cp0 -> glyph index}]
    high_cp_to_glyphindex = {
        (_cp>>12, (_cp>>6)&0x3f, _cp&0x3f): _glyphindex
        for _cp, _glyphindex in cp_to_glyphindex.items()
        if 0x7ff < _cp <= 0xffff
    }
    cp12s = set(_cp12 for _cp12, _, _ in high_cp_to_glyphindex)
    cp6s =  set(_cp6 for _, _cp6, _ in high_cp_to_glyphindex)
    high_bmp_maps = {}
    for cp12 in cp12s:
        map = {}
        for cp6 in cp6s:
            submap = {
                _cp0: _glyphindex
                for (_cp12, _cp6, _cp0), _glyphindex in high_cp_to_glyphindex.items()
                if (_cp12, _cp6) == (cp12, cp6)
            }
            _append_map(map_table, map, submap, cp6)
        _append_map(map_table, high_bmp_maps, map, cp12)
    # -- astral-planes map: codepoints 0x10000 - 0x17ffff =: cp18<<18 + scp12<<12 + cp6 <<6 + cp0
    #    master table: [cp18 (*6) -> map index]
    #    map table: [map index -> {cp12 -> submap index}]
    #    map table: [map index -> {cp6 -> subsubmap index}]
    #    map table: [subsubmap index -> {cp0 -> glyph index}]
    astral_cp_to_glyphindex = {
        (_cp>>18, (_cp>>12)&0x3f, (_cp>>6)&0x3f, _cp&0x3f): _glyphindex
        for _cp, _glyphindex in cp_to_glyphindex.items()
        if _cp > 0xffff
    }
    cp18s = set(_cp18 for _cp18, _, _, _ in astral_cp_to_glyphindex)
    cp12s = set(_cp12 for _, _cp12, _, _ in astral_cp_to_glyphindex)
    cp6s =  set(_cp6 for _, _, _cp6, _ in astral_cp_to_glyphindex)
    astral_maps = {}
    for cp18 in cp18s:
        map = {}
        for cp12 in cp12s:
            submap = {}
            for cp6 in cp6s:
                subsubmap = {
                    _cp0: _glyphindex
                    for (_cp18, _cp12, _cp6, _cp0), _glyphindex in astral_cp_to_glyphindex.items()
                    if (_cp18, _cp12, _cp6) == (cp18, cp12, cp6)
                }
                _append_map(map_table, submap, subsubmap, cp6)
            _append_map(map_table, map, submap, cp12)
        _append_map(map_table, astral_maps, map, cp18)
    # -- native map: native codepoints 0x00--0xff =: cp6<<6 + cp0
    #    master table: [cp6 (*32) -> map index]
    #    map table: [map index -> {cp0 -> glyph index}]
    native_cp_to_glyphindex = {
        int(_g.codepoint): _i for _i, _g in enumerate(glyphs) if _g.codepoint
    }
    native_maps = {}
    for cp6 in range(4):
        map = {
            _cp & 0x3f: _glyphindex
            for _cp, _glyphindex in native_cp_to_glyphindex.items()
            if _cp>>6 == cp6
        }
        if map:
            map_index = len(map_table)
            map_table.append(map)
            native_maps[cp6] = map_index
    # convert maps to U8/M data structures
    all_maps = tuple(_create_map(_map_dict) for _map_dict in map_table)
    low_bmp_indexes = tuple(low_bmp_maps.get(_i, 0) for _i in range(32))
    high_bmp_indexes = tuple(high_bmp_maps.get(_i, 0) for _i in range(16))
    astral_indexes = tuple(astral_maps.get(_i, 0) for _i in range(6))
    native_indexes = tuple(native_maps.get(_i, 0) for _i in range(4))
    n_maps = len(all_maps)
    headers_size = n_maps * _MAP_HEADER.size
    # map table can always start at byte 0x100 (page 1, byte 0)
    cumu_size = tuple(accumulate(
        (len(_map) * _MAP_ENTRY.size for _map in all_maps),
        initial=256 + headers_size
    ))
    map_headers = (n_maps * _MAP_HEADER)(*(
        _MAP_HEADER(
            map_offset_byte_address=_offset % 256,
            map_offset_page_address=_offset // 256,
            number_of_entries=len(_map),
        )
        for _map, _offset in zip(all_maps, cumu_size)
    ))
    # start glyph table at first page boundary after map data
    glyph_table_page = ceildiv(cumu_size[-1], 256)
    master_table = _MASTER_TABLE(
        glyph_table_offset=glyph_table_page,
        glyph_count=len(glyphs), # or only the ones we could index?
        map_table_offset=1,
        map_count=n_maps,
        map_index_for_native=(le.uint16*4)(*native_indexes),
        map_index_for_low_bmp=(le.uint16*32)(*low_bmp_indexes),
        map_index_for_high_bmp=(le.uint16*16)(*high_bmp_indexes),
        map_index_for_astrals=(le.uint16*6)(*astral_indexes),
    )
    #FIXME map data must not cross page boundary
    return master_table, map_headers, all_maps


def _write_u8m(u8m, outstream):
    # FIXME can't seek if we output to stdout

    # not sure about these 2 bytes
    outstream.write(bytes(le.uint16(160)))
    anchor = outstream.tell()

    def _align(page, offs):
        outstream.write(bytes(page * 256 + offs - outstream.tell() + anchor))

    outstream.write(bytes(u8m.selection_header))
    outstream.write(bytes(u8m.master_table))
    _align(1, 0)
    outstream.write(bytes(u8m.map_headers))
    for mh, md in zip(u8m.map_headers, u8m.map_data):
        _align(mh.map_offset_page_address, mh.map_offset_byte_address)
        outstream.write(bytes(md))
    _align(u8m.master_table.glyph_table_offset, 0)
    outstream.write(bytes(u8m.glyph_records))
    for gr, br, bd in zip(u8m.glyph_records, u8m.bitmap_records, u8m.bitmap_data):
        _align(gr.bitmap_offset_page_address, gr.bitmap_offset_byte_address)
        outstream.write(bytes(br))
        outstream.write(bytes(bd))
