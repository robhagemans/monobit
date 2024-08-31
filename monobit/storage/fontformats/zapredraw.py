"""
monobit.storage.formats.zapredraw - RiscOS !ZapRedraw UCS file

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Glyph, Font, Char
from monobit.encoding import encodings
from monobit.base.struct import little_endian as le, bitfield
from monobit.base.binary import ceildiv

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single, ensure_charcell, make_contiguous


###############################################################################
# https://github.com/jaylett/zap/blob/master/dists/fonts/!ZapFonts/Fonts/!ReadMe%2Cfff

_ZAP_MAGIC = b'ZRUF'
_ZAP_HEADER = le.Struct(
    #  +0 magic word 'ZRUF' (ZapRedraw UCS Font)
    magic='4s',
    #  +4 reserved SBZ
    reserved_0='uint32',
    #  +8 width of glyphs in px
    width='uint32',
    # +12 height of glyphs in px
    height='uint32',
    # +16 size of chunk directory
    dir_size='uint32',
    # +20 offset to null glyph / 0
    null_offset='uint32',
    # +24 reserved SBZ
    reserved_1='uint32',
    reserved_2='uint32',
    # +32 reserved SBZ
)

_CHUNK_ENTRY = le.Struct(
    #  +0 chunk number (eg a chunk containing glyph &2A3F puts &2A00 here)
    chunk_number='uint32',
    #  +4 number of glyphs in this chunk
    count='uint32',
    #  +8 file offset from start of header of glyph data
    offset='uint32',
    # +12 reserved, must be 0
    reserved='uint32',
)


@loaders.register(
    name='zapredraw',
    magic=(_ZAP_MAGIC,),
    patterns=('*,1bd',),
)
def load_zapredraw(instream):
    """Load a new-style ZapFont (ZRUF)."""
    header = _ZAP_HEADER.read_from(instream)
    if header.magic != _ZAP_MAGIC:
        raise FileFormatError(
            f'Not a !ZapRedraw file: incorrect signature {header.magic}.'
        )
    logging.debug('header: %s', header)
    chunk_count = header.dir_size // _CHUNK_ENTRY.size
    chunk_dir = (_CHUNK_ENTRY * chunk_count).read_from(instream)
    logging.debug(chunk_dir)
    glyphs = []
    if header.null_offset:
        # instream.seek(header.null_offset)
        part_font = load_bitmap(
            instream, width=header.width, height=header.height,
            count=1,
            msb='right', align='right',
            byte_swap=ceildiv(header.width, 8),
        )
        glyphs.append(part_font.glyphs[0].modify(codepoint=None, tag='null'))
    for entry in chunk_dir:
        # The glyph data is in the same format as held by ZapRedraw in 1 bpp modes (see
        # the ZapRedraw documentation). However, if the chunk contains less than 256
        # glyphs, the data is preceded by a 256 byte translation table: for each glyph
        # in the chunk, the table gives the character offset into the data + 1, or 0 if
        # the glyph is not defined. The table must not be present for chunks containing
        # all 256 glyphs.
        if entry.count < 256:
            translation_table = instream.read(256)
            logging.debug(translation_table)
            codemap = sorted(
                (_offs, _cp)
                for _cp, _offs in enumerate(translation_table)
                if _offs
            )
            codepoints = (_cp for _offs, _cp in codemap)
        else:
            codepoints = range(256)
        part_font = load_bitmap(
            instream, width=header.width, height=header.height,
            count=entry.count,
            msb='right', align='right',
            byte_swap=ceildiv(header.width, 8),
        )
        glyphs.extend(
            _g.modify(codepoint=entry.chunk_number+_cp)
            for _g, _cp in zip(part_font.glyphs, codepoints)
        )
    font = Font(
        glyphs,
        source_format='ZapRedraw UCS',
        default_char='"null"',
    )
    # encoding is RiscOS latin-1 for chunk 0, unicode elsewhere.
    chunk_0_encoding = encodings['risc-os'].subset('0x20-0x7e,0x80-0xff')
    font = font.label(char_from=chunk_0_encoding)
    font = font.label(char_from='unicode')
    return font.modify(encoding=None)
