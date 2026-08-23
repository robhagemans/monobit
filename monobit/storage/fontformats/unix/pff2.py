"""
monobit.storage.fontformats.unix.pff2 - GRUB PFF2 format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from monobit.base.struct import big_endian as be, bitfield
from monobit.base.binary import ceildiv
from monobit.base import Props, FileFormatError
from monobit.storage.utils.limitations import ensure_single
from monobit.storage import loaders, savers, Stream
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

@savers.register(linked=load_pff2)
def save_pff2(fonts, outstream):
    """Save to GRUB PFF2 font file."""
    font = ensure_single(fonts)
    font = ensure_levels(font, 2)
    _convert_write_pff2(outstream, font)


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
    return Props(name=header.name.decode('ascii'), anchor=anchor, data=data)


def _read_pff2(instream):
    first_section = _read_section(instream)
    if first_section.name != 'FILE' or first_section.data != b'PFF2':
        raise FileFormatError('Not a PFF2 file: incorrect FILE section.')
    sections = {}
    while instream.peek(1):
        section = _read_section(instream)
        sections[section.name] = section
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
    flags='uint8',
    # be.Struct(
    #     reserved=bitfield('uint8', 5),
    #     compressed=bitfield('uint8', 3),
    # ),
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


###############################################################################
# PFF2 writer


def _write_section(outstream, section, length=None):
    """Write a PFF2 section."""
    header = _SECTION_HEADER(
        name=section.name[:4].encode('ascii').ljust(4, b'\0'),
        length=len(section.data) if length is None else length
    )
    outstream.write(bytes(header))
    outstream.write(section.data)


def _convert_write_pff2(outstream, font):
    """Convert font to pff2 and write out."""
    _write_section(outstream, Props(name='FILE', data=b'PFF2'))
    _write_section(outstream, Props(name='NAME', data=font.name.encode('ascii') + b'\0'))
    _write_section(outstream, Props(name='FAMI', data=font.family.encode('ascii') + b'\0'))
    weight = font.weight.lower()
    if weight in ('regular', 'normal', 'bold'):
        _write_section(outstream, Props(name='WEIG', data=(
            'normal' if font.weight == 'regular' else font.weight
        ).encode('ascii') + b'\0'))
    slant = font.slant.lower()
    if slant in ('normal', 'roman', 'oblique', 'italic'):
        _write_section(outstream, Props(name='SLAN', data=(
            'normal' if font.slant == 'roman' else
            'italic' if font.slant == 'oblique' else font.slant
        ).encode('ascii') + b'\0'))
    _write_section(outstream, Props(name='PTSZ', data=bytes(be.uint16(font.point_size))))
    _write_section(outstream, Props(name='MAXW', data=bytes(be.uint16(font.bounding_box.x))))
    _write_section(outstream, Props(name='MAXH', data=bytes(be.uint16(font.bounding_box.y))))
    _write_section(outstream, Props(name='ASCE', data=bytes(be.uint16(font.ascent))))
    _write_section(outstream, Props(name='DESC', data=bytes(be.uint16(font.descent))))
    anchor = (
        outstream.tell()
        + _SECTION_HEADER.size
        + _CHIX_GLYPH_ENTRY.size * len(font.glyphs)
        + _SECTION_HEADER.size
    )
    glyphbytes = tuple(_g.as_bytes(align='bit') for _g in font.glyphs)
    cumul_sizes = accumulate((len(_b)+_DATA_GLYPH_ENTRY.size for _b in glyphbytes), initial=0)
    glyph_entries = (
        _CHIX_GLYPH_ENTRY(codepoint=ord(_g.char), offset=anchor+_cumsize)
        for _g, _cumsize in zip(font.glyphs, cumul_sizes)
    )
    _write_section(outstream, Props(name='CHIX', data=b''.join(bytes(_ge) for _ge in glyph_entries)))
    assert outstream.tell() == anchor - _SECTION_HEADER.size
    data_entries = (
        _DATA_GLYPH_ENTRY(
            width=_g.width, height=_g.height,
            x_offset=_g.left_bearing, y_offset=_g.shift_up,
            device_width=_g.advance_width,
        )
        for _g in font.glyphs
    )
    _write_section(outstream, length=-1, section=Props(name='DATA', data=b''.join(
        bytes(_de) + bytes(_gb) for _de, _gb in zip(data_entries, glyphbytes)
    )))
