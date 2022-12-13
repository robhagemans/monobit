"""
monobit.formats.fontx - DOS/V FONTX2 format

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..struct import bitfield, little_endian as le
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError
from ..binary import ceildiv

from .raw import load_bitmap
from .windows import _normalise_metrics


_FONTX_MAGIC = b'FONTX2'


@loaders.register(name='fontx', magic=(_FONTX_MAGIC,))
def load_fontx(instream, where=None):
    """Load font from fontx file."""
    fontx_props, glyphs = _read_fontx(instream)
    logging.info('fontx properties:')
    for line in str(fontx_props).splitlines():
        logging.info('    ' + line)
    props = _convert_from_fontx(fontx_props)
    return Font(glyphs, **props)


@savers.register(linked=load_fontx)
def save_fontx(fonts, outstream, where=None, endianness:str='little'):
    """Save font to fontx file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to fontx file.')
    font, = fonts
    endian = endianness[0].lower()
    fontx_props, fontx_glyphs = _convert_to_fontx(font)
    logging.info('fontx properties:')
    for line in str(fontx_props).splitlines():
        logging.info('    ' + line)
    _write_fontx(outstream, fontx_props, fontx_glyphs, endian)


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
    data = instream.read()
    sbcs_header = _SBCS_HEADER.from_bytes(data)
    ofs = sbcs_header.size
    if sbcs_header.magic != _FONTX_MAGIC:
        raise FileFormatError(
            'Not a FONTX file: '
            f'incorrect magic `{header.magic}` != {_FONTX_MAGIC}'
        )
    bytewidth = ceildiv(sbcs_header.width, 8)
    bytesize = bytewidth * sbcs_header.height
    logging.debug(bytesize)
    props = vars(sbcs_header)
    if not sbcs_header.code_flag:
        glyphs = tuple(
            Glyph.from_bytes(
                data[ofs+_cp*bytesize:ofs+(_cp+1)*bytesize],
                width=sbcs_header.width,
                codepoint=_cp
            )
            for _cp in range(0, 256)
        )
    else:
        dbcs_header = _DBCS_HEADER.from_bytes(data, ofs)
        props.update(vars(dbcs_header))
        blocks = _BLOCK_OFFSET.array(dbcs_header.n_blocks).from_bytes(
            data, ofs + dbcs_header.size
        )
        ofs += dbcs_header.size + blocks.size
        block_offs = (0, ) + tuple(accumulate(
            (_entry.end-_entry.start+1)*bytesize
            for _entry in blocks
        ))
        glyphs = tuple(
            Glyph.from_bytes(
                data[ofs+_ofs+_i*bytesize:ofs+_ofs+(_i+1)*bytesize],
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
        name=fontx_props.name.decode('ascii', 'ignore'),
        encoding='ms-shift-jis'
    )
    return props
