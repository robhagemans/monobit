"""
monobit.storage.fontformats.apple.fbit - Mac `fbit` bitmap fonts

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from io import BytesIO
import logging

from monobit.core import Font
from monobit.base.struct import big_endian as be
from monobit.storage.fontformats.raw import load_bitmap

# Apple Japan Technote 100004 "リゾルバブルフォント フォントフォーマット" ("Resolvable Font Format")
# http://mirror.informatimago.com/next/developer.apple.com/ja/technotes/tn10004.html
# (Machine translated:)
# > In Kanji Talk, the bitmap data of the Japanese bitmap font is held with a
# > resource called 'fbit', and the bitmap data is accessed by the code resource
# > 'fdef'. The header of this 'fbit' resource contains a field that defines the
# > resource ID of the 'FOND' resource associated with the 'fbit' font. The standard
# > header format of fbit is as follows.

# type 'fbit' {
#     unsigned hex integer   /* font flags */
#     literal longInt        /* resource type */
#     unsigned integer       /* resource ID number */
#     unsigned integer       /* version number */
#     unsigned integer       /* fdef ID number */
#     fill long              /* pointer to fdef code */
#     unsigned integer       /* FOND ID */
#     unsigned integer       /* priority */
#     fill long              /* reserved */
#     unsigned integer       /* character height */
#     unsigned integer       /* character width */
#     unsigned hex integer   /* font style */
#     unsigned integer       /* reserved for future use */
#     unsigned hex integer   /* first kanji code in this font */
#     unsigned hex integer   /* last kanji code in this font */
# };

_FBIT_HEADER = be.Struct(
    font_flag='uint16',
    resource_type='4s',
    resource_id='uint16',
    version='uint16',
    fdef_id='uint16',
    fdef_code_pointer='uint32',
    fond_id='uint16',
    priority='uint16',
    reserved0='uint32',
    height='uint16',
    width='uint16',
    style='uint16',
    reserved1='uint16',
    first_codepoint='uint16',
    last_codepoint='uint16',
)

_LENGTHS_TABLE = be.Struct(
    # first character in the run, by ordinal position in shift-JIS table
    first='uint16',
    # last character in the run, by ordinal position in shift-JIS table
    last='uint16',
    # number of codepoints in the run
    count='uint16',
)

def extract_fbit(data, offset):
    """Extract fbit resource."""
    with BytesIO(data[offset:]) as stream:
        header = _FBIT_HEADER.read_from(stream)
        logging.debug('fbit header: %s', header)
        # table of run lengths
        table_size = be.uint16.read_from(stream)
        runs = (_LENGTHS_TABLE * table_size).read_from(stream)
        logging.debug('runs: %s', runs)
        glyphs = []
        logging.debug('first codepoint: %x', header.first_codepoint)
        for run in runs:
            # find shift-JIS codepoint based on ordinal
            # each page runs from 0x40 to 0xfc inclusive, 188 bytes
            page, position = divmod(run.first, 188)
            # 0x8140 is not counted
            first_codepoint = (page + 0x81) * 0x100 + position + 0x41
            logging.debug('first codepoint in run: %x', first_codepoint)
            temp_font = load_bitmap(
                stream, header.width, header.height, run.count,
                align='bit',
                first_codepoint=first_codepoint
            )
            logging.debug('%s', temp_font)
            glyphs.extend(temp_font.glyphs)
    return dict(
        font=Font(glyphs, encoding='mac-japanese')
    )
