"""
monobit.storage.fontformats.u8m - U8/M UTF-8 for microcomputers font format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.binary import ceildiv
from monobit.base.struct import little_endian as le
from monobit.base import Props
from monobit.storage import loaders, savers, Magic
from monobit.core import Font, Glyph, Char, Codepoint

from monobit.storage.utils.limitations import ensure_single, ensure_levels


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


# https://github.com/kreativekorp/u8m

_SELECTION_HEADER = le.Struct(
    magic=le.uint8 * 4,
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

def _read_u8m(instream):
    """Read a U8/M file."""
    # unknown word, usually 160 ? maybe a local dos (e.g. c64) header?
    unknown = le.uint16.read_from(instream)
    anchor = instream.tell()
    u8m = Props()
    u8m.selection_header = _SELECTION_HEADER.read_from(instream)
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
            # gr=_gr,
        )
        for (_gr, _bm) in zip(u8m.glyph_records, u8m.bitmap_records)
    ]

    # apply codepoints from nested map tables

    def _traverse_map(map_index):
        map_array = u8m.map_table[map_index]
        for map in map_array:
            count = map.last_index_value - map.first_index_value + 1
            for i in range(count):
                codepoint = map.first_index_value + i
                glyph_index = map.glyph_submap_index + i
                yield codepoint, glyph_index

    def _add_label(glyph_index, new_label, notes=None):
        glyph = glyphs[glyph_index]
        glyphs[glyph_index] = (
            glyph.modify(
                labels=glyph.get_labels() + (new_label,),
                notes=notes,
            )
        )

    for cp6, map_index in enumerate(u8m.master_table.map_index_for_native):
        for cp0, glyph_index in _traverse_map(map_index):
            cp = (cp6<<6) + cp0
            _add_label(glyph_index, Codepoint(cp), notes=(cp6, cp0))
    for cp6, map_index in enumerate(u8m.master_table.map_index_for_low_bmp):
        for cp0, glyph_index in _traverse_map(map_index):
            cp = (cp6<<6) + cp0
            _add_label(glyph_index, Char(chr(cp)), notes=(cp6, cp0))
    for cp12, map_index in enumerate(u8m.master_table.map_index_for_high_bmp):
        for cp6, submap_index in _traverse_map(map_index):
            for cp0, glyph_index in _traverse_map(submap_index):
                cp = (cp12<<12) + (cp6<<6) + cp0
                _add_label(glyph_index, Char(chr(cp)), notes=(cp12, cp6, cp0))
    for cp18, map_index in enumerate(u8m.master_table.map_index_for_astrals):
        for cp12, submap_index in _traverse_map(map_index):
            for cp6, subsubmap_index in _traverse_map(submap_index):
                for cp0, glyph_index in _traverse_map(subsubmap_index):
                    cp = (cp18<<18) + (cp12<<12) + (cp6<<6) + cp0
                    _add_label(glyph_index, Char(chr(cp)), notes=(cp18, cp12, cp6, cp0))

    # convert font metrics and metadata
    return Font(
        glyphs,
        family=u8m.selection_header.family_name.rstrip(b'\0').decode('utf-8'),
        point_size=u8m.selection_header.point_size,
        ascent=u8m.master_table.line_ascent,
        descent=u8m.master_table.line_descent,
        line_height=u8m.master_table.line_height,
        # unconverted fields
        **{
            'u8m.line_gap': u8m.master_table.line_gap,
            'u8m.family_id': u8m.selection_header.family_id,
            'u8m.style': u8m.selection_header.style,
        },
    )
