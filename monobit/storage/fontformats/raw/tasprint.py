"""
monobit.storage.fontformats.raw.tasprint - TasPrint fonts

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# format described by John Elliott at https://www.seasip.info/ZX/tasprint.html

import logging

from monobit.storage import loaders, savers, Magic
from monobit.base import FileFormatError
from monobit.core import Raster, Glyph, Font, Char
from monobit.base.struct import little_endian as le

from .raw import load_bitmap, save_bitmap
from .plus3dos import _PLUS3DOS_HEADER, _PLUS3DOS_MAGIC
from monobit.storage.utils.limitations import ensure_charcell


@loaders.register(
    name='tasprint',
    patterns=('tasfont0', 'font.obj'),
)
def load_tasprint(
        instream,
        count:int=96, n_cols:int=10, width:int=None,
        first_codepoint:int=32
    ):
    """
    Load TasPrint fonts.

    count: number of glyphs per font (default: 96)
    n_cols: number of columns per glyph definition (default: 10)
    width: actual glyph width <= n_cols (default: same as n_cols)
    first-codepoint: first codepoint in each font (default: 32)
    """
    fonts = []
    while len(instream.peek(1)) > 0:
        logging.debug('reading strike')
        try:
            font = _read_tasprint_strike(
                instream, count, n_cols, width=width,
                first_codepoint=first_codepoint,
            )
        except ValueError:
            break
        font = font.label(char_from='ascii')
        fonts.append(font)
    return fonts


@loaders.register(
    name='tas3dos',
    # signature, issue==1, version==0, file_size=0xc82, file_type==3, data_length==3074, load_addr=30000
    magic=(_PLUS3DOS_MAGIC + b'\1\0\x82\x0c\0\0\3\2\x0c\x30\x75',),
)
def load_tasprint_3dos(instream):
    """Load TasPrint 16x16 fonts with 3dos header."""
    header = _PLUS3DOS_HEADER.read_from(instream)
    width = int(le.int16.read_from(instream))
    logging.debug(header)
    if header.signature != _PLUS3DOS_MAGIC:
        raise FileFormatError(
            f'Not a +3DOS file: incorrect signature {header.signature}.'
        )
    if header.file_type != 3 or header.data_length != 3047 or header.param1 != 30000:
        logging.warning('+3DOS header values are not consistent with TasPrint file.')
    font = _read_tasprint_strike(instream, 96, 16, width)
    font = font.label(char_from='ascii')
    return font


@loaders.register(
    name='tascpc',
    # filetype==2, logical_length==5120, data_location==22240
    magic=(
        Magic.offset(18) + b'\2' + Magic.offset(2) + b'\xe0\x56' + Magic.offset(1) + b'\0\x14',
    ),
)
def load_tasprint_cpc(instream):
    """Load TasPrint 16x16 fonts with AMSDOS header."""
    header = _AMSDOS_HEADER.read_from(instream)
    logging.debug(header)
    if header.file_type != 2 or header.logical_length != 5120:
        logging.warning('AMSDOS header values are not consistent with TasPrint file.')
    font = _read_tasprint_strike(instream, 256, 10, first_codepoint=0)
    font = font.label(char_from='tasprint')
    return font


@savers.register(linked=load_tasprint)
def save_tasprint(fonts, outstream):
    """Save a TasPrint font."""
    for font in fonts:
        font = ensure_charcell(font)
        if font.cell_size.x > 16:
            raise FileFormatError(
                'TasPrint format can only store fonts with cell-size.x <= 16;'
                f' this font has cell-size={font.cell_size}.'
            )
        if font.cell_size.y != 16:
            raise FileFormatError(
                'TasPrint format can only store fonts with cell-size.y == 16;'
                f' this font has cell-size={font.cell_size}.'
            )
        font = font.resample(
            chars=(Char(chr(_c)) for _c in range(32, 128)),
            missing=font.get_glyph(' '),
        )
        rasters = tuple(_g.pixels for _g in font.glyphs)
        tops = (_r.crop(bottom=8).transpose() for _r in rasters)
        bottoms = (_r.crop(top=8).transpose() for _r in rasters)
        for top, bot in zip(tops, bottoms):
            outstream.write(top.as_bytes())
            outstream.write(bot.as_bytes())




###############################################################################

# https://www.cpcwiki.eu/index.php/AMSDOS_Header
_AMSDOS_HEADER = le.Struct(
    user_number='uint8',
    filename='8s',
    extension='3s',
    zero='uint32',
    block_number='uint8',
    last_block='uint8',
    file_type='uint8',
    data_length='uint16',
    data_location='uint16',
    first_block='uint8',
    logical_length='uint16',
    entry_address='uint16',
    unused0='36s',
    # uint24le real_length
    real_length_lo='uint16',
    real_length_hi='uint8',
    checksum='uint16',
    unused1='59s',
)


def _read_tasprint_strike(instream, n_glyphs, n_cols, width=None, first_codepoint=32):
    size = n_glyphs * n_cols * 2
    data = instream.read(size)
    rasters = tuple(
        Raster.from_bytes(
            data[_i*n_cols : (_i+1)*n_cols],
            8, n_cols,
        ).transpose()
        for _i in range(n_glyphs*2)
    )
    if width:
        rasters = tuple(_r.crop(right=n_cols-width) for _r in rasters)
    tops = rasters[::2]
    bottoms = rasters[1::2]
    glyphs = (
        Glyph(Raster.stack(_t, _b), codepoint=_cp)
        for _cp, (_t, _b) in enumerate(zip(tops, bottoms), first_codepoint)
    )
    font = Font(glyphs)
    return font
