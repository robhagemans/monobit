"""
monobit.storage.formats.raw.nearlyraw - almost raw binary font files

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic, FileFormatError
from monobit.core import Glyph, Font
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap, save_bitmap


###############################################################################
# OPTIKS PCR - near-raw format
# http://fileformats.archiveteam.org/wiki/PCR_font
# http://cd.textfiles.com/simtel/simtel20/MSDOS/GRAPHICS/OKF220.ZIP
# OKF220.ZIP → OKFONTS.ZIP → FONTS.DOC - Has an overview of the format.
# > I have added 11 bytes to the head of the file
# > so that OPTIKS can identify it as a font file. The header has
# > a recognition pattern, OPTIKS version number and the size of
# > the font file.


_PCR_HEADER = le.Struct(
    magic='7s',
    # maybe it's a be uint16 of the file size, followed by the same size as le
    # anyway same difference
    height='uint8',
    zero='uint8',
    bytesize='uint16',
)

@loaders.register(
    name='pcr',
    magic=(b'KPG\1\2\x20\1', b'KPG\1\1\x20\1'),
    patterns=('*.pcr',),
)
def load_pcr(instream):
    """Load an OPTIKS .PCR font."""
    header = _PCR_HEADER.read_from(instream)
    font = load_bitmap(instream, width=8, height=header.height, count=256)
    font = font.modify(source_format='Optiks PCR')
    return font


###############################################################################
# REXXCOM Font Mania
# raw bitmap with DOS .COM header
# http://fileformats.archiveteam.org/wiki/Font_Mania_(REXXCOM)

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

@loaders.register(
    name='mania',
    magic=(Magic.offset(8) + b'FONT MANIA, VERSION',),
    patterns=('*.com',),
)
def load_mania(instream):
    """Load a REXXCOM Font Mania font."""
    header = _FM_HEADER.read_from(instream)
    logging.debug('Version string %r', header.version_string.decode('latin-1'))
    instream.read(header.bitmap_offset - _FM_HEADER.size)
    font = load_bitmap(
        instream,
        width=8, height=header.bitmap_size//256,
        count=256
    )
    font = font.modify(source_format='DOS loader (REXXCOM Font Mania)')
    return font


###############################################################################
# Fontraption
# raw bitmap with DOS .COM header, plain or TSR
# https://github.com/viler-int10h/Fontraption/blob/master/FORMATS.inc

_FRAPT_SIG = b'VILE\x1a'

_FRAPT_HEADER = le.Struct(
    magic='5s',
    loader_0='16s',
    height='uint8',
    loader_1='3s',
)
@loaders.register(
    name='frapt',
    magic=(_FRAPT_SIG,),
    patterns=('*.com',),
)
def load_frapt(instream):
    """Load a Fontraption plain .COM font."""
    header = _FRAPT_HEADER.read_from(instream)
    if header.magic != _FRAPT_SIG:
        raise FileFormatError(
            f'Not a Fontraption .COM file: incorrect signature {header.magic}.'
        )
    font = load_bitmap(instream, width=8, height=header.height)
    font = font.modify(source_format='DOS loader (Fontraption)')
    return font

@loaders.register(
    name='frapt-tsr',
    magic=(b'\xe9\x60',),
    patterns=('*.com',),
)
def load_frapt_tsr(instream):
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
    font = load_bitmap(instream, width=8, height=height, count=256)
    font = font.modify(source_format='DOS TSR (Fontraption)')
    return font


###############################################################################
# FONTEDIT loader

_FONTEDIT_SIG = b'\xeb\x33\x90\r   \r\n PC Magazine \xfe Michael J. Mefford\0\x1a'

@loaders.register(
    name='fontedit',
    magic=(_FONTEDIT_SIG,),
    patterns=('*.com',),
)
def load_fontedit(instream):
    """Load a FONTEDIT .COM font."""
    sig = instream.read(99)
    if not sig.startswith(_FONTEDIT_SIG):
        raise FileFormatError(
            'Not a FONTEDIT .COM file: incorrect signature '
            f'{sig[:len(_FONTEDIT_SIG)]}.'
        )
    height = sig[50]
    font = load_bitmap(instream, width=8, height=height, count=256)
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
    name='psfcom',
    magic=(
        b'\xeb\x04\xeb\xc3' + Magic.offset(11) + _PSFCOM_SIG08,
        b'\xeb\x04\xeb\xc3' + Magic.offset(11) + _PSFCOM_SIG16,
    ),
    patterns=('*.com',),
)
def load_psfcom(instream, first_codepoint:int=0):
    """
    Load a PSFCOM font.

    first_codepoint: first codepoint in file (default: 0)
    """
    header = _PSFCOM_HEADER.read_from(instream)
    logging.debug('Version string %r', header.sig.decode('latin-1'))
    if header.sig == _PSFCOM_SIG16:
        height = 16
    else:
        height = 8
    instream.read(header.address - _PSFCOM_HEADER.size - 0x100)
    font = load_bitmap(
        instream, width=8, height=height, first_codepoint=first_codepoint
    )
    font = font.modify(
        source_format='Amstrad/Spectrum CP/M loader (PSFCOM)',
        encoding='amstrad-cpm-plus',
    )
    font = font.label()
    return font


@loaders.register(
    name='letafont',
    magic=(
        bytes.fromhex('210e 0111 90e2 0164 08ed b0c3 90e2 2a01'),
    ),
    patterns=('*.com',),
)
def load_letafont(instream):
    """Load a LETAFONT font."""
    instream.read(44)
    font = load_bitmap(
        instream, width=8, height=8, count=256
    )
    font = font.modify(
        source_format='Amstrad/Spectrum CP/M loader (LETAFONT)',
        encoding='amstrad-cpm-plus',
    )
    font = font.label()
    return font


@loaders.register(
    name='udg',
    magic=(
        bytes.fromhex('210e 0111 2ce2 0134 08ed b0c3 2ce2 2a01'),
    ),
    patterns=('*.com',),
)
def load_letafont(instream):
    """Load a UDG .COM font."""
    instream.read(114)
    font = load_bitmap(
        instream, width=8, height=8, count=256
    )
    font = font.modify(
        source_format='Amstrad/Spectrum CP/M loader (UDG)',
        encoding='amstrad-cpm-plus',
    )
    font = font.label()
    return font



###############################################################################
# XBIN font section
# https://web.archive.org/web/20120204063040/http://www.acid.org/info/xbin/x_spec.htm

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

@loaders.register(
    name='xbin',
    magic=(_XBIN_MAGIC,),
    patterns=('*.xb',),
)
def load_xbin(instream):
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
    font = load_bitmap(instream, width=8, height=height, count=count)
    font = font.modify(source_format='XBIN')
    return font


@savers.register(linked=load_xbin)
def save_xbin(fonts, outstream):
    """Save an XBIN font."""
    font, *extra = fonts
    if extra:
        raise ValueError('Can only save a single font to an XBIN file')
    if font.spacing != 'character-cell' or font.cell_size.x != 8:
        raise ValueError(
            'This format can only store 8xN character-cell fonts'
        )
    codepoints = font.get_codepoints()
    if not codepoints:
        raise ValueError('No storable codepoints found in font.')
    max_cp = max(int(_cp) for _cp in codepoints)
    if max_cp >= 512:
        logging.warning('Glyphs above codepoint 512 will not be stored.')
    blank = Glyph.blank(width=8, height=font.cell_size.y)
    if max_cp >= 256:
        count = 512
    else:
        count = 256
    glyphs = (font.get_glyph(_cp, missing=blank) for _cp in range(count))
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

_DRHALO_SIG = b'AH'

@loaders.register(
    name='drhalo',
    magic=(_DRHALO_SIG,),
    patterns=('*.fon',),
)
def load_drhalo(instream, first_codepoint:int=0):
    """Load a Dr Halo / Dr Genius .FON font."""
    start = instream.read(16)
    if not start.startswith(_DRHALO_SIG):
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: incorrect signature '
            f'{start[:len(_DRHALO_SIG)]}.'
        )
    width = int(le.int16.read_from(instream))
    height = int(le.int16.read_from(instream))
    if not height or not width:
        raise FileFormatError(
            'Not a Dr. Halo bitmap .FON: may be stroked format.'
        )
    font = load_bitmap(
        instream, width=width, height=height, first_codepoint=first_codepoint,
    )
    font = font.modify(source_format='Dr. Halo')
    return font



###############################################################################
# Hercules Write On! printing utility
# supplied with Hercules InColor utilities disk
# quotes are from the Write On! README section on the CVF.EXE conversion utility
# see also https://www.seasip.info/Unix/PSF/index.html

_WOF_MAGIC = b'\x45\x53\x01\x00'
_WOF_HEADER = le.Struct(
    magic=le.uint8 * 4,
    # header size
    size='uint16',
    # > Char Width is the width of the characters in the font,
    # > expressed in pixels.  This value must be a multiple of 8.
    char_width='uint16',
    # > Char Height is the height of the characters in the font,
    # > expressed in pixels.  This value must be a multiple of 14.
    char_height='uint16',
    # > Tile Height must always be 14 for Write On!  (When Write On!
    # > displays characters that are taller than 14 dots or wider than
    # > 8 dots, it assembles them from two or more 8 x 14 tiles, mosaic
    # > fashion.)
    tile_height='uint16',
    # > Dest Min Char is the ASCII code of the first character in the
    # > destination font (.WOF) file
    min_char='uint16',
    # > Dest Max Char is the ASCII code of the last character in the
    # > destination font (.WOF)
    max_char='uint16',
    unknown_0='uint16',
    maybe_width_too='uint16',
    unknown_1='uint16',
)

@loaders.register(
    name='writeon',
    magic=(_WOF_MAGIC,),
    patterns=('*.wof',),
)
def load_writeon(instream):
    """Load a Write On! font."""
    header = _WOF_HEADER.read_from(instream)
    if bytes(header.magic) != _WOF_MAGIC:
        raise FileFormatError(
            'Not a Hercules Write On! file: '
            f'incorrect signature {bytes(header.magic)}.'
        )
    font = load_bitmap(
        instream,
        width=header.char_width, height=header.char_height,
        first_codepoint=header.min_char,
        count=header.max_char-header.min_char+1,
    )
    font = font.modify(source_format='Hercules Write On!')
    font = font.label(char_from='ascii')
    return font


@savers.register(linked=load_writeon)
def save_writeon(fonts, outstream):
    """Save a Write On! font."""
    font, *extra = fonts
    if extra:
        raise ValueError('Can only save a single font to a Write On! file')
    if font.spacing != 'character-cell':
        raise ValueError(
            'This format can only store character-cell fonts'
        )
    # get contiguous range of glyphs
    min_char = int(min(font.get_codepoints()))
    max_char = int(max(font.get_codepoints()))
    max_char = min(0x7f, max_char)
    font = font.resample(
        codepoints=range(min_char, max_char+1),
        missing=font.get_glyph(' '),
    )
    header = _WOF_HEADER(
        magic=le.uint8.array(4)(*_WOF_MAGIC),
        size=_WOF_HEADER.size,
        char_width=font.cell_size.x,
        char_height=font.cell_size.y,
        # > Tile Height must always be 14 for Write On!
        tile_height=14,
        min_char=min_char,
        max_char=max_char,
        maybe_width_too=font.cell_size.x,
    )
    outstream.write(bytes(header))
    save_bitmap(outstream, font)


###############################################################################
# 64C - two unknown bytes plus 8x8 raw in c64 order (upper- or lowercase)
# I haven't found a sepcification
# large collection of sample files at https://home-2002.code-cop.org/c64/index.html#char

@loaders.register(
    name='64c',
    patterns=('*.64c',),
    # maybe-magic b'\0\x38', b'\0\x20' most comon, but many others occur
)
def load_64c(instream, charset:str='upper'):
    """
    Load a 64C font.

    charset: 'upper' for c64 uppercase & graphical, 'lower' for lowercase & uppercase, '' for not specified
    """
    # the second byte is likely a flag, the first is almost always null
    null = instream.read(1)
    unknown_flags = instream.read(1)
    if null != b'\0':
        logging.warning(f'Non-null first byte %s.', null)
    font = load_bitmap(
        instream,
        width=8, height=8,
    )
    if charset == 'upper':
        font = font.label(char_from='c64')
    elif charset == 'lower':
        font = font.label(char_from='c64-alternate')
    font = font.modify(source_format='64c')
    return font


@savers.register(linked=load_64c)
def save_64c(fonts, outstream):
    """Save a 64C font."""
    font, *extra = fonts
    if extra:
        raise ValueError('Can only save a single font to a 64c file')
    if font.spacing != 'character-cell' or font.cell_size != (8, 8):
        raise ValueError(
            'This format can only store 8x8 character-cell fonts'
        )
    # not an actual magic sequence. we also see \0\x20 \0\x30 \0\x48 \0\xc8
    outstream.write(b'\x00\x38')
    save_bitmap(outstream, font)
