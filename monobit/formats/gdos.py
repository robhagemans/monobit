"""
monobit.formats.gdos - Atari GDOS/GEM format

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..struct import bitfield, little_endian as le, big_endian as be, sizeof
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..magic import FileFormatError, Magic
from ..binary import bytes_to_bits, ceildiv
from ..raster import Raster


@loaders.register(
    name='gdos',
    patterns=('*.fnt', '*.gft', '*.[cev]ga'),
    # maybe - this is the usual value for 'lighten' and 'skew'
    magic=(Magic.offset(62) + b'UUUU',),
)
def load_gdos(instream, endianness:str=''):
    """
    Load font from Atari GDOS/GEM .FNT file.

    endianness: (b)ig or (l)ittle-endian. default: guess from data
    """
    gdos_props, gdos_glyphs = _read_gdos(instream, endianness)
    logging.info(
        'GDOS properties:\n    ' +
        '\n    '.join(str(gdos_props).splitlines())
    )
    props = _convert_from_gdos(gdos_props)
    logging.info(
        'yaff properties:\n    ' +
        '\n    '.join(str(props).splitlines())
    )
    font = Font(gdos_glyphs, **vars(props))
    return font


@savers.register(linked=load_gdos)
def save_gdos(fonts, outstream, endianness:str='little'):
    """
    Save font to Atari GDOS/GEM .FNT file.

    endianness: (b)ig or (l)ittle-endian. default: little
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to GDOS file.')
    font, = fonts
    header, gdos_glyphs = _convert_to_gdos(font, endianness)
    logging.info('GDOS properties:')
    logging.info(header)
    _write_gdos(outstream, header, gdos_glyphs, endianness)


################################################################################
# Atari GDOS/GEM FNT file format

# http://cd.textfiles.com/ataricompendium/BOOK/HTML/APPENDC.HTM#cnt
# https://temlib.org/AtariForumWiki/index.php/GDOS_Font_file_format
# http://www.seasip.info/Gem/filefmt.html
# http://www.verycomputer.com/10_34378d1abfb218c2_1.htm

# * all above sources seem to be incomplete. see also the GEM source code,
# * in particular EQUATES.A86 - found in GDOS.ZIP or at
# * https://github.com/shanecoughlan/OpenGEM/blob/master/source/OpenGEM-7-RC3-SDK/OpenGEM-7-SDK/GEM%20VDI%20AND%20SOURCE%20CODE/GEM%203%20VDI%20source%20code/EQUATES.A86

# storable code points
_GDOS_RANGE = range(0, 256)

# we have a choice of big and little endian files, need different base classes
_BASE = {'l': le, 'b': be}

# we need to specify the flags structure separately
# due to the way ctypes applies endianness to bitfields
_FH_FLAGS = {
    'l': le.Struct(
        # 0 Contains System Font
        default=bitfield('word', 1),
        # 1 Horizontal Offset Tables should be used.
        horz_off=bitfield('word', 1),
        # 2 Font data need not be byte-swapped.
        #;Bit 2: Font image is in byteswapped format
        # * interpretation - this flag should be set if the file is in
        # * standard == Motorola == big-endian format
        stdform=bitfield('word', 1),
        # 3 Font is mono-spaced.
        monospace=bitfield('word', 1),
        unused4=bitfield('word', 1),
        #;Bit 5: Extended font header
        #;      - another reference gives 'compressed'
        # * EQUATES.A86 has
        # * COMPRESSED		equ	0020h	; font data compressed flag
        compressed=bitfield('word', 1),
        unused6=bitfield('word', 1),
        #;Bit 7: Font supports DBCS characters (used internally
        #;       by ViewMAX in DRDOS 6.0/V).
        # * internal use only, ignore
        dbcs_flag=bitfield('word', 1),
        unused8_12=bitfield('word', 5),
        #;Bit 13: Use 'full font ID' - see below.
        use_full_id=bitfield('word', 1),
        unused14_15=bitfield('word', 2),
    ),
    'b': be.Struct(
        unused14_15=bitfield('word', 2),
        use_full_id=bitfield('word', 1),
        unused8_12=bitfield('word', 5),
        dbcs_flag=bitfield('word', 1),
        unused6=bitfield('word', 1),
        compressed=bitfield('word', 1),
        unused4=bitfield('word', 1),
        monospace=bitfield('word', 1),
        stdform=bitfield('word', 1),
        horz_off=bitfield('word', 1),
        default=bitfield('word', 1),
    ),
}


# style flags (font_id high byte)
# from fontdef.h in SDSDL: GEM video driver for SDL
# /* style bits */
#define	THICKEN	0x001
#define	LIGHT	0x002
#define	SKEW	0x004
#define	UNDER	0x008
#define	OUTLINE 0x010
#define	SHADOW	0x020
#define ROTODD  0x040
#define ROTHIGH 0x080
#define	ROTATE	0x0c0
#define	SCALE	0x100

_FNT_HEADER = {
    _endian: _BASE[_endian].Struct(
        # Face ID (must be unique).
        # * per UTILITY.A86, the high byte is the 'attribute value'
        # * whereas the low byte is the font id proper. so 0 <= font_id <= 255
        # * unless the 'use_full_id' flag is set,
        # * in which case the low byte is discarded.
        # * The 'attribute' is a bit field including flags for
        # * thicken (1) lighten (2) skew (4) underline (8) outline (10) shadow (20)
        # * Presumably it's used for predefined italic fonts etc, so they
        # * won't need to be generated algorithmically? or internal use only?
        font_id='word',
        # Face size (in points).
        point='word',
        # Name, ASCII, 0-terminated
        name='32s',
        # Lowest character index in face (usually 32 for disk-loaded fonts).
        first_ade='word',
        # Highest character index in face.
        last_ade='word',
        # Top line distance expressed as a positive offset from baseline.
        top='word',
        # Ascent line distance expressed as a positive offset from baseline.
        ascent='word',
        # Half line distance expressed as a positive offset from baseline.
        # * Illustrations in various sources show this as the x-height
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
        # ;Amount character slants left when skewed
        # * Origin to be moved left by this amount before drawing skewed glyph
        # * Values tend to be ~ descent/2 which makes sense if the skewed glyph
        # * is generated keeping the baseline constant and with a 1x2 pitch
        left_offset='word',
        # Right offset
        # ;Amount character slants right
        # * Origin to be moved back (left) by this number of pixels after
        # * drawing skewed glyph. Value tends to be ~ ascent/2
        right_offset='word',
        # Thickening size (in pixels).
        thicken='word',
        # Underline size (in pixels).
        ul_size='word',
        # Lightening mask (used to eliminate pixels, usually 0x5555).
        # * From GUI screenshots, the lightening is done by a dither pattern
        # * that looks like alternating 0x5555 and 0xaaaa, though on the
        # * GEM character styles image in "Atari ST Graphics and Sound"
        # * it appears to be 0x5555 applied on both axes
        lighten='word',
        # Skewing mask (rotated to determine when to perform additional rotation on
        # a character when skewing, usually 0x5555).
        # * What I think this means is this. 'Rotated' is used as in bit-rotate,
        # * so the bits of the mask are rotated; when we get a 1 bit a row in the
        # * glyph is pushed further to the right.
        # * So a 0x5555 skew means a 1x2 shear in monobit terminology,
        # * which agrees with the offset values being half of ascent/descent.
        skew='word',
        # flags, see structure above
        flags=_FH_FLAGS[_endian],
        # Offset from start of file to horizontal offset table.
        hor_table='dword',
        # Offset from start of file to character offset table.
        off_table='dword',
        # Offset from start of file to font data.
        dat_table='dword',
        # Form width (in bytes).
        form_width='word',
        # Form height (in scanlines).
        form_height='word',
        # pointer to the next font (set by GDOS after loading).
        next_font='dword',
    )
    for _endian in ('l', 'b')
}

# based on EQUATES.A86 in GEM source code
# it seems either John Elliott's page missed out a few fields or there
# are different versions of the extended header (for different GEM versions?)
# this produces sensible results on the fonts included with OpenGEM
_EXTENDED_HEADER = {
    _endian: _BASE[_endian].Struct(
        # Offset of next section of this font
        # ;from start of file (eg, another character
        # ;range). The next section will have its
        # ;own font header.
        # ; next font header offset
        # ; next font header segment
        next_sect='dword',
        # ; offset to use counter (low word)
        # ; offset to use counter (high word)
        use_count='dword',
        # ; font file data offset
        # ; font file data segment
        file_data_off='dword',
        # ; font file data size
        data_size='word',
        # ; font string index
        strindex='word',
        # ; low word of header LRU
        # ; high word of header LRU
        hdrlru='dword',
        # ; GDOS font management flags
        gdos_flags='word',
        # ; full font id word
        # * the full word replaces the font_id in the main header
        # * which really is a byte although stored in a word field
        full_id='word',
        # ;Escape sequence buffer?
        buffer='38s',
        # ;If compressed, the size of this font segment
        # ;from the end of the header to the end of the
        # ;compressed data.
        # ; compressed data size
        compressed_size='word',
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
# but is also much less clear so I'm using John Elliott's which seems to produce
# sensible results on real ifiles.
_HORIZ_OFFS_ENTRY = {
    _endian: _BASE[_endian].Struct(
        pre='int8',
        post='int8',
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


################################################################################
# GDOS reader

def _read_gdos(instream, endian):
    """Read GDOS binary file and return as properties and glyphs."""
    data = instream.read()
    # loop over linked list of character ranges
    headers = []
    glyph_ranges = []
    offset = 0
    while True:
        if not data:
            break
        header, ext_header, off_table, hor_table, endian = _read_gdos_header(
            data, endian
        )
        glyphs = _read_gdos_glyphs(
            data, header, ext_header, off_table, hor_table, endian
        )
        headers.append(header)
        glyph_ranges.append(glyphs)
        # if no next section given, we're done
        if not ext_header.next_sect:
            break
        data = data[ext_header.next_sect-offset:]
        offset = ext_header.next_sect
    glyphs = tuple(_g for _range in glyph_ranges for _g in _range)
    if any(
            len(set(tuple(getattr(_h, _attr) for _h in headers))) > 1
            for _attr in ('font_id', 'name', 'point')
        ):
        logging.warning(
            'Different font headers given for character ranges. '
            'Using first header.'
        )
    # note that not all values in the first header make sense when applied
    # to the whole font - e.g. codepage range is just for first section
    return Props(**vars(headers[0]), **vars(ext_header)), glyphs

def _read_gdos_header(data, endian):
    """Parse GDOS binary file and return as properties and glyphs."""
    endian = endian[:1].lower()
    header = _FNT_HEADER[endian or 'l'].from_bytes(data)
    if not endian:
        if header.point >= 256:
            # probably a big-endian font
            endian = 'b'
            header = _FNT_HEADER[endian].from_bytes(data)
            logging.info('Treating as big-endian based on point-size field')
        else:
            endian = 'l'
            logging.info('Treating as little-endian based on point-size field')
    n_chars = header.last_ade - header.first_ade + 1
    logging.debug(header)
    if header.flags.compressed:
        ext_header = _EXTENDED_HEADER[endian].from_bytes(
            data, _FNT_HEADER[endian].size
        )
        logging.debug(ext_header)
    else:
        ext_header = _EXTENDED_HEADER[endian]()
    if header.flags.horz_off:
        hor_table = _HORIZ_OFFS_ENTRY[endian].array(n_chars).from_bytes(
            data, header.hor_table
        )
    else:
        hor_table = [_HORIZ_OFFS_ENTRY[endian]()] * n_chars
    off_table = _CHAR_OFFS_ENTRY[endian].array(n_chars+1).from_bytes(
        data, header.off_table
    )
    if header.flags.stdform and endian != 'b':
        logging.warning('Ignoring big-endian flag')
    if not header.flags.stdform and endian != 'l':
        logging.warning('Ignoring little-endian flag')
    return header, ext_header, off_table, hor_table, endian

def _read_gdos_glyphs(data, header, ext_header, off_table, hor_table, endian):
    """Read glyphs from bitmap strike data."""
    # bitmap strike
    if header.flags.compressed:
        strike = _read_compressed_strike(data, header, ext_header, endian)
    else:
        strike = _read_strike(data, header)
    # extract glyphs
    pixels = [
        [_row[_loc.offset:_next.offset] for _row in strike]
        for _loc, _next in zip(off_table[:-1], off_table[1:])
    ]
    glyphs = [
        Glyph(
            _pix, codepoint=_ord,
            left_bearing=-_hor_table.pre, right_bearing=-_hor_table.post
        )
        for _ord, (_pix, _hor_table) in enumerate(
            zip(pixels, hor_table),
            start=header.first_ade
        )
    ]
    return glyphs


def _read_strike(data, header):
    """Read uncompressed bitmap strike."""
    return [
        bytes_to_bits(data[_offset : _offset+header.form_width])
        for _offset in range(
            header.dat_table,
            header.dat_table + header.form_width*header.form_height,
            header.form_width
        )
    ]

# description of the run-length encoding scheme
# from DECODE.A86 in the GDOS sources
# see e.g. https://github.com/shanecoughlan/OpenGEM
# see also https://github.com/th-otto/gemfedit/blob/master/unix/decode.c
# for a C implementation of the algorithm
#
# https://github.com/shanecoughlan/OpenGEM/blob/master/source/OpenGEM-7-RC1-SDK/OpenGEM-7-SDK/GEM%20VDI%20AND%20SOURCE%20CODE/GEM%203%20VDI%20source%20code/DECODE.A86#L50
# ;**************************************************************************
# ;Now for the tricky bit - decoding the data.
# ;
# ;The decoding scheme is this:
# ;Starting with a string of zeros, then alternating ones and zeros read string
# ;lengths encoded as:
# ;ZERO strings:
# ; length of string   Encoding
# ;     1-8	    1xyz	xyz=n-1 in binary
# ;     9-16	    01xyz       xyz=n-9 in binary (1xyz=n-1)
# ;    17-32	    001wxyz    wxyz=n-17 in binary (1wxyz=n-1)
# ; etc to:
# ;    64K-1	    0000 0000 0000 0111 1111 1111 1111 0
# ;BUT 64K-1 no alternation:
# ;		    0000 0000 0000 0111 1111 1111 1111 1
# ;This last is used to break up long strings so that we can use 16 bit counts
# ;
# ;ONE strings:
# ; length of string   Encoding
# ;     1		     0
# ;     2		     10
# ;     3		     110
# ; etc where the 0 flags the end of the string
# ;NOTE that there is no theoretical limit to the lengths of strings encountered
# ;
# ;Lastly, convert each line except the top one to the XOR of itself and the
# ;line above.
# ;
# ;**********************************************************************
# ;

def _read_compressed_strike(data, header, ext_header, endian):
    """Read run length encoded bitmap strike."""
    if ext_header.next_sect:
        bmp_bytes = list(data[header.dat_table:ext_header.next_sect])
    else:
        bmp_bytes = list(data[header.dat_table:])
    if endian == 'l':
        bmp_bytes[0::2], bmp_bytes[1::2] = bmp_bytes[1::2], bmp_bytes[0::2]
    compressed_bmp = bytes_to_bits(bmp_bytes)
    ofs = 0
    bits = []
    n_strike_bits = header.form_height * header.form_width * 8
    while ofs < len(compressed_bmp) and len(bits) < n_strike_bits:
        try:
            idx_one = compressed_bmp.index(True, ofs) - ofs
        except ValueError:
            idx_one = len(compressed_bmp) - ofs
        if idx_one:
            # include the leading one
            field = compressed_bmp[ofs+idx_one:ofs+2*idx_one+3]
            ofs += 2*idx_one+3
        else:
            # 1-8 case, skip the leading one
            field = compressed_bmp[ofs+1:ofs+4]
            ofs += 4
        field = ''.join('1' if _b else '0' for _b in field)
        n_zeros = int(field, 2) + 1
        max = 2**16
        if n_zeros > max:
            # error
            raise FileFormatError('could not read compressed bitmap.')
        elif n_zeros == max:
            # special case, no alternation
            bits.extend([False]*(max-1))
        else:
            bits.extend([False]*n_zeros)
            try:
                idx_zero = compressed_bmp.index(False, ofs) - ofs
            except ValueError:
                idx_zero = len(compressed_bmp) - ofs
            bits.extend([True]*(idx_zero+1))
            ofs += idx_zero + 1
    # (undocumented?) decoding produces always 1 or more zeroes at the start
    # so remove the first zero to ensure it's possible to start with a 1
    # this is what's meant by the 'imagined zero' mentioned in other sources?
    strike = [
        tuple(bits[_s:_s+header.form_width*8])
        for _s in range(1, n_strike_bits+1, header.form_width*8)
    ]
    # convert line to xor of itself and previous (cumulative)
    prev = (0,) * header.form_width*8
    for n, _ in enumerate(strike):
        strike[n] = tuple(_r^_l for _r, _l in zip(strike[n], prev))
        prev = strike[n]
    return strike


def _convert_from_gdos(gdos_props):
    """Convert GDOS font properties."""
    props = Props(
        name=gdos_props.name.decode('latin-1', errors='ignore'),
        point_size=gdos_props.point,
        shift_up=-gdos_props.bottom,
        ascent=gdos_props.ascent+1,
        descent=gdos_props.descent,
        bold_smear=gdos_props.thicken,
        underline_thickness=gdos_props.ul_size,
    )
    props.gdos = ' '.join((
        f'font-id={gdos_props.font_id}',
        f'left-offset={gdos_props.left_offset}',
        f'right-offset={gdos_props.right_offset}',
    ))
    if gdos_props.lighten != 0x5555:
        props.gdos += f' lighten-mask=0x{gdos_props.lighten:x}'
    if gdos_props.skew != 0x5555:
        props.gdos += f' skew-mask=0x{gdos_props.skew:x}'
    return props


################################################################################
# GDOS writer

def _convert_to_gdos(font, endianness):
    """Convert monobit font to GDOS properties and glyphs."""
    # ensure codepoint values are set if possible
    font = font.label(codepoint_from=font.encoding)
    font = font.subset(_GDOS_RANGE)
    font = _make_contiguous(font)
    # bring to padded normal form with equalised upshifts
    font = font.equalise_horizontal()
    upshifts = set(_g.shift_up for _g in font.glyphs)
    shift_up, *remainder = upshifts
    assert not remainder
    # check glyph dimensions / bitfield ranges
    if any(_g.left_bearing < -127 or _g.right_bearing < -127 for _g in font.glyphs):
        raise FileFormatError(
            'GDOS format: negative bearings must not exceed 127.'
        )
    # keep namespace properties
    if 'gdos' in font.get_properties():
        propsplit = (item.partition('=') for item in font.gdos.split())
        add_props = {_k: int(_v) for _k, _, _v in propsplit}
    else:
        add_props = {}
    endian = endianness[0].lower()
    flags = _FH_FLAGS[endian](
        default=add_props.get('font-id', 255) == 1,
        horz_off=1,
        stdform=endian == 'b',
        monospace=font.spacing in ('monospace', 'character-cell'),
        compressed=0,
        dbcs_flag=0,
        use_full_id=0,
    )
    header = _FNT_HEADER[endian](
        font_id=add_props.get('font-id', 255),
        point=font.point_size,
        name=font.name.encode('ascii', 'replace')[:32],
        first_ade=int(min(font.get_codepoints())),
        last_ade=int(max(font.get_codepoints())),
        # common shift up must be negative as we brought to padded normal form
        top=font.raster_size.y + shift_up,
        ascent=font.ascent-1,
        # Half line distance expressed as a positive offset from baseline.
        # interpreting as x-height
        half=font.x_height,
        descent=font.descent,
        # common shift up must be negative as we brought to padded normal form
        bottom=-shift_up,
        # Width of the widest character.
        # I'm interpreting this as the widest per-glyph bounding box
        max_char_width=max(_g.bounding_box.x for _g in font.glyphs),
        # Width of the widest character cell.
        # interpreting as widest advance width
        max_cell_width=font.max_width,
        left_offset=add_props.get('left-offset', 0),
        right_offset=add_props.get('right-offset', 0),
        thicken=font.bold_smear,
        ul_size=font.underline_thickness,
        lighten=add_props.get('lighten_mask', 0x5555),
        skew=add_props.get('skew_mask', 0x5555),
        flags=flags,
        #hor_table, off_table, dat_table, form_width, form_height
    )
    return header, font.glyphs


def _make_contiguous(font):
    """Get contiguous range, fill gaps with empties."""
    glyphs = tuple(
        font.get_glyph(codepoint=_cp, missing='empty').modify(codepoint=_cp)
        for _cp in range(
            int(min(font.get_codepoints())),
            int(max(font.get_codepoints()))+1
        )
    )
    # remove empties at end
    while glyphs and glyphs[-1].is_blank() and not glyphs[-1].advance_width:
        glyphs = glyphs[:-1]
    if not glyphs:
        raise FileFormatError(
            'Output format: no glyphs in storable codepoint range 0--255.'
        )
    font = font.modify(glyphs)
    return font

def _generate_bitmap_strike(glyphs):
    """Generate horizontal bitmap strike."""
    # all glyphs have been brought to the same height previously
    matrices = tuple(_g.as_matrix() for _g in glyphs)
    strike = tuple(
        sum((_m[_row] for _m in matrices), ())
        for _row in range(glyphs[0].height)
    )
    offsets = (0,) + tuple(accumulate(_g.width for _g in glyphs))
    return Raster(strike, _0=0, _1=1), offsets

def _write_gdos(outstream, header, glyphs, endianness):
    """Write gdos properties and glyphs to binary file."""
    endian = endianness[0].lower()
    # generate strike and off_table table
    strike, offsets = _generate_bitmap_strike(glyphs)
    n_chars = len(glyphs)
    # horizontal offsets - based on neg bearings
    hor_table = _HORIZ_OFFS_ENTRY[endian].array(n_chars)(*(
        _HORIZ_OFFS_ENTRY[endian](
            pre=-_g.left_bearing,
            post=-_g.right_bearing,
        )
        for _g in glyphs
    ))
    # offsets table
    off_table = _CHAR_OFFS_ENTRY[endian].array(n_chars+1)(*(
        _CHAR_OFFS_ENTRY[endian](offset=_o)
        for _o in offsets
    ))
    # add pointers to header
    header.hor_table = sizeof(header)
    header.off_table = header.hor_table + sizeof(hor_table)
    header.dat_table = header.off_table + sizeof(off_table)
    header.form_width = ceildiv(strike.width, 8)
    header.form_height = strike.height
    # write output
    outstream.write(b''.join((
        bytes(header),
        bytes(hor_table),
        bytes(off_table),
        strike.as_bytes(),
    )))
