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
# v3 http://jphdupre.chez-alice.fr/chiwriter/technic3/gcw3v01.html#pagev09
# v4 http://jphdupre.chez-alice.fr/chiwriter/manuel4/mcw4-155.html#page158
# we use the v4 field names here

_HEADER = le.Struct(
    # [0] 0x10 for cw3 files, 0x11 for cw4
    filetype='uint8',
    # [1] 8.3 null-terminated
    filename='13s',
    # [14] often 0xBA==186 in filetype==0x10, usually 0 in 0x11
    unused1='uint8',
    # [15] baseline, counting from the top
    baseline='uint8',
    # [16] number of stored glyphs
    numchars='uint8',
    # [17] first codepoint, add 0x20
    firstchar='uint8',
    # [18] unused?
    proportional='uint8',
    # [19] glyph raster dimensions
    hsize='uint8',
    vsize='uint8',
    # [21] not sure hat this means, leading? usually 0 in CW files
    baseshift='uint8',
    # [22] 'width of space' (v3) 'defaultwidth' (v4)
    defaultwidth='uint8',
    # [23]
    unused2=struct.uint8,
    # [24] this is used in v3 files but unclear what for
    unknown='uint8',
    # [25]
    unused3=struct.uint8 * 7,
    # [32] seems unused
    copyright='56s',
)
_WIDTH_OFFSET_V3 = 0xFA
_BITMAP_OFFSET = 0x158


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
    if (version == 4) or (version is None and header.filetype == 0x11):
        woffset = 120 + header.firstchar
    elif version in (3, None):
        woffset = _WIDTH_OFFSET_V3
    else:
        raise ValueError(f'Version must be 3 or 4, not `{version}`.')
    widths = le.uint8.array(header.numchars).from_bytes(data, woffset)
    logging.debug(widths)
    shift_up = -(header.vsize-header.baseline) if header.baseline else None
    glyphs = [Glyph.blank(
        width=header.hsize, height=header.vsize,
        right_bearing=(header.defaultwidth or header.hsize) - header.hsize,
        shift_up=shift_up,
        codepoint=0x20,
    )]
    bytesize = ceildiv(header.hsize, 8)*header.vsize
    # bitmap offset
    boffset = _BITMAP_OFFSET
    glyphs.extend(
        Glyph.from_bytes(
            data[boffset+_i*bytesize:boffset+(_i+1)*bytesize],
            width=header.hsize,
            # width table may hold zeros which means full-width
            right_bearing=(_wid or header.hsize)-header.hsize,
            codepoint=_i+0x20+header.firstchar,
            shift_up=shift_up,
        )
        for _i, _wid in enumerate(widths)
    )
    glyphs = [
        _g.crop(right=max(0, -_g.right_bearing)).drop('shift-left')
        for _g in glyphs
    ]
    font = Font(
        glyphs,
        source_format=f'ChiWriter ({header.filetype:#02x})',
        name=header.filename.decode('latin-1').split('.')[0],
        font_id=header.filename.decode('latin-1'),
    )
    return font
