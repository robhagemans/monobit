"""
monobit.formats.nearlyraw - almost raw binary font files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from ..storage import loaders, savers
from ..glyph import Glyph
from ..font import Font
from ..struct import little_endian as le, bitfield
from ..magic import Magic, FileFormatError

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
