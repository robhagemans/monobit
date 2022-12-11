"""
monobit.formats.vfont - BSD/SunOS vfont format

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..struct import bitfield, little_endian as le, big_endian as be
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError



@loaders.register(name='vfont', magic=(b'\x01\x1e', b'\x1e\x01'))
def load_vfont(instream, where=None):
    """Load font from vfont file."""
    vfont_props, vfont_glyphs = _read_vfont(instream)
    logging.info('vfont properties:')
    for line in str(vfont_props).splitlines():
        logging.info('    ' + line)
    glyphs = _convert_from_vfont(vfont_glyphs)
    return Font(glyphs)


@savers.register(linked=load_vfont)
def save_vfont(fonts, outstream, where=None):
    """Save font to vfont file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to vfont file.')
    font, = fonts
    vfont_props, vfont_glyphs = _convert_to_vfont(font)
    logging.info('vfont properties:')
    for line in str(vfont_props).splitlines():
        logging.info('    ' + line)
    _write_fzx(outstream, vfont_props, vfont_glyphs)


################################################################################
# vfont binary format

# http://www-lehre.inf.uos.de/~sp/Man/_Man_SunOS_4.1.3_html/html5/vfont.5.html
# https://web.archive.org/web/20210303052254/https://remilia.otherone.xyz/man/2.10BSD/5/vfont


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
        size='uint16',
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
    data = instream.read()
    header = _HEADER[endian].from_bytes(data)
    if header.magic == 0x1e01:
        endian = 'b'
        header = _HEADER[endian].from_bytes(data)
    if header.magic != 0o436:
        raise FileFormatError(
            'Not a vfont file: '
            f'incorrect magic number 0o{header.magic:o} != 0o436'
        )
    dispatch = _DISPATCH[endian].array(256).from_bytes(
        data, _HEADER[endian].size
    )
    bitmap = data[_HEADER[endian].size + dispatch.size:]
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


def _write_vfont(outstream, vfont_props, vfont_glyphs):
    """Write vfont properties and glyphs to binary file."""
    raise NotImplementedError()


###############################################################################
# metrics conversion

def _convert_from_vfont(vfont_glyphs):
    """Convert vfont properties and glyphs to standard."""
    # set glyph properties
    glyphs = (
        _glyph.modify(
            codepoint=_codepoint,
            left_bearing=-_glyph.vfont.left,
            right_bearing=_glyph.vfont.width-_glyph.width+_glyph.vfont.left,
            shift_up=-_glyph.vfont.down,
        ).drop('vfont')
        for _codepoint, _glyph in enumerate(vfont_glyphs)
    )
    # drop undefined glyphs (zero advance empty)
    glyphs = tuple(
        _glyph for _glyph in glyphs
        if _glyph.advance_width or not _glyph.is_blank()
    )
    return glyphs

def _convert_to_fzx(font):
    """Convert monobit font to vfont properties and glyphs."""
    raise NotImplementedError()
