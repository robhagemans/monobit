"""
monobit.formats.vfont - BSD/SunOS vfont format

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..struct import bitfield, little_endian as le, big_endian as be
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..magic import FileFormatError


@loaders.register(
    name='vfont',
    magic=(b'\x01\x1e', b'\x1e\x01'),
    patterns=('*.vfont',),
)
def load_vfont(instream, first_codepoint:int=0):
    """
    Load font from vfont file.

    first_codepoint: first codepoint in file (default: 0)
    """
    vfont_props, vfont_glyphs = _read_vfont(instream)
    logging.info('vfont properties:')
    for line in str(vfont_props).splitlines():
        logging.info('    ' + line)
    glyphs = _convert_from_vfont(vfont_glyphs, first_codepoint)
    return Font(glyphs)


@savers.register(linked=load_vfont)
def save_vfont(fonts, outstream, endianness:str='little'):
    """Save font to vfont file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to vfont file.')
    font, = fonts
    endian = endianness[0].lower()
    vfont_props, vfont_glyphs = _convert_to_vfont(font)
    logging.info('vfont properties:')
    for line in str(vfont_props).splitlines():
        logging.info('    ' + line)
    _write_vfont(outstream, vfont_props, vfont_glyphs, endian)


################################################################################
# vfont binary format

# http://www-lehre.inf.uos.de/~sp/Man/_Man_SunOS_4.1.3_html/html5/vfont.5.html
# https://web.archive.org/web/20210303052254/https://remilia.otherone.xyz/man/2.10BSD/5/vfont

_VFONT_MAGIC = 0o436

# storable code points
_VFONT_RANGE = range(0, 256)


# we have a choice of big and little endian files, need different base classes
_BASE = {'l': le, 'b': be}

# struct header {
#        short           magic;
#        unsigned short  size;
#        short           maxx;
#        short           maxy;
#        short           xtnd;
# } header;

_HEADER = {
    _endian: _BASE[_endian].Struct(
        magic='short',
        size_='uint16',
        maxx='short',
        maxy='short',
        xtnd='short',
    )
    for _endian in ('l', 'b')
}

# struct dispatch {
#        unsigned short  addr;
#        short           nbytes;
#        char            up;
#        char            down;
#        char            left;
#        char            right;
#        short           width;
# };


_DISPATCH = {
    _endian: _BASE[_endian].Struct(
        addr='uint16',
        nbytes='short',
        up='int8',
        down='int8',
        left='int8',
        right='int8',
        width='short',
    )
    for _endian in ('l', 'b')
}


def _read_vfont(instream):
    """Read vfont binary file and return as properties."""
    endian = 'l'
    header = _HEADER[endian].read_from(instream)
    if header.magic == 0x1e01:
        endian = 'b'
        header = _HEADER[endian].from_bytes(bytes(header))
    if header.magic != _VFONT_MAGIC:
        raise FileFormatError(
            'Not a vfont file: '
            f'incorrect magic number 0o{header.magic:o} != 0o436'
        )
    dispatch = _DISPATCH[endian].array(256).read_from(instream)
    bitmap = instream.read()
    glyph_bytes = tuple(
        bitmap[_entry.addr:_entry.addr+_entry.nbytes]
        for _entry in dispatch
    )
    # construct glyphs and set properties
    glyphs = tuple(
        Glyph.from_bytes(
            _glyph, vfont=_entry, width=_entry.left+_entry.right
        ) if _entry.nbytes else
        Glyph.blank(
            width=_entry.left+_entry.right,
            height=_entry.up+_entry.down,
            vfont=_entry
        )
        for _glyph, _entry in zip(glyph_bytes, dispatch)
    )
    return Props(**vars(header)), glyphs


def _convert_from_vfont(vfont_glyphs, first_codepoint):
    """Convert vfont properties and glyphs to standard."""
    # set glyph properties
    glyphs = (
        _glyph.modify(
            codepoint=_codepoint,
            left_bearing=-_glyph.vfont.left,
            right_bearing=_glyph.vfont.width-_glyph.width+_glyph.vfont.left,
            shift_up=-_glyph.vfont.down,
        ).drop('vfont')
        for _codepoint, _glyph in enumerate(vfont_glyphs, first_codepoint)
    )
    # drop undefined glyphs (zero advance empty)
    glyphs = tuple(
        _glyph for _glyph in glyphs
        if _glyph.advance_width or not _glyph.is_blank()
    )
    return glyphs


###############################################################################
# writer

def _convert_to_vfont(font):
    """Convert monobit font to vfont properties and glyphs."""
    # ensure codepoint values are set if possible
    font = font.label(codepoint_from=font.encoding)
    font = font.subset(_VFONT_RANGE)
    font = _make_contiguous(font)
    # set glyph properties
    glyphs = tuple(
        _glyph.modify(
            vfont=dict(
                left=-_glyph.left_bearing,
                right=_glyph.width+_glyph.left_bearing,
                down=-_glyph.shift_up,
                up=_glyph.height+_glyph.shift_up,
                width=_glyph.advance_width,
            )
        )
        for _glyph in font.glyphs
    )
    props = dict(
        maxx=max(_g.width for _g in glyphs),
        maxy=max(_g.height for _g in glyphs),
    )
    return props, glyphs


def _write_vfont(outstream, vfont_props, vfont_glyphs, endian):
    """Write vfont properties and glyphs to binary file."""
    glyph_bytes = tuple(_g.as_bytes() for _g in vfont_glyphs)
    offsets = (0,) + tuple(accumulate(len(_g) for _g in glyph_bytes))
    dispatch = _DISPATCH[endian].array(len(vfont_glyphs))(*(
        _DISPATCH[endian](
            addr=_o if  len(_b) else 0,
            nbytes=len(_b),
            **_g.vfont
        )
        for _b, _g, _o in zip(glyph_bytes, vfont_glyphs, offsets)
    ))
    bitmap = b''.join(glyph_bytes)
    header = _HEADER[endian](
        magic=_VFONT_MAGIC,
        size_=len(bitmap),
        **vfont_props
    )
    outstream.write(
        bytes(header)
        + bytes(dispatch)
        + bitmap
    )


def _make_contiguous(font):
    """Get contiguous range, fill gaps with empties."""
    glyphs = tuple(
        font.get_glyph(codepoint=_cp, missing='empty').modify(codepoint=_cp)
        for _cp in _VFONT_RANGE
    )
    font = font.modify(glyphs)
    return font
