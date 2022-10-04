"""
monobit.formats.dec - DEC Dynamically Redefined Character Set

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# DRCS format documentation
# https://vt100.net/dec/vt320/soft_characters

import logging

from ..storage import loaders, savers
from ..streams import FileFormatError
from ..struct import Props
from ..font import Font
from ..glyph import Glyph


@loaders.register(
    magic=(b'\x90', b'\x1bP'),
    name='dec-drcs'
)
def load_dec_drcs(instream, where=None):
    """Load character-cell fonts from DEC DRCS file."""
    dec_glyphs, dec_props = read_drcs(instream)
    props, count, first_codepoint = parse_drcs_props(dec_props)
    glyphs = parse_drcs_glyphs(dec_glyphs, first_codepoint)
    if len(glyphs) != count:
        logging.warning('Expected %d glyphs, found %d.', count, len(glyphs))
    return Font(glyphs, **vars(props))


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

    'Pw', # Font width
    # Selects the number of columns per line (font set size).
    #    0 = 80 columns. (Default)
    #    1 = 80 columns.
    #    2 = 132 columns.

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


def read_char(f):
    c = f.read(1)
    while c in (b'\r', b'\n'):
        c = f.read(1)
    return c

def read_args(f, sep, term=None):
    val, c = b'', b'*'
    while c and c != term:
        c = read_char(f)
        if (c == term or not c) and not val:
            break
        if c in (sep, term):
            yield val
            val = b''
        else:
            val += c

def read_dscs_name(f):
    dscs = []
    sep = read_char(f)
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
        c = read_char(f)
    return b''.join(dscs)

def read_drcs(f):
    """Read a DEC DRCS file."""
    dcs = f.read(1)
    esc = dcs == b'\x1b'
    # one-byte x90 or two-byte esc P
    if esc:
        dcs += f.read(1)
    if not dcs in _ESC_START:
        raise FileFormatError('not a Dec DRCS file')
    argreader = read_args(f, b';', b'{')
    dec_props = dict(zip(_DEC_PARMS[:-1], argreader))
    dec_props[_DEC_PARMS[-1]] = read_dscs_name(f)
    term = _ESC_END[esc]
    # really shld be ESC \ but we only check 1 char
    term = term[0]
    glyphdefs = read_args(f, b';', term)
    glyphdefs = list(glyphdefs)
    return glyphdefs, dec_props

def parse_drcs_glyphs(glyphdefs, first_codepoint):
    """Convert DRCS glyphs to monobit glyphs."""
    glyphbytes = (
        tuple(
            tuple(_b - ord(b'?') for _b in _block)
            for _block in _glyph.split(b'/')
        )
        for _glyph in glyphdefs
    )
    glyphbytes = (tuple(zip(*_g)) for _g in glyphbytes)
    glyphstrs = (
        tuple(
            ''.join(f'{_b:06b}' for _b in reversed(_pair))
            for _pair in _glyph
        )
        for _glyph in glyphbytes
    )
    glyphs = (
        Glyph(
            tuple(_c == '1' for _c in _row)
            for _row in _glyph
        )
        for _glyph in glyphstrs
    )
    glyphs = tuple(
        _g.rotate(turns=3).modify(codepoint=_cp)
        for _cp, _g in enumerate(glyphs, first_codepoint)
    )
    return glyphs

def parse_drcs_props(dec_props):
    """Convert DRCS properties to yaff properties."""
    # determine glyph count from Pcss
    count = 96 if int(dec_props['Pcss']) else 94
    # determine starting codepoint from Pcn
    pcn = int(dec_props['Pcn'])
    first_codepoint = pcn + 0x20
    if count == 94 and not pcn:
        first_codepoint = 0x21
    # determine glyph width from Pcmw and Pw
    target_cols = 132 if int(dec_props['Pw']) else 80
    pcmw = int(dec_props['Pcmw'])
    width, height = 0, 0
    if not pcmw:
        width = 9 if target_cols == 132 else 15
    elif 15 >= pcmw >= 5:
        width = pcmw
    elif 4 >= pcmw >= 2:
        width = 3 + pcmw
        height = 10
    else:
        logging.warning('illegal value %d for Pcmw', pcmw)
    # determine glyph height from Pcmh
    if not height:
        height = int(dec_props['Pcmh']) or 12
    props = Props(
        encoding='ascii',
        name=dec_props['Dscs'].decode('ascii'),
        raster_size=(width, height),
        device=f'{target_cols}-column terminal',
    )
    # preserve unparsed properties
    props.dec_drcs = Props(**{
        _k: _v.decode('ascii')
        for _k, _v in dec_props.items()
        if _k in ('Pfn', 'Pe', 'Pt')
    })
    return props, count, first_codepoint


