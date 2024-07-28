"""
monobit.storage.formats.raw.comloaders - executable font loaders

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, Magic, FileFormatError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield

from .raw import load_bitmap


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
# LETAFONT
# https://www.seasip.info/Unix/PSF/Amstrad/Letafont/index.html

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


###############################################################################
# UDG
# https://www.seasip.info/Unix/PSF/Amstrad/UDG/index.html

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
