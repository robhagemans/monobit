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
# font formats claiming descent from/compatibility with FONTRIX for IBM
# I have only found FONTRIX and its fonts for the Apple II
# and they are similar but incompatible (header offsets are different)

# ChiWriter format
# v3 http://jphdupre.chez-alice.fr/chiwriter/technic3/gcw3v01.html#pagev09
# v4 http://jphdupre.chez-alice.fr/chiwriter/manuel4/mcw4-155.html#page158
# we use the v4 field names here

# GRASP 'new' format
# http://fileformats.archiveteam.org/wiki/GRASP_font

# PC-PAINT

# the header definition below is based on the ChiWrriter v4 reference above
_HEADER = le.Struct(
    # [0] 0x10 for pcpaint/grasp/cw3 files, 0x11 for cw4
    filetype='uint8',
    # [1] 8.3 null-terminated
    filename='13s',
    # [14] often 0xBA==186 or 0x46==70 when filetype==0x10, usually 0 in 0x11
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
    # [21] not sure what this means, leading? usually 0 in CW files
    # from comparison with GRASP, it means the bytewidth/stride of the bitmaps
    baseshift='uint8',
    # [22] 'width of space' (v3) 'defaultwidth' (v4)
    defaultwidth='uint8',

    # here file formats diverge in their interpretation. [ChiWriter v4] gives:
    # [23]
    #unused2=struct.uint8 * 9,
    # [32] defined but seems unused
    #copyright='56s',
    # [88] table of 256 uint8 advance widths
    # which means the first entry is 88+32 + firstchar == 120 + firstchar

    # however, v3 (filetype 0x10) files use the byte at offset [24]
    # and start the width table at 250. below is from v3 spec:
    # [23] 'Space gap' is a separate field from 'Width of space'. Meaning unclear.
    space_gap='uint8',
    # [24] 'Line gap', again unclear.
    # Simplest assumption is vsize + line_gap is the distance between baselines
    # But this leads to very wide line spacing, often double-spaced.
    # Perhaps it is the distance from baseline to next raster top?
    line_gap='uint8',

    # GRASP ssems to have:
    # [23]
    #unknown3=struct.uint8*2,
    # [25]
    #filesize='uint16',
    # [27]
    #unknown4=struct.uint8*32,
    # [59]
    # Unknown (not a pointer to the bitmap for the space character)
    #unknown5='uint16',
    # [61]
    #offsets=struct.uint16 * 94,
    # [249]
    # Unknown; possibly the width of a space character
    # however one sample file has 0 here so maybe not
    #space_width='uint8',
    # [250]
    #widths=struct.uint8 * 94,
)

_WIDTH_OFFSET_V3 = 0xFA # 250
_WIDTH_OFFSET_V4 = 0x58 # 88

_BITMAP_OFFSET = 0x158 # 344


# magic 0x10 or 0x11 is a bit too generic
@loaders.register(
    'cft', 'eft', 'lft', 'mft', 'nft', 'pft', 'sft', 'xft',
    name='chiwriter'
)
def load_chiwriter(instream, where=None, filetype:int=None):
    """
    Load a ChiWriter font.

    filetype: override filetype. 0x10 for pcpaint, grasp, chiwriter v3. 0x11 for chiwriter v4. 0x00 for pcpaint/grasp old format
    """
    data = instream.read()
    header = _HEADER.from_bytes(data)
    logging.debug(header)
    if filetype is not None:
        header.filetype = filetype
    # locate width table
    # the V3 format only has space for 94 widths as bitmaps start at 344
    # the V4 format files have the earlier offset even if they have <= 94 glyphs
    if header.filetype == 0x11 or header.numchars > 94:
        woffset = _WIDTH_OFFSET_V4 + 0x20 + header.firstchar
    else:
        woffset = _WIDTH_OFFSET_V3
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
            right_bearing=(_wid or header.defaultwidth)-header.hsize,
            codepoint=_i+0x20+header.firstchar,
            shift_up=shift_up,
        )
        for _i, _wid in enumerate(widths)
    )
    glyphs = [
        _g.crop(right=max(0, -_g.right_bearing)).drop('shift-left')
        for _g in glyphs
    ]
    if header.line_gap:
        # assuming distance from baseline to next raster top
        line_height = header.line_gap + header.baseline
    else:
        line_height = None
    font = Font(
        glyphs,
        source_format=f'ChiWriter ({header.filetype:#02x})',
        name=header.filename.decode('latin-1').split('.')[0],
        font_id=header.filename.decode('latin-1'),
        line_height=line_height,
    )
    return font
