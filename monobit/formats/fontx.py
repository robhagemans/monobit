"""
monobit.formats.fontx - DOS/V FONTX2 format

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..struct import bitfield, little_endian as le
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..magic import FileFormatError
from ..binary import ceildiv

from .raw import load_bitmap


_FONTX_MAGIC = b'FONTX2'


@loaders.register(
    name='fontx',
    magic=(_FONTX_MAGIC,),
    patterns=('*.fnt',),
)
def load_fontx(instream):
    """Load font from fontx file."""
    fontx_props, glyphs = _read_fontx(instream)
    logging.info('fontx properties:')
    for line in str(fontx_props).splitlines():
        logging.info('    ' + line)
    props = _convert_from_fontx(fontx_props)
    return Font(glyphs, **props)


@savers.register(linked=load_fontx)
def save_fontx(fonts, outstream, endianness:str='little'):
    """Save font to fontx file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to fontx file.')
    font, = fonts
    endian = endianness[0].lower()
    props, blocks,glyphs = _convert_to_fontx(font)
    logging.info('fontx properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    _write_fontx(outstream, props, blocks, glyphs)


################################################################################
# fontx binary format

# https://unifoundry.com/japanese/index.html
# http://elm-chan.org/docs/dosv/fontx_e.html


_SBCS_HEADER = le.Struct(
    magic='6s',
    name='8s',
    # Glyph Width (pixels), ncols
    width='uint8',
    # Glyph Height (pixels), nrows
    height='uint8',
    # Code Flag:
    #   0 for Alphanumeric Keyboard
    #   1 for Shift-JIS
    code_flag='uint8',
)
_DBCS_HEADER= le.Struct(
    # Number of Code Blocks, nb
    n_blocks='uint8',
)
_BLOCK_OFFSET = le.Struct(
    # Code Block Start
    # lowest low-byte in block
    start='uint16',
    # Code Block nb End
    # highest low-byte in block
    end='uint16',
)


def _read_fontx(instream):
    """Read fontx binary file and return as properties."""
    endian = 'l'
    sbcs_header = _SBCS_HEADER.read_from(instream)
    if sbcs_header.magic != _FONTX_MAGIC:
        raise FileFormatError(
            'Not a FONTX file: '
            f'incorrect magic `{sbcs_header.magic}` != {_FONTX_MAGIC}'
        )
    bytewidth = ceildiv(sbcs_header.width, 8)
    bytesize = bytewidth * sbcs_header.height
    props = vars(sbcs_header)
    if not sbcs_header.code_flag:
        glyphs = tuple(
            Glyph.from_bytes(
                instream.read(bytesize),
                width=sbcs_header.width,
                codepoint=_cp
            )
            for _cp in range(0, 256)
        )
    else:
        dbcs_header = _DBCS_HEADER.read_from(instream)
        props.update(vars(dbcs_header))
        blocks = _BLOCK_OFFSET.array(dbcs_header.n_blocks).read_from(instream)
        block_offs = (0, ) + tuple(accumulate(
            (_entry.end-_entry.start+1)*bytesize
            for _entry in blocks
        ))
        data = instream.read()
        glyphs = tuple(
            Glyph.from_bytes(
                data[_ofs+_i*bytesize:_ofs+(_i+1)*bytesize],
                width=sbcs_header.width,
                codepoint=_cp
            )
            for _b, (_entry, _ofs) in enumerate(zip(blocks, block_offs))
            for _i, _cp in enumerate(range(_entry.start, _entry.end+1))
        )
    return Props(**props), glyphs


def _convert_from_fontx(fontx_props):
    """Convert fontx properties and glyphs to standard."""
    props = dict(
        name=fontx_props.name.decode('latin-1', 'ignore'),
    )
    return props


###############################################################################
# writer

def _convert_to_fontx(font):
    """Convert monobit font to fontx properties and glyphs."""
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'FONTX2 format can only store character-cell fonts.'
        )
    # inflate glyphs to fill positive horizontal bearings
    font = font.equalise_horizontal()
    blank = Glyph.blank(*font.raster_size)
    # ensure codepoint values are set if possible
    if font.encoding:
        font = font.label(codepoint_from=font.encoding)
    props = Props(
        code_flag=len(max(font.get_codepoints())) > 1,
        name=font.name[:8].encode('ascii', 'replace'),
        width=font.cell_size.x,
        height=font.cell_size.y,
    )
    if not props.code_flag:
        # sbcs_font
        blocks = (range(256),)
    else:
        # dbcs font
        # find contiguous ranges and build block table
        # at most 256 blocks; keep one page in one block and contiguous range within
        # at most 2-byte codepoints
        cps = tuple(int(_c) for _c in font.get_codepoints())
        pages = tuple(
            tuple(
                _c for _c in cps
                if _c >= 0x100*_hi and _c < 0x100*(_hi+1)
            )
            for _hi in range(256)
        )
        # skip empty ranges
        blocks = tuple(
            range(min(_page), max(_page)+1)
            for _page in pages if _page
        )
    glyphs = tuple(
        font.get_glyph(codepoint=_cp, missing=blank).modify(codepoint=_cp)
        for _range in blocks
        for _cp in _range
    )
    return props, blocks, glyphs

def _write_fontx(outstream, props, blocks, glyphs):
    """Write fontx properties and glyphs to binary file."""
    glyph_bytes = tuple(_g.as_bytes() for _g in glyphs)
    bitmap = b''.join(glyph_bytes)
    offsets = (0,) + tuple(accumulate(len(_g) for _g in glyph_bytes))
    sbcs_header = _SBCS_HEADER(
        magic=_FONTX_MAGIC,
        **vars(props)
    )
    if props.code_flag:
        dbcs_header = _DBCS_HEADER(
            n_blocks=len(blocks)
        )
        block_offsets = _BLOCK_OFFSET.array(len(blocks))(*(
            _BLOCK_OFFSET(start=min(_block), end=max(_block))
            for _block in blocks
        ))
        outstream.write(
            bytes(sbcs_header)
            + bytes(dbcs_header)
            + bytes(block_offsets)
            + bitmap
        )
    else:
        outstream.write(
            bytes(sbcs_header)
            + bitmap
        )
