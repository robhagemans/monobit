"""
monobit.storage.fontformats.unix.pff2 - GRUB PFF2 format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import cycle

from monobit.base.struct import big_endian as be, bitfield
from monobit.base.binary import ceildiv
from monobit.storage import loaders, Stream
from monobit.base import Props, FileFormatError
from monobit.core import Font, Glyph


@loaders.register(
    name='pff2',
    patterns=('*.pf2',),
    magic=(b'FILE\0\0\0\4PFF2',),
)
def load_pff2(instream):
    """Load a GRUB PFF2 font file."""
    sections = _read_pff2(instream)
    return _convert_pff2(sections)


###############################################################################
# GRUB PFF2 reader
# see http://grub.gibibit.com/New_font_format


_SECTION_HEADER = be.Struct(
    name='4s',
    # signed length. -1 indicates "read all to end of file"
    length='int32',
)


def _read_section(instream):
    """Read a PFF2 section."""
    header = _SECTION_HEADER.read_from(instream)
    anchor = instream.tell()
    data = instream.read(header.length)
    return header.name.decode('ascii'), anchor, data


def _read_pff2(instream):
    name, anchor, data = _read_section(instream)
    if name != 'FILE' or data != b'PFF2':
        raise FileFormatError('Not a PFF2 file: incorrect FILE section.')
    sections = {}
    while instream.peek(1):
        name, anchor, data = _read_section(instream)
        sections[name] = Props(name=name, anchor=anchor, data=data)
    return sections


def _convert_string(sections, name):
    try:
        props = sections[name]
    except KeyError:
        return None
    return props.data.rstrip(b'\0').decode('ascii')

def _convert_int(sections, name, inttype=be.int16):
    try:
        props = sections[name]
    except KeyError:
        return None
    return int(inttype.from_bytes(props.data))


def _convert_pff2(sections):
    """Convert PFF2 to monobit."""
    pff2_props = Props(
        name=_convert_string(sections, 'NAME'),
        family=_convert_string(sections, 'FAMI'),
        weight=_convert_string(sections, 'WEIG'),
        slant=_convert_string(sections, 'SLAN'),
        point_size=_convert_int(sections, 'PTSZ', be.uint16),
        ascent=_convert_int(sections, 'ASCE', be.int16),
        descent=_convert_int(sections, 'DESC', be.int16),
        # ignoring MAXW and MAXH
    )
    if pff2_props.slant == 'normal':
        pff2_props.slant = 'roman'
    if pff2_props.weight == 'normal':
        pff2_props.weight = 'regular'
    try:
        glyphs = _convert_pff2_glyphs(sections['CHIX'], sections['DATA'])
    except KeyError:
        raise FileFormatError('No CHIX or DATA section found.')
    return Font(glyphs, **vars(pff2_props))


_CHIX_GLYPH_ENTRY = be.Struct(
    codepoint='uint32',
    flags=be.Struct(
        reserved=bitfield('uint8', 5),
        compressed=bitfield('uint8', 3),
    ),
    offset='uint32',
)

_DATA_GLYPH_ENTRY = be.Struct(
    width='uint16',
    height='uint16',
    x_offset='int16',
    y_offset='int16',
    device_width='int16',
)


def _convert_pff2_glyphs(chix, data):
    """Convert CHIX and DATA sections to glyphs."""
    with Stream.from_data(chix.data, mode='r') as chixstream:
        n_glyphs = len(chix.data) // _CHIX_GLYPH_ENTRY.size
        entries = (_CHIX_GLYPH_ENTRY * n_glyphs).read_from(chixstream)
    with Stream.from_data(data.data, mode='r') as datastream:
        glyphs = []
        for entry in entries:
            # offsets given relative to start of file, not data section
            datastream.seek(entry.offset - data.anchor)
            metrics = _DATA_GLYPH_ENTRY.read_from(datastream)
            rasterdata = datastream.read(
                ceildiv(metrics.width * metrics.height, 8)
            )
            glyphs.append(Glyph.from_bytes(
                rasterdata, width=metrics.width, height=metrics.height, align='bit',
                left_bearing=metrics.x_offset, shift_up=metrics.y_offset,
                right_bearing=metrics.device_width-metrics.width-metrics.x_offset,
                char=chr(entry.codepoint),
            ))
    return glyphs
