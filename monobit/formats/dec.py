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
    if not dcs in (b'\x90', b'\x1bP'):
        raise FileFormatError('not a Dec DRCS file')
    dec_parms = ('Pfn', 'Pcn', 'Pe', 'Pcmw', 'Pw', 'Pt', 'Pcmh', 'Pcss')
    argreader = read_args(f, b';', b'{')
    dec_props = dict(zip(dec_parms, argreader))
    dec_props['Dscs'] = read_dscs_name(f)
    # really shld be ESC \ but we only check 1 char
    term = b'\x1b' if esc else b'\x9c'
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


