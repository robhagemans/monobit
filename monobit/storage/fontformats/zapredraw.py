"""
monobit.storage.formats.zapredraw - RiscOS !ZapRedraw UCS file

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import groupby

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
    # >  +0 magic word 'ZRUF' (ZapRedraw UCS Font)
    magic='4s',
    # >  +4 reserved SBZ
    reserved_0='uint32',
    # >  +8 width of glyphs in px
    width='uint32',
    # > +12 height of glyphs in px
    height='uint32',
    # > +16 size of chunk directory
    dir_size='uint32',
    # > +20 offset to null glyph / 0
    null_offset='uint32',
    # > +24 reserved SBZ
    reserved_1='uint32',
    reserved_2='uint32',
    # > +32 reserved SBZ
)

_CHUNK_ENTRY = le.Struct(
    # >  +0 chunk number (eg a chunk containing glyph &2A3F puts &2A00 here)
    chunk_number='uint32',
    # >  +4 number of glyphs in this chunk
    count='uint32',
    # >  +8 file offset from start of header of glyph data
    offset='uint32',
    # > +12 reserved, must be 0
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
        # we are already at the point indicated by null_offset - no need to seek
        logging.debug(instream.tell())
        logging.debug(header.null_offset)
        part_font = load_bitmap(
            instream, width=header.width, height=header.height,
            count=1,
            msb='right', align='right',
            byte_swap=ceildiv(header.width, 8),
        )
        glyphs.append(part_font.glyphs[0].modify(codepoint=None, tag='null'))
    for entry in chunk_dir:
        # > The glyph data is in the same format as held by ZapRedraw in 1 bpp modes (see
        # > the ZapRedraw documentation). However, if the chunk contains less than 256
        # > glyphs, the data is preceded by a 256 byte translation table: for each glyph
        # > in the chunk, the table gives the character offset into the data + 1, or 0 if
        # > the glyph is not defined. The table must not be present for chunks containing
        # > all 256 glyphs.
        # note that "character offset" here means the character's ordinal in the list
        # so if the first defined character has codepoint 3, the next one codepoint 5,
        # the translation table starts \0\0\0\1\0\2 ...
        logging.debug(instream.tell())
        logging.debug(entry.offset)
        if entry.count < 256:
            translation_table = instream.read(256)
            logging.debug(translation_table)
            codepoints = sorted(
                _cp
                for _cp, _offs in enumerate(translation_table)
                if _offs
            )
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


@savers.register(linked=load_zapredraw)
def save_zapredraw(fonts, outstream):
    """Save a !ZapRedraw UCS font."""
    font = ensure_single(fonts)
    font = ensure_charcell(font)
    font = font.label()
    # determine number of chunks:
    # first bytes of 16-bit unicode codepoints
    chunked_codepoints = tuple(sorted(
        divmod(ord(_c), 0x100)
        for _c in font.get_chars()
        # can't save multi-char or unicodepoints beyond plane 00
        if len(_c) == 1 and ord(_c) < 0x10000
    ))
    chunk_map = []
    for chunk, codepairs in groupby(chunked_codepoints, lambda _c: _c[0]):
        codepoints = tuple(_cp for _ch, _cp in codepairs)
        if len(codepoints) < 256:
            translation_table = bytearray(256)
            for i, cp in enumerate(codepoints):
                translation_table[cp] = i + 1
        else:
            translation_table = b''
        chunk_map.append((chunk, codepoints, translation_table))
    n_chunks = len(chunk_map)
    dir_size = n_chunks * _CHUNK_ENTRY.size
    header = _ZAP_HEADER(
        magic=_ZAP_MAGIC,
        width=font.cell_size.x,
        height=font.cell_size.y,
        dir_size=dir_size,
        null_offset=dir_size + _ZAP_HEADER.size,
    )
    glyph_size = header.height * ceildiv(header.width, 8)
    # first chunk
    chunk_dir = [_CHUNK_ENTRY(
        chunk_number=0,
        count=256,
        offset=header.null_offset + glyph_size,
    )]
    offset = header.null_offset + glyph_size + 256 * glyph_size
    # other chunks
    for chunk, codepoints, _ in chunk_map[1:]:
        chunk_dir.append(
            _CHUNK_ENTRY(
                chunk_number=chunk*0x100,
                count=len(codepoints),
                offset=offset,
            )
        )
        offset += len(codepoints) * glyph_size
    chunk_dir = (_CHUNK_ENTRY * n_chunks)(*chunk_dir)
    # write out
    outstream.write(bytes(header))
    outstream.write(bytes(chunk_dir))
    # null character
    outstream.write(_zap_glyph(font.get_default_glyph().pixels))
    # first chunk, fill with risc-os encoding
    riscos = encodings['risc-os']
    for cp in range(256):
        glyph = font.get_glyph(char=riscos.char(cp), missing='space')
        outstream.write(_zap_glyph(glyph.pixels))
    # other chunks
    for chunk, codepoints, translation_table in chunk_map[1:]:
        # may be empty
        outstream.write(bytes(translation_table))
        for cp in codepoints:
            glyph = font.get_glyph(char=chr(chunk*0x100 + cp), missing='space')
            outstream.write(_zap_glyph(glyph.pixels))


def _zap_glyph(raster):
    glyphbytes = raster.mirror().as_bytes(
        align='right',
        byte_swap=ceildiv(raster.width, 8),
    )
    return glyphbytes
