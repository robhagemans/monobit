"""
monobit.formats.dec - DEC Dynamically Redefined Character Set

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# DRCS format documentation
# https://vt100.net/dec/vt320/soft_characters
# https://vt100.net/docs/vt510-rm/DECDLD


import shlex
import logging

from ..storage import loaders, savers
from ..magic import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..binary import ceildiv
from ..basetypes import Coord
from ..properties import reverse_dict


@loaders.register(
    name='dec',
    magic=(b'\x90', b'\x1bP'),
)
def load_dec_drcs(instream):
    """Load character-cell fonts from DEC DRCS file."""
    dec_glyphs, dec_props = _read_drcs(instream)
    props, count, first_codepoint = _parse_drcs_props(dec_props)
    glyphs = _parse_drcs_glyphs(dec_glyphs, props, first_codepoint)
    if len(glyphs) != count:
        logging.warning('Expected %d glyphs, found %d.', count, len(glyphs))
    return Font(glyphs, **props)


@savers.register(linked=load_dec_drcs)
def save_dec_drcs(fonts, outstream, *, use_8bit:bool=False):
    """Write font to a DEC DRCS file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to dec-drcs file.')
        # check if font is fixed-width and fixed-height
    font, = fonts
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    # ensure codepoint values are set if possible
    font = font.label(codepoint_from=font.encoding)
    # fill out bearings and equalise heights
    font = font.equalise_horizontal()
    # upper size limits vary by device, not enforced.
    # lower sizes would conflict with vt200 size values
    if font.raster_size.x < 5 or font.raster_size.y < 1:
        raise FileFormatError(
            'This format only supports fonts of 5px or wider and 1px or taller.'
        )
    _write_dec_drcs(font, outstream)


##########################################################################

# initial and final escape sequences
_ESC_START = (b'\x90', b'\x1bP')
_ESC_END = (b'\x9c', b'\x1b\\')

# parameters
_DEC_PARMS = (
    'Pfn', # Font number
    # Selects the DRCS font buffer to load.
    # The VT320 has one DRCS font buffer. Pfn has two valid values, 0 and
    # 1. Both values refer to the same DRCS buffer.

    'Pcn', # Starting character
    # Selects where to load the first character in the DRCS font buffer.
    # The location corresponds to a location in the ASCII code table.
    # Pcn is affected by the character set size. (See Pcss below.) In a
    # 94-character set, a Pcn value of 0 or 1 means that the first soft
    # character is loaded into position 2/1 of the character table. In a
    # 96-character set, a Pcn value of 0 means the first character is
    # loaded into position 2/0 of the character table. The greatest Pcn
    # value is 95 (position 7/15).

    'Pe', # Erase control
    # Selects which characters to erase from the DRCS buffer before
    # loading the new font.
    # 0 = erase all characters in the DRCS buffer with this number,
    #     width and rendition.
    # 1 = erase only characters in locations being reloaded.
    # 2 = erase all renditions of the soft character set (normal, bold,
    #     80-column, 132-column).

    'Pcmw', # Character matrix width
    # Selects the maximum character cell width. VT300 modes:
    #     0 = 15 pixels wide for 80 columns,
    #         9 pixels wide for 132 columns. (Default)
    #     1 = illegal.
    #     2 = 5 × 10 pixel cell
    #     3 = 6 × 10 pixel cell
    #     4 = 7 × 10 pixel cell
    #     5 = 5 pixels wide.
    #     6 = 6 pixels wide.
    #     ...
    #     15 = 15 pixels wide.
    # If you omit a Pcmw value, the terminal uses the default character
    # width. Any Pcmw value over 15 is illegal.
    # Use Pcmw values 2 through 4 with VT220 compatible software. Remember
    # that VT220 fonts appear different VT320. Fonts designed specifically
    # for the VT320 should use values 5 through 15.

    'Pss', # Font set size (also 'Pw')
    # Defines the screen width and screen height for this font.
    # 0,1 = 80 columns, 24 lines. (default)
    #   2 = 132 columns, 24 lines
    #  11 = 80 columns, 36 lines
    #  12 = 132 columns, 36 lines
    #  21 = 80 columns, 48 lines
    #  22 = 132 columns, 48 lines

    'Pt', # Text or full-cell
    # Defines the font as a text font or full-cell font.
    #    0 = text. (Default)
    #    1 = text.
    #    2 = full cell.
    # Full-cell fonts can individually address all pixels in a cell.
    # Text fonts cannot individually address all pixels. If you specify a
    # text cell, the terminal automatically performs spacing and centering
    # of the characters.

    'Pcmh', # Character matrix height
    # Selects the maximum character cell height.
    #    0 = 12 pixels high. (Default)
    #    1 = 1 pixel high.
    #    2 = 2 pixels high.
    #    3 = 3 pixels high.
    #    ...
    #    12 = 12 pixels high.
    # Pcmh values over 12 are illegal. If the value of Pcmw is 2, 3 or 4,
    # Pcmh is ignored.

    'Pcss', # Character set size
    # Defines the character set as a 94- or 96-character graphic set.
    #    0 = 94-character set. (Default)
    #    1 = 96-character set.
    # The value of Pcss changes the meaning of the Pcn (starting
    # character) parameter above.
    # If Pcss = 0 (94-character set)
    #    The terminal ignores any attempt to load characters into the 2/0
    #    or 7/15 table positions.
    #    1  column 2/row 1
    #    ...
    #    94 column 7/row 14
    # If Pcss = 1 (96-character set)
    #    0 column 2/row 0
    #    ...
    #    95 column 7/row 15

    'Dscs', # Character Set Name
    # Dscs defines the character set name. It consists of from one to
    # three characters. The last character of the name is a character in
    # the range ‘0’ to ‘~’ (3016 to 7E16). There can be from zero to two
    # name characters preceding this one, in the range SP to ‘/’ (2016 to
    # 2F16). This name will be used in the Select Character Set (SCS)
    # sequence.
)

# terminal dimensions
_PSS_DIMS = {
    0: (80, 24),
    1: (80, 24),
    2: (132, 24),
    11: (80, 36),
    12: (132, 36),
    21: (80, 48),
    22: (132, 48),
}
_DEVICE_PATTERN = '{}x{} terminal'


# format-specific properties
_ERASE_CONTROL = {
    0: 'erase=font',
    1: 'erase=glyphs',
    2: 'erase=all',
}
_FONT_TYPE = {
    0: 'type=text',
    1: 'type=text',
    2: 'type=full-cell',
}

_JOINER = '='
_PFN_NAME = 'buffer'
_DSCS_NAME = 'dscs-id'
# recommmended default id for user-defined sets
# https://vt100.net/docs/vt510-rm/DECDLD
_DEFAULT_DSCS = ' @'

##########################################################################

def _read_char(f):
    c = f.read(1)
    while c in (b'\r', b'\n'):
        c = f.read(1)
    return c

def _read_args(f, sep, term=None):
    val, c = b'', b'*'
    while c and c != term:
        c = _read_char(f)
        if (c == term or not c) and not val:
            break
        if c in (sep, term):
            yield val
            val = b''
        else:
            val += c

def _read_dscs_name(f):
    dscs = []
    sep = _read_char(f)
    c = b''
    if sep != b'{':
        # { may have been absorbed by the Pcss read if there was no closing ;
        #raise FileFormatError(f'invalid Dscs separator {sep}')
        c = sep
    # read Dscs
    for _ in range(3):
        dscs.append(c)
        if c and ord(c) in range(0x30, 0x80):
            break
        if c and ord(c) not in range(0x20, 0x30):
            raise FileFormatError('invalid Dscs sequence')
        c = _read_char(f)
    return b''.join(dscs)

def _read_drcs(f):
    """Read a DEC DRCS file."""
    dcs = f.read(1)
    esc = dcs == b'\x1b'
    # one-byte x90 or two-byte esc P
    if esc:
        dcs += f.read(1)
    if not dcs in _ESC_START:
        raise FileFormatError('not a Dec DRCS file')
    argreader = _read_args(f, b';', b'{')
    dec_props = dict(zip(_DEC_PARMS[:-1], argreader))
    dec_props[_DEC_PARMS[-1]] = _read_dscs_name(f)
    term = _ESC_END[esc]
    # really shld be ESC \ but we only check 1 char
    term = term[0]
    glyphdefs = _read_args(f, b';', term)
    glyphdefs = list(glyphdefs)
    return glyphdefs, dec_props


def _convert_drcs_glyph(glyphdef, raster_size):
    """Convert DRCS glyph to monobit glyph."""
    glyphbytes = (
        tuple(_b - ord(b'?') for _b in _block)
        for _block in glyphdef.split(b'/')
    )
    glyphbytes = zip(*glyphbytes)
    glyphstrs = tuple(
        ''.join(f'{_b:06b}' for _b in _pair[::-1])
        for _pair in glyphbytes
    )
    glyph = Glyph(glyphstrs, _0='0', _1='1')
    # pylint: disable=unexpected-keyword-arg
    glyph = glyph.turn(anti=1)
    glyph = glyph.crop(
        right=glyph.width-raster_size.x,
        bottom=glyph.height-raster_size.y
    )
    return glyph


def _parse_drcs_glyphs(glyphdefs, props, first_codepoint):
    """Convert DRCS glyphs to monobit glyphs."""
    glyphs = (
        _convert_drcs_glyph(_g, Coord(*props['raster_size']))
        for _g in glyphdefs
    )
    glyphs = tuple(
        _g.modify(codepoint=_cp)
        for _cp, _g in enumerate(glyphs, first_codepoint)
    )
    return glyphs

def _parse_drcs_props(dec_props):
    """Convert DRCS properties to yaff properties."""
    # determine glyph count from Pcss
    count = 96 if int(dec_props['Pcss']) else 94
    # determine starting codepoint from Pcn
    pcn = int(dec_props['Pcn'])
    first_codepoint = pcn + 0x20
    if count == 94 and not pcn:
        first_codepoint = 0x21
    # determine glyph width from Pcmw and Pss
    try:
        cols, rows = _PSS_DIMS[int(dec_props['Pss'])]
    except KeyError:
        raise FileFormatError(f"unknown value {dec_props['Pss']} for Pss")
    device = _DEVICE_PATTERN.format(cols, rows)
    pcmw = int(dec_props['Pcmw'])
    width, height = 0, 0
    if not pcmw:
        width = 9 if cols == 132 else 15
    elif pcmw >= 5:
        width = pcmw
    elif 4 >= pcmw >= 2:
        width = 3 + pcmw
        height = 10
    else:
        logging.warning('illegal value %d for Pcmw', pcmw)
    # determine glyph height from Pcmh
    if not height:
        height = int(dec_props['Pcmh']) or 12
    props = dict(
        encoding='ascii',
        raster_size=(width, height),
        device=device,
    )
    scs_id = dec_props['Dscs'].decode('ascii')
    # preserve unparsed properties
    props['dec_drcs'] = shlex.join((
        _JOINER.join((_DSCS_NAME, scs_id)),
        _JOINER.join((_PFN_NAME, str(int(dec_props['Pfn'])))),
        _ERASE_CONTROL[int(dec_props['Pe'])],
        _FONT_TYPE[int(dec_props['Pt'])],
    ))
    return props, count, first_codepoint

##########################################################################

def _write_dec_drcs(font, outstream, use_8bit=False):
    """Write a font to a DRCS file."""
    esc = not use_8bit
    # we can onl store the printable ascii range
    ascii = tuple(chr(_b) for _b in range(0x20, 0x80))
    glyphs = tuple(
        font.get_glyph(char=_c, missing='empty')
        for _c in ascii
    )
    # write 96 glyphs?
    is_big = not glyphs[0].is_blank() or not glyphs[-1].is_blank()
    if not is_big:
        glyphs = glyphs[1:-1]
    dec_props = _convert_to_drcs_props(font, is_big)
    outstream.write(_ESC_START[esc])
    outstream.write(b';'.join(
        str(dec_props[_k]).encode('ascii')
        for _k in _DEC_PARMS[:-1])
    )
    dscs = dec_props[_DEC_PARMS[-1]].encode('ascii')
    outstream.write(b'{')
    outstream.write(dscs)
    outstream.write(b'\n')
    for _g in glyphs:
        outstream.write(_convert_to_drcs_glyph(_g))
    outstream.write(_ESC_END[esc])
    # select character set (SCS) - no 8-bit variant?
    outstream.write(b' \x1b(%s\n' % (dscs,))

def _convert_to_drcs_props(font, is_big):
    # device spec
    pss_to_dims = reverse_dict(_PSS_DIMS)
    devices = {
        _DEVICE_PATTERN.format(*_k): _v
        for _k, _v in pss_to_dims.items()
    }
    pss = devices.get(font.device, 0)
    # format-specific
    pfn, pe, pt = 0, 1, 2
    dscs_id = _DEFAULT_DSCS
    try:
        unparsed = font.dec_drcs
    except AttributeError:
        pass
    else:
        uprops = shlex.split(unparsed)
        erase = reverse_dict(_ERASE_CONTROL)
        ftype = reverse_dict(_FONT_TYPE)
        for uprop in uprops:
            pe = erase.get(uprop, pe)
            pt = ftype.get(uprop, pt)
            key, _, value = uprop.split(_JOINER)
            if key == _PFN_NAME:
                pfn = value
            if key == _DSCS_NAME:
                dscs_id = value
    dec_props = {
        'Pfn': pfn,
        'Pcn': int(not is_big),  # we only define full sets
        'Pe': pe,
        'Pcmw': font.raster_size.x,
        'Pss': pss,
        'Pt': pt,
        'Pcmh': font.raster_size.y,
        'Pcss': int(is_big),
        'Dscs': dscs_id,
    }
    return dec_props

def _convert_to_drcs_glyph(glyph):
    # cut to sixel blocks
    nblocks = ceildiv(glyph.height, 6)
    blocks = (
        glyph.crop(
            top=_i*6,
            bottom=max(0, glyph.height-(_i+1)*6)
        )
        for _i in range(nblocks)
    )
    blocks = (_b.turn(clockwise=1) for _b in blocks)
    blockbytes = (_b.as_bytes(align='r') for _b in blocks)
    glyphdef = b'/'.join(
        bytes(_c + ord('?') for _c in _b)
        for _b in blockbytes
    ) + b';\n'
    return glyphdef
