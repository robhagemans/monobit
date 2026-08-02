"""
monobit.storage.fontformats.apple.fbit - Mac `fbit` bitmap fonts

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from io import BytesIO
import logging

from monobit.core import Font, Glyph
from monobit.base.binary import ceildiv
from monobit.base.struct import big_endian as be

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

_RUNS_TABLE = be.Struct(
    # first character in the run, by ordinal position in shift-JIS table
    first='uint16',
    # last character in the run, by ordinal position in shift-JIS table
    last='uint16',
    # number of codepoints in the run
    count='uint16',
)


def _ordinal_to_shiftjis(ordinal):
    """Find shift-JIS codepoint based on ordinal."""
    # each page runs from 0x40 to 0x7e inclusive, 0x80 to 0xfc inclusive, 188 bytes
    page, position = divmod(ordinal, 188)
    # high byte in 0x81-0x9F or 0xE0-0xFC
    hi = (page + 0x81) + 64 * (page >= 0x1f)
    # low byte in 0x40-0x7E or 0x80-0xFC
    lo = position + 0x40 + (position >= 0x3f)
    return hi * 0x100 + lo


def extract_fbit(data, offset, data_fork_stream):
    """Extract fbit resource."""
    with BytesIO(data[offset:]) as stream:
        header = _FBIT_HEADER.read_from(stream)
        logging.debug('fbit header: %s', header)
        glyphstream = stream
        if header.fdef_id == 5:
            stream.read(78)
            glyphstream = data_fork_stream
        elif header.fdef_id == 7:
            stream.read(66)
            glyphstream = data_fork_stream
        elif header.fdef_id != 0:
            logging.warning(
                'Unknown fdef id %d, trying format for fdef_id 0', fdef_id
            )
        # table of run lengths
        table_size = be.uint16.read_from(stream)
        runs = (_RUNS_TABLE * table_size).read_from(stream)
        logging.debug('runs: %s', runs)
        if glyphstream is None:
            logging.warning(
                'Glyphs for this font are stored in the data fork, which was not found. '
                'Use -data-fork=<filename> to indicate its location.'
            )
            glyphs = ()
        else:
            glyphs = tuple(
                Glyph.from_bytes(
                    glyphstream.read(ceildiv(header.width * header.height, 8)),
                    header.width, header.height,
                    align='bit', bit_order='row-major',
                    codepoint=_ordinal_to_shiftjis(_run.first + _i)
                )
                for _run in runs
                for _i in range(_run.count)
            )
    return dict(
        font=Font(glyphs, encoding='mac-japanese', source_format='[Mac] fbit')
    )
