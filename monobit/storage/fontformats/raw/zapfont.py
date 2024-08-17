"""
monobit.storage.formats.raw.zapfont - RiscOS !ZapFont file

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Magic
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Glyph, Font, Char
from monobit.base.struct import little_endian as le, bitfield
from monobit.base.binary import ceildiv

from .raw import load_bitmap, save_bitmap
from monobit.storage.utils.limitations import ensure_single


###############################################################################
# https://github.com/jaylett/zap/blob/master/dists/fonts/!ZapFonts/Fonts/!ReadMe%2Cfff

_ZAP_MAGIC = b'ZapFont\r'
_ZAP_HEADER = le.Struct(
    #  +0 "ZapFont",13
    magic='8s',
	#  +8 Width of each font character in pixels
    width='uint32',
	# +12 Height of each font character in pixels
    height='uint32',
	# +16 First character code given (eg 0 or &20)
    first='uint32',
	# +20 Last character code given +1 (eg &100)
    last='uint32',
	# +24 Reserved (0)
    reserved_0='uint32',
	# +28 Reserved (0)
    reserved_1='uint32',
	# +32 Bitmaps (starting at character code given in #&10)
	#      Format of bitmaps is as for ZapRedraw documentation.
	#      Characters >=256 are used for cursors - see ZapRedraw docs.
	#      Any glyphs above 256 in the file are igno
)

@loaders.register(
    name='zapfont',
    magic=(_ZAP_MAGIC,),
    patterns=('*,1bd',),
)
def load_zapfont(instream):
    """Load a ZapFont."""
    header = _ZAP_HEADER.read_from(instream)
    if header.magic != _ZAP_MAGIC:
        raise FileFormatError(
            f'Not a !ZapFont file: incorrect signature {header.magic}.'
        )
    logging.debug('header: %s', header)
    count = header.last - header.first
    font = load_bitmap(
        instream, width=header.width,
        height=header.height, count=count,
        msb='right',
        align='right',
        byte_swap=ceildiv(header.width, 8),
    )
    font = font.modify(source_format='ZapFont')
    return font
