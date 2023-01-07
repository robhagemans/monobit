"""
monobit.formats.raw - raw binary font files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import zip_longest

from ..binary import ceildiv, bytes_to_bits
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..streams import FileFormatError
from ..basetypes import Coord


@loaders.register('bin', 'rom', name='raw')
def load_binary(
        instream, where=None, *,
        cell:Coord=(8, 8), count:int=-1, offset:int=0, padding:int=0,
        align:str='left', strike_count:int=1, strike_bytes:int=-1,
        first_codepoint:int=0
    ):
    """
    Load character-cell font from binary bitmap.

    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyph rows (default: 0)
    count: number of glyphs to extract (<= 0 means all; default: all)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    align: alignment of strike row ('left' for most-, 'right' for least-significant; 'bit' for bit-aligned; default: 'left')
    first_codepoint: first code point in bitmap (default: 0)
    """
    width, height = cell
    # get through the offset
    # we don't assume instream is seekable - it may be sys.stdin
    instream.read(offset)
    return load_bitmap(
        instream, width, height, count, padding, align, strike_count, strike_bytes, first_codepoint
    )

@savers.register(linked=load_binary)
def save_binary(
        fonts, outstream, where=None, *,
        strike_count:int=1, align:str='left', padding:int=0,
    ):
    """
    Save character-cell fonts to binary bitmap.

    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    align: alignment of strike row ('left' for most-, 'right' for least-significant; 'bit' for bit-aligned; default: 'left')
    padding: number of bytes between encoded glyph rows (default: 0)
    """
    for font in fonts:
        save_bitmap(
            outstream, font,
            strike_count=strike_count, align=align, padding=padding
        )


###############################################################################
# raw 8x14 format
# CHET .814 - http://fileformats.archiveteam.org/wiki/CHET_font

@loaders.register('814', name='8x14')
def load_chet(instream, where=None):
    """Load a raw 8x14 font."""
    return load_binary(instream, where, cell=(8, 14))


###############################################################################
# raw 8x8 format
# https://www.seasip.info/Unix/PSF/Amstrad/UDG/index.html

@loaders.register('64c', 'udg', 'ch8', name='8x8')
def load_8x8(instream, where=None):
    """Load a raw 8x8 font."""
    return load_binary(instream, where, cell=(8, 8))

# https://www.seasip.info/Unix/PSF/Amstrad/Genecar/index.html
# GENECAR included three fonts in a format it calls .CAR. This is basically a
# raw dump of the font, but using a 16×16 character cell rather than the usual 16×8.
@loaders.register('car', name='16x16')
def load_16x16(instream, where=None):
    """Load a raw 16x16 font."""
    return load_binary(instream, where, cell=(16, 16))


###############################################################################
# raw 8xN format with height in suffix
# guess we won't have them less than 4 or greater than 32

from pathlib import PurePath

_F_SUFFIXES = tuple(f'f{_height:02}' for _height in range(4, 33))

@loaders.register(*_F_SUFFIXES, name='8xn')
def load_8xn(instream, where=None):
    """Load a raw 8xN font."""
    suffix = PurePath(instream.name).suffix
    try:
        height = int(suffix[2:])
    except ValueError:
        height=8
    return load_binary(instream, where, cell=(8, height))


###############################################################################
# raw formats we can't easily recognise from suffix or magic

# degas elite .fnt, 8x16x128, + flags, 2050 bytes https://temlib.org/AtariForumWiki/index.php/DEGAS_Elite_Font_file_format
# warp 9 .fnt, 8x16x256 + flags, 4098 bytes https://temlib.org/AtariForumWiki/index.php/Warp9_Font_file_format
# however not all have the extra word

# Harlekin III .fnt - "Raw font data line by line, 8x8 (2048 bytes) or 8x16 (4096 bytes) only."
# https://temlib.org/AtariForumWiki/index.php/Fonts
# i.e. this is a wide-strike format, load width -strike-count=-1


###############################################################################
# OPTIKS PCR - near-raw format
# http://fileformats.archiveteam.org/wiki/PCR_font
# http://cd.textfiles.com/simtel/simtel20/MSDOS/GRAPHICS/OKF220.ZIP
# OKF220.ZIP → OKFONTS.ZIP → FONTS.DOC - Has an overview of the format.
# > I have added 11 bytes to the head of the file
# > so that OPTIKS can identify it as a font file. The header has
# > a recognition pattern, OPTIKS version number and the size of
# > the font file.

from ..struct import little_endian as le

_PCR_HEADER = le.Struct(
    magic='7s',
    # maybe it's a be uint16 of the file size, followed by the same size as le
    # anyway same difference
    height='uint8',
    zero='uint8',
    bytesize='uint16',
)

@loaders.register('pcr', name='pcr', magic=(b'KPG\1\2\x20\1', b'KPG\1\1\x20\1'))
def load_pcr(instream, where=None):
    """Load an OPTIKS .PCR font."""
    header = _PCR_HEADER.read_from(instream)
    font = load_binary(instream, where, cell=(8, header.height), count=256)
    font = font.modify(source_format='Optiks PCR')
    return font



###############################################################################
# REXXCOM Font Mania
# raw bitmap with DOS .COM header
# http://fileformats.archiveteam.org/wiki/Font_Mania_(REXXCOM)

from ..struct import little_endian as le

# guessed by inspection, with reference to Intel 8086 opcodes
_FM_HEADER = le.Struct(
    # JMP SHORT opcode 0xEB
    jmp='uint8',
    # signed jump target - 0x4b or 0x4e
    code_offset='int8',
    bitmap_offset='uint16',
    bitmap_size='uint16',
    # seems to be always 0x2000 le, i.e. b'\0x20'.
    nul_space='2s',
    version_string='62s',
    # 'FONT MANIA, VERSION 1.0 \r\n COPYRIGHT (C) REXXCOM SYSTEMS, 1991'
    # 'FONT MANIA, VERSION 2.0 \r\n COPYRIGHT (C) REXXCOM SYSTEMS, 1991'
    # 'FONT MANIA, VERSION 2.2 \r\n COPYRIGHT (C) 1992  REXXCOM SYSTEMS'
)

# the version string would be a much better signature, but we need an offset
@loaders.register(
    #'com',
    name='mania', magic=(b'\xEB\x4D', b'\xEB\x4E', b'\xEB\x47\xA2\x05')
)
def load_mania(instream, where=None):
    """Load a REXXCOM Font Mania font."""
    header = _FM_HEADER.read_from(instream)
    logging.debug('Version string %r', header.version_string.decode('latin-1'))
    font = load_binary(
        instream, where,
        offset=header.bitmap_offset - _FM_HEADER.size,
        cell=(8, header.bitmap_size//256),
        count=256
    )
    font = font.modify(source_format='DOS loader (REXXCOM Font Mania)')
    return font


###############################################################################
# Fontraption
# raw bitmap with DOS .COM header, plain or TSR
# https://github.com/viler-int10h/Fontraption/blob/master/FORMATS.inc

from ..struct import little_endian as le

_FRAPT_SIG = b'VILE\x1a'

_FRAPT_HEADER = le.Struct(
    magic='5s',
    loader_0='16s',
    height='uint8',
    loader_1='3s',
)
@loaders.register(
    #'com',
    name='frapt', magic=(_FRAPT_SIG,)
)
def load_frapt(instream, where=None):
    """Load a Fontraption plain .COM font."""
    header = _FRAPT_HEADER.read_from(instream)
    if header.magic != _FRAPT_SIG:
        raise FileFormatError(
            f'Not a Fontraption .COM file: incorrect signature {header.magic}.'
        )
    font = load_binary(instream, where, cell=(8, header.height))
    font = font.modify(source_format='DOS loader (Fontraption)')
    return font

@loaders.register(
    #'com',
    name='frapt-tsr', magic=(b'\xe9\x60',)
)
def load_frapt_tsr(instream, where=None):
    """Load a Fontraption TSR .COM font."""
    instream.seek(0x28)
    sig = instream.read(5)
    if sig != _FRAPT_SIG:
        raise FileFormatError(
            f'Not a Fontraption .COM file: incorrect signature {sig}.'
        )
    instream.seek(0x5d)
    height, = instream.read(1)
    instream.seek(0x63)
    font = load_binary(instream, where, cell=(8, height), count=256)
    font = font.modify(source_format='DOS TSR (Fontraption)')
    return font

###############################################################################
# FONTEDIT loader

_FONTEDIT_SIG = b'\xeb\x33\x90\r   \r\n PC Magazine \xfe Michael J. Mefford\0\x1a'

@loaders.register(
    #'com',
    name='fontedit', magic=(_FONTEDIT_SIG,)
)
def load_fontedit(instream, where=None):
    """Load a FONTEDIT .COM font."""
    sig = instream.read(99)
    if not sig.startswith(_FONTEDIT_SIG):
        raise FileFormatError(
            'Not a FONTEDIT .COM file: incorrect signature '
            f'{sig[:len(_FONTEDIT_SIG)]}.'
        )
    height = sig[50]
    font = load_binary(instream, where, cell=(8, height), count=256)
    font = font.modify(source_format='DOS loader (FONTEDIT)')
    return font


###############################################################################
# psftools PSF2AMS font loader
# raw bitmap with Z80 CP/M loader, prefixed with a DOS stub, 512-bytes offset
# https://github.com/ZXSpectrumVault/john-elliot/blob/master/psftools/tools/psf2ams.c
# /* Offsets in PSFCOM:
#  * 0000-000E  Initial code
#  * 000F-002D  Signature
#  * 002E-002F  Length of font, bytes (2k or 4k)
#  * 0030-0031  Address of font */

#_PSFCOM_STUB = bytes.fromhex('eb04 ebc3 ???? b409 ba32 01cd 21cd 20')
_PSFCOM_SIG08 = b'\rFont converted with PSF2AMS\r\n\032'
_PSFCOM_SIG16 = b'\rFont Converted with PSF2AMS\r\n\032'
_PSFCOM_HEADER = le.Struct(
    code='15s',
    sig='31s',
    bitmap_size='uint16',
    # apparently the offset to the space char, but 0-31 are defined before that
    # so this is the offset - 0x100 ?
    address='uint16',
)

@loaders.register(
    #'com',
    name='psfcom',
    magic=(b'\xeb\x04\xeb\xc3',)
)
def load_psfcom(instream, where=None):
    """Load a PSFCOM font."""
    header = _PSFCOM_HEADER.read_from(instream)
    logging.debug('Version string %r', header.sig.decode('latin-1'))
    if header.sig == _PSFCOM_SIG16:
        height = 16
    else:
        height = 8
    font = load_binary(
        instream, where,
        offset=header.address - _PSFCOM_HEADER.size - 0x100,
        cell=(8, height),
    )
    font = font.modify(
        source_format='Amstrad/Spectrum CP/M loader (PSFCOM)',
        encoding='amstrad-cpm-plus',
    )
    font = font.label()
    return font



###############################################################################
# XBIN font section
# https://web.archive.org/web/20120204063040/http://www.acid.org/info/xbin/x_spec.htm

from ..struct import little_endian as le, bitfield

_XBIN_MAGIC = b'XBIN\x1a'
_XBIN_HEADER = le.Struct(
    magic='5s',
    # Width of the image in character columns.
    width='word',
    # Height of the image in character rows.
    height='word',
    # Number of pixel rows (scanlines) in the font, Default value for VGA is 16.
    # Any value from 1 to 32 is technically possible on VGA. Any other values
    # should be considered illegal.
    fontsize='byte',
    # A set of flags indicating special features in the XBin file.
    # 7 6 5  4        3        2        1    0
    # Unused 512Chars NonBlink Compress Font Palette
    palette=bitfield('byte', 1),
    font=bitfield('byte', 1),
    compress=bitfield('byte', 1),
    nonblink=bitfield('byte', 1),
    has_512_chars=bitfield('byte', 1),
    unused_flags=bitfield('byte', 3)
)

@loaders.register('.xb', name='xbin', magic=(_XBIN_MAGIC,))
def load_xbin(instream, where=None):
    """Load a XBIN font."""
    header = _XBIN_HEADER.read_from(instream)
    if header.magic != _XBIN_MAGIC:
        raise FileFormatError(
            f'Not an XBIN file: incorrect signature {header.magic}.'
        )
    if not header.font:
        raise FileFormatError('XBIN file contains no font.')
    height = header.fontsize
    if header.has_512_chars:
        count = 512
    else:
        count = 256
    # skip 48-byte palette, if present
    if header.palette:
        instream.read(48)
    font = load_binary(instream, where, cell=(8, height), count=count)
    font = font.modify(source_format='XBIN')
    return font


@savers.register(linked=load_xbin)
def save_xbin(fonts, outstream, where=None):
    """Save an XBIN font."""
    font, *extra = fonts
    if extra:
        raise FileFormatError('Can only save a single font to an XBIN file')
    if font.spacing != 'character-cell' or font.cell_size.x != 8:
        raise FileFormatError(
            'This format can only store 8xN character-cell fonts'
        )
    font = font.label(codepoint_from=font.encoding)
    max_cp = max(int(_cp) for _cp in font.get_codepoints())
    if max_cp >= 512:
        logging.warning('Glyphs above codepoint 512 will not be stored.')
    blank = Glyph.blank(width=8, height=font.cell_size.y)
    if max_cp >= 256:
        count = 512
    else:
        count = 256
    glyphs = (font.get_glyph(_cp, missing=blank) for _cp in range(count))
    # TODO: take codepoint or ordinal?
    # TODO: bring to normal form
    header = _XBIN_HEADER(
        magic=_XBIN_MAGIC,
        fontsize=font.cell_size.y,
        font=1,
        has_512_glyphs=count==512,
    )
    outstream.write(bytes(header))
    font = Font(glyphs)
    save_bitmap(outstream, font)


###############################################################################
# Dr. Halo / Dr. Genius F*X*.FON

from ..struct import little_endian as le

_DRHALO_SIG = b'AH'

@loaders.register(
    #'fon',
    name='drhalo', magic=(_DRHALO_SIG,)
)
def load_drhalo(instream, where=None):
    """Load a Dr Halo / Dr Genius .FON font."""
    start = instream.read(16)
    if not start.startswith(_DRHALO_SIG):
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: incorrect signature ' f'{start[:len(_DRHALO_SIG)]}.'
        )
    width = int(le.int16.read_from(instream))
    height = int(le.int16.read_from(instream))
    if not height or not width:
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: may be stroked format.'
        )
    font = load_binary(
        instream, where, cell=(width, height),
    )
    font = font.modify(source_format='Dr. Halo')
    return font


###############################################################################
###############################################################################
# bitmap reader

def load_bitmap(
        instream, width, height, count=-1, padding=0, align='left',
        strike_count=1, strike_bytes=-1, first_codepoint=0,
    ):
    """Load fixed-width font from bitmap."""
    data, count, cells_per_row, bytes_per_row, nrows = _extract_data_and_geometry(
        instream, width, height, count, padding, strike_count, strike_bytes,
    )
    cells = _extract_cells(
        data, width, height, align, cells_per_row, bytes_per_row, nrows
    )
    # reduce to given count, if exceeded
    cells = cells[:count]
    # assign codepoints
    glyphs = tuple(
        Glyph(_cell, codepoint=_index)
        for _index, _cell in enumerate(cells, first_codepoint)
    )
    return Font(glyphs)


def _extract_data_and_geometry(
        instream, width, height, count=-1, padding=0,
        strike_count=1, strike_bytes=-1,
    ):
    """Determine geometry from defaults and data size."""
    data = None
    # determine byte-width of the bitmap strike rows
    if strike_bytes <= 0:
        if strike_count <= 0:
            data = instream.read()
            strike_bytes = len(data) // height
        else:
            strike_bytes = ceildiv(strike_count*width, 8)
    else:
        strike_count = -1
    # deteermine number of cells per strike row
    if strike_count <= 0:
        strike_count = (strike_bytes * 8) // width
    # determine bytes per strike row
    row_bytes = strike_bytes*height + padding
    # determine number of strike rows
    if count is None or count <= 0:
        if not data:
            data = instream.read()
        # get number of chars in extract
        nrows = ceildiv(len(data), row_bytes)
        count = nrows * strike_count
    else:
        nrows = ceildiv(count, strike_count)
        if not data:
            data = instream.read(nrows * row_bytes)
    # we may exceed the length of the rom because we use ceildiv, pad with nulls
    data = data.ljust(nrows * row_bytes, b'\0')
    if nrows == 0 or row_bytes == 0:
        return b'', 0, 0, 0, 0
    return data, count, strike_count, row_bytes, nrows


def _extract_cells(
        data, width, height, align, cells_per_row, bytes_per_row, nrows
    ):
    """Extract glyphs from bitmap strike with given geometry."""
    # extract one strike row at a time
    # note that the strikes may not be immediately contiguous if there's padding
    glyphrows = (
        Raster.from_bytes(
            data[_i*bytes_per_row : (_i+1)*bytes_per_row],
            width*cells_per_row, height,
            align=align
        )
        for _i in range(nrows)
    )
    # clip out glyphs
    cells = tuple(
        _glyphrow.crop(
            left=_i*width,
            right=_glyphrow.width - (_i+1)*width
        )
        for _glyphrow in glyphrows
        for _i in range(cells_per_row)
    )
    return cells


###############################################################################
###############################################################################
# bitmap writer

def save_bitmap(
        outstream, font, *,
        strike_count:int=1, align:str='left', padding:int=0,
    ):
    """
    Save character-cell font to binary bitmap.

    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    align: alignment of strike row ('left' for most-, 'right' for least-significant; 'bit' for bit-aligned; default: 'left')
    padding: number of bytes between encoded glyph rows (default: 0)
    """
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    # TODO: normalise
    # get pixel rasters
    rasters = (_g.pixels for _g in font.glyphs)
    # contruct rows (itertools.grouper recipe)
    args = [iter(rasters)] * strike_count
    grouped = zip_longest(*args, fillvalue=Glyph())
    glyphrows = (
        Raster.concatenate(*_row)
        for _row in grouped
    )
    for glyphrow in glyphrows:
        outstream.write(glyphrow.as_bytes(align=align))
        outstream.write(b'\0' * padding)
