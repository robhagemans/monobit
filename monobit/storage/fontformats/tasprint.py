"""
monobit.storage.fontformats.tasprint - TasPrint fonts

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# format described by John Elliott at https://www.seasip.info/ZX/tasprint.html

import logging

from monobit.storage import loaders, savers, Magic
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Raster, Glyph, Font, Char
from monobit.base.struct import little_endian as le

from .raw import load_bitmap, save_bitmap
from .raw.plus3dos import _PLUS3DOS_HEADER, _PLUS3DOS_MAGIC
from monobit.storage.utils.limitations import ensure_charcell, ensure_single


# +3DOS: signature, issue==1, version==0, file_size=0xc82, file_type==3, data_length==3074, load_addr=30000
_TASPRINT_P3DOS = Magic(_PLUS3DOS_MAGIC + b'\1\0\x82\x0c\0\0\3\2\x0c\x30\x75')
# AMSDOS: filetype==2, logical_length==5120
_TASPRINT_AMSDOS = (
    b'\0' + Magic.offset(11) + b'\0\0\0\0\0\0\2\0\0'
    + Magic.offset(2) + b'\0\0\x14\0\0'
    + Magic.offset(36) + b'\0\x14\0'
)

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


@loaders.register(
    name='tasprint',
    patterns=('tasfont0', 'font.obj'),
    magic=(_TASPRINT_P3DOS, _TASPRINT_AMSDOS),
)
def load_tasprint(instream, version:str=None, width:int=16):
    """
    Load TasPrint fonts.

    version: tasprint format version, one of '48k', '+3', 'cpc', 'pcw'
    width: character width (for version=`pcw`; default:16)
    """
    if version == '+3' or not version and _TASPRINT_P3DOS.fits(instream):
        logging.debug('Loading TasPrint +3 file.')
        return load_tasprint_3dos(instream)
    elif version == 'cpc' or not version and _TASPRINT_AMSDOS.fits(instream):
        logging.debug('Loading TasPrint CPC file.')
        return load_tasprint_cpc(instream)
    data = instream.read()
    if version == '48k' or len(data) % (2 * 96 * 10) == 0:
        logging.debug('Loading TasPrint 48k/QL file.')
        return parse_tasprint_48k(data)
    elif version == 'pcw' or len(data) == 2 * 128 * 16:
        logging.debug('Loading TasPrint PCW file.')
        return parse_tasprint_pcw(data, width)
    logging.debug('Could not determine tasprint version for file with length %d', len(data))


def parse_tasprint_48k(
        data,
        count:int=96, n_cols:int=10, width:int=None,
        first_codepoint:int=32
    ):
    """
    Load fonts in TasPrint format for Spectrum 48k / QL.

    count: number of glyphs per font (default: 96)
    n_cols: number of columns per glyph definition (default: 10)
    width: actual glyph width <= n_cols (default: same as n_cols)
    first-codepoint: first codepoint in each font (default: 32)
    """
    fonts = []
    bytesize = 2 * count * n_cols
    while data:
        strike, data = data[:bytesize], data[bytesize:]
        try:
            font = _read_tasprint_strike(
                strike, count, n_cols, width=width,
                first_codepoint=first_codepoint,
            )
        except ValueError:
            break
        font = font.label(char_from='ascii')
        fonts.append(font)
    return fonts


def parse_tasprint_pcw(data, width):
    """
    Load fonts in TasPrint format for Amstrad PCW.

    width: actual glyph width <= n_cols (default: 16)
    """
    font = _read_tasprint_strike(
        data, count=128, n_cols=16, width=width,
        first_codepoint=1,
    )
    font = font.label(char_from='ascii-printable')
    return font


def load_tasprint_3dos(instream):
    """Load TasPrint 16x16 fonts with 3dos header."""
    header = _PLUS3DOS_HEADER.read_from(instream)
    width = int(le.int16.read_from(instream))
    logging.debug(header)
    if header.signature != _PLUS3DOS_MAGIC:
        raise FileFormatError(
            f'Not a +3DOS file: incorrect signature {header.signature}.'
        )
    if header.file_type != 3 or header.data_length != 3074 or header.param_1 != 30000:
        logging.warning('+3DOS header values are not consistent with TasPrint file.')
    data = instream.read()
    font = _read_tasprint_strike(data, 96, 16, width)
    font = font.label(char_from='ascii')
    return font


def load_tasprint_cpc(instream):
    """Load TasPrint 10x16 fonts with AMSDOS header."""
    header = _AMSDOS_HEADER.read_from(instream)
    logging.debug(header)
    if header.file_type != 2 or header.logical_length != 5120:
        logging.warning('AMSDOS header values are not consistent with TasPrint file.')
    data = instream.read()
    font = _read_tasprint_strike(data, 256, 10, first_codepoint=0)
    font = font.label(char_from='tasprint')
    return font


@savers.register(linked=load_tasprint)
def save_tasprint(fonts, outstream, version:str='48k'):
    """
    Save a TasPrint font.

    version: tasprint format version, one of '48k', '+3', 'cpc', 'pcw'
    """
    if version == '48k':
        # ensure 10x16
        for font in fonts:
            # FIXME: glyph count must be 96
            font = ensure_charcell(font, cell_size=(10, 16))
            return _write_tasprint_strike(
                outstream, font, codepoint_range=range(32, 128)
            )
    font = ensure_single(fonts)
    font = ensure_charcell(font)
    if version == '+3':
        header = _PLUS3DOS_HEADER(
            signature=_PLUS3DOS_MAGIC,
            issue=1,
            version=0,
            file_size=3202,
            file_type=3,
            data_length=3074,
            param_1=30000,
            param_2=21506,
            checksum=18,
        )
        outstream.write(bytes(header))
        outstream.write(bytes(le.int16(font.cell_size.x)))
        codepoint_range = range(32, 128)
    elif version == 'cpc':
        font = ensure_charcell(font, cell_size=(10, 16))
        name = font.name[:8].split(' ')[0].upper().ljust(8, ' ')
        header = _AMSDOS_HEADER(
            filename=name.encode('ascii', 'ignore'),
            extension=b'DAT',
            file_type=2,
            data_length=0,
            # this number varies in every file
            data_location=22240,
            logical_length=5120,
            real_length_lo=5120,
            real_length_hi=0,
        )
        header.checksum = sum(bytes(header))
        outstream.write(bytes(header))
        codepoint_range = range(256)
    elif version == 'pcw':
        codepoint_range = range(1, 129)
    else:
        raise UnsupportedError(f'Unsupported TasPrint version `{version}`; must be one of `48k`, `+3`, `cpc`, `pcw`.')
    return _write_tasprint_strike(outstream, font, codepoint_range)



###############################################################################


def _read_tasprint_strike(data, count, n_cols, width=None, first_codepoint=32):
    logging.debug(
        'Reading TasPrint strike with %i glyphs, %i columns', count, n_cols
    )
    rasters = tuple(
        Raster.from_bytes(
            data[_i*n_cols : (_i+1)*n_cols],
            8, n_cols,
        ).transpose()
        for _i in range(count*2)
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


def _write_tasprint_strike(outstream, font, codepoint_range):
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
        chars=(Char(chr(_c)) for _c in codepoint_range),
        missing=font.get_glyph(' '),
    )
    rasters = tuple(_g.pixels for _g in font.glyphs)
    tops = (_r.crop(bottom=8).transpose() for _r in rasters)
    bottoms = (_r.crop(top=8).transpose() for _r in rasters)
    for top, bot in zip(tops, bottoms):
        outstream.write(top.as_bytes())
        outstream.write(bot.as_bytes())
