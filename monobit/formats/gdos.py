"""
monobit.formats.gdos - Atari GDOS/GEM format

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..struct import bitfield, little_endian as le, big_endian as be
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError
from ..binary import bytes_to_bits



@loaders.register(
    'gft', #'fnt'
    name='gdos'
)
def load_gdos(instream, where=None, endianness:str=''):
    """
    Load font from Atari GDOS/GEM .FNT file.

    endianness: (b)ig or (l)ittle-endian. default: guess from data
    """
    gdos_props, gdos_glyphs = _read_gdos(instream, endianness)
    logging.info('GDOS properties:')
    for line in str(gdos_props).splitlines():
        logging.info('    ' + line)
    props = _convert_from_gdos(gdos_props)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    font = Font(gdos_glyphs, **vars(props))
    return font


################################################################################
# Atari GDOS/GEM FNT file format

# http://cd.textfiles.com/ataricompendium/BOOK/HTML/APPENDC.HTM#cnt
# https://temlib.org/AtariForumWiki/index.php/GDOS_Font_file_format
# http://www.seasip.info/Gem/filefmt.html
# http://www.verycomputer.com/10_34378d1abfb218c2_1.htm

_BASE = {'l': le, 'b': be}

_FNT_HEADER = {
    _endian: _BASE[_endian].Struct(
        # Face ID (must be unique).
        font_id='word',
        # Face size (in points).
        point_size='word',
        # Name, ASCII, 0-terminated
        name='32s',
        # Lowest character index in face (usually 32 for disk-loaded fonts).
        first_char='word',
        # Highest character index in face.
        last_char='word',
        # Top line distance expressed as a positive offset from baseline.
        top='word',
        # Ascent line distance expressed as a positive offset from baseline.
        ascent='word',
        # Half line distance expressed as a positive offset from baseline.
        half='word',
        # Descent line distance expressed as a positive offset from baseline.
        descent='word',
        # Bottom line distance expressed as a positive offset from baseline
        bottom='word',
        # Width of the widest character.
        max_char_width='word',
        # Width of the widest character cell.
        max_cell_width='word',
        # Left offset
        left_offset='word',
        # Right offset
        right_offset='word',
        # Thickening size (in pixels).
        thicken='word',
        # Underline size (in pixels).
        ul_size='word',
        # Lightening mask (used to eliminate pixels, usually 0x5555).
        lighten='word',
        # Skewing mask (rotated to determine when to perform additional rotation on
        # a character when skewing, usually 0x5555).
        skew='word',
        # 0 Contains System Font
        system_flag=bitfield('word', 1),
        # 1 Horizontal Offset Tables should be used.
        horiz_offs_flag=bitfield('word', 1),
        # 2 Font data need not be byte-swapped.
        byteswapped_flag=bitfield('word', 1),
        # 3 Font is mono-spaced.
        monospaced_flag=bitfield('word', 1),
        unused4=bitfield('word', 1),
        extended_flag=bitfield('word', 1),
        unused6=bitfield('word', 1),
        dbcs_flag=bitfield('word', 1),
        unused8_12=bitfield('word', 5),
        full_id_flag=bitfield('word', 1),
        unused14_15=bitfield('word', 2),
        # Offset from start of file to horizontal offset table.
        hoffs='dword',
        # Offset from start of file to character offset table.
        coffs='dword',
        # Offset from start of file to font data.
        bmps='dword',
        # Form width (in bytes).
        width='word',
        # Form height (in scanlines).
        height='word',
        # pointer to the next font (set by GDOS after loading).
        reserved='dword',
    )
    for _endian in ('l', 'b')
}
_EXTENDED_HEADER = {
    _endian: _BASE[_endian].Struct(
        # Offset of next section of this font
        # ;from start of file (eg, another character
        # ;range). The next section will have its
        # ;own font header.
        next='dword',
        # ;File offset of file data
        fdata_tbl='dword',
        # ;Length of file data
        fdata_len='word',
        # ;Reference count when the font is loaded
        reserved='dword',
        # ;Device flags
        dflags='word',
        # ;Full font ID
        fullid='word',
        # ;Escape sequence buffer?
        buffer='38s',
        # ;If compressed, the size of this font segment
        # ;from the end of the header to the end of the
        # ;compressed data.
        csize='word',
    )
    for _endian in ('l', 'b')
}

# from seasip.info (John Elliott):
# If there is a horizontal offsets table, this comes next. It contains two bytes
# for each character. The first is the number of pixels by which that letter
# should be moved to the left when it is displayed; the second is the number of
# pixels by which the next letter printed should be moved to the left. In other
# words, these two implement proportional spacing by making the letter narrower
# than the cell size in the header.

# from atari compendium:
# Horizontal Offset Table:
# The Horizontal Offset Table is an optional array of positive or negative WORD values
# which when added to the values in the character offset table yield the true spacing
# information for each character. One entry appears in the table for each character.
# This table is not often used.

# note that the atari compendium descriprtion disagrees with John Elliott,
# but is also much less clear so I'm using John Elliott's
_HORIZ_OFFS_ENTRY = {
    _endian: _BASE[_endian].Struct(
        pre='byte',
        post='byte',
    )
    for _endian in ('l', 'b')
}

# The character offsets table consists of one word for each character; this word
# is the X-coordinate of the glyph in question within the font.

# Character Offset Table:
# The Character Offset Table is an array of WORDs which specifies the distance
# (in pixels) from the previous character to the next. The first entry is the
# distance from the start of the raster form to the left side of the first
# character. One succeeding entry follows for each character in the font
# yielding (number of characters + 1) entries in the table. Each entry must be
# byte-swapped as it appears in Intel ('Little Endian') format.

_CHAR_OFFS_ENTRY = {
    _endian: _BASE[_endian].Struct(
        offset='word',
    )
    for _endian in ('l', 'b')
}
# The font itself is stored as a bitmapped image of all the characters side by
# side. If the image is in byteswapped format, each byte will appear to be swapped
# with its neighbour (as in a standard GEM device-independent bitmap).

# Font Data:
# The binary font data is arranged on a single raster form. The raster's height
# is the same as the font's height. The raster's width is the sum of the
# character width's padded to end on a WORD boundary.
# There is no padding between characters. Each character may overlap BYTE
# boundaries. Only the last character in a font is padded to make the width of
# the form end on an even WORD boundary.
# If bit #2 of the font flags header item is cleared, each WORD in the font data
# must be byte-swapped.


def _read_gdos(instream, endianness):
    """Read GDOS binary file and return as properties and glyphs."""
    data = instream.read()
    return _parse_gdos(data, endianness)

def _parse_gdos(data, endianness):
    """Parse GDOS binary file and return as properties and glyphs."""
    endian = endianness[:1].lower()
    header = _FNT_HEADER[endian or 'l'].from_bytes(data)
    if not endian:
        if header.point_size > 256:
            # probably a big-endian font
            return _parse_gdos(data, 'b')
        endian = 'l'
    n_chars = header.last_char - header.first_char + 1
    if header.extended_flag:
        ext_header = _EXTENDED_HEADER[endian].from_bytes(
            data, _FNT_HEADER[endian].size
        )
    if header.horiz_offs_flag:
        hoffs = _HORIZ_OFFS_ENTRY[endian].array(n_chars).from_bytes(
            data, header.hoffs
        )
    else:
        hoffs = [_HORIZ_OFFS_ENTRY[endian]()] * n_chars
    coffs = _CHAR_OFFS_ENTRY[endian].array(n_chars).from_bytes(
        data, header.coffs
    )
    # bitmap strike
    # TODO - byteswaps
    strike = [
        bytes_to_bits(data[_offset : _offset+header.width])
        for _offset in range(
            header.bmps,
            header.bmps + header.width*header.height,
            header.width
        )
    ]
    # extract glyphs
    pixels = [
        [_row[_loc.offset:_next.offset] for _row in strike]
        for _loc, _next in zip(coffs[:-1], coffs[1:])
    ]
    glyphs = [
        Glyph(
            _pix, codepoint=_ord,
            left_bearing=-_hoffs.pre, right_bearing=-_hoffs.post
        )
        for _ord, (_pix, _hoffs) in enumerate(
            zip(pixels, hoffs),
            start=header.first_char
        )
    ]
    return Props(**vars(header)), glyphs


def _convert_from_gdos(gdos_props):
    """Convert GDOS font properties."""
    props = Props(
        name=gdos_props.name.decode('latin-1', errors='ignore'),
        point_size=gdos_props.point_size,
        left_bearing=gdos_props.left_offset,
        right_bearing=gdos_props.right_offset,
        shift_up=-gdos_props.bottom,
        ascent=gdos_props.ascent,
        descent=gdos_props.descent,
        bold_smear=gdos_props.thicken,
        underline_thickness=gdos_props.ul_size,
    )
    props.gdos = f'font-id={gdos_props.font_id}'
    if gdos_props.lighten != 0x5555:
        props.gdos += f' lighten-mask=0x{gdos_props.lighten:x}'
    if gdos_props.skew != 0x5555:
        props.gdos += f' skew-mask=0x{gdos_props.skew:x}'
    return props
