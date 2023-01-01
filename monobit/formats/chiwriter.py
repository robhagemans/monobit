"""
monobit.formats.chiwriter - ChiWriter font files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from .. import struct
from ..struct import little_endian as le
from ..binary import ceildiv
from .raw import load_binary


###############################################################################
# ChiWriter format
# based on reverse-engineering guesswork

_HEADER = le.Struct(
    # 0x10 for cw3 files, 0x11 for cw4
    version='uint8',
    # 8.3 null-terminated
    filename='13s',
    # often 0xBA==186 in version==0x10, often 0 in 0x11
    unknown='uint8',
    # or maybe point-size? e.g. 6 for SFT, 16 for PFT/EFT, 22 for XFT,
    # 35 for LFT,
    resolution='uint8',
    # number of stored glyphs
    count='uint8',
    # first codepoint, add 0x20
    code_start='uint8',
    # always zero? or part of a uint16 field?
    zero0='uint8',
    # glyph raster dimensions
    width='uint8',
    height='uint8',
    # always zero? or part of a uint16 field?
    zero1='uint8',
    # advance width of space character
    space_width='uint8',
    # always zero? or part of a uint16 field?
    zero2='uint8',
    # seems to be always zero in v. 0x11 but used in v. 0x10
    unknown1='uint8'
)

# magic 0x10 or 0x11 is a bit too generic
@loaders.register(
    'cft', 'eft', 'lft', 'mft', 'nft', 'pft', 'sft', 'xft',
    name='chiwriter'
)
def load_chiwriter(instream, where=None, version:int=None):
    """
    Load a ChiWriter font.

    version: file format version; 3 or 4. None (default) to detect from file.
    """
    data = instream.read()
    header = _HEADER.from_bytes(data)
    logging.debug(header)
    # locate width table
    # this is not correct for prisca/EBOLD.LFT which has 0x10
    # but follows the first scheme. maybe only PFT and SFT follow this?
    if (version == 4) or (version is None and header.version == 0x11):
        woffset = 120 + header.code_start
    elif version in (3, None):
        woffset = 250
    else:
        raise ValueError(f'Version must be 2 or 3, not `{version}`.')
    widths = le.uint8.array(header.count).from_bytes(data, woffset)
    logging.debug(widths)
    glyphs = [Glyph.blank(
        width=header.width, height=header.height,
        right_bearing=(header.space_width or header.width) - header.width,
        codepoint=0x20,
    )]
    bytesize = ceildiv(header.width, 8)*header.height
    # bitmap offset
    boffset = 344
    glyphs.extend(
        Glyph.from_bytes(
            data[boffset+_i*bytesize:boffset+(_i+1)*bytesize],
            width=header.width,
            # width table may hold zeros which means full-width
            right_bearing=(_wid or header.width)-header.width,
            codepoint=_i+0x20+header.code_start,
        )
        for _i, _wid in enumerate(widths)
    )
    glyphs = [
        _g.crop(right=max(0, -_g.right_bearing)).drop('shift-left')
        for _g in glyphs
    ]
    font = Font(
        glyphs,
        source_format=f'ChiWriter ({header.version:#02x})',
        name=header.filename.decode('latin-1').split('.')[0],
        font_id=header.filename.decode('latin-1'),
    )
    return font
