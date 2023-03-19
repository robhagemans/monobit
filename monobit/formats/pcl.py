"""
monobit.formats.pcl - HP PCL soft fonts

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


import logging

from ..storage import loaders, savers
from ..magic import FileFormatError, Magic
from ..struct import big_endian as be
from ..glyph import Glyph
from ..font import Font
from ..properties import Props


@loaders.register(
    name='hppcl',
    magic=(
        b'\x1b)s' + Magic.offset(2) + b'W',
        b'\x1b)s' + Magic.offset(3) + b'W',
        b'\x1b)s' + Magic.offset(4) + b'W',
    ),
    patterns=('*.sft', '*.sfl', '*.sfp'),
)
def load_hppcl(instream):
    """Load a HP PCL soft font."""
    pre, esc_cmd = read_until(instream, b'\x1b', 3)
    if pre:
        logging.debug(pre)
    if esc_cmd != b'\x1b)s':
        raise FileFormatError('Not a PCL soft font')
    sizestr, _ = read_until(instream, b'W', 1)
    size = bytestr_to_int(sizestr)
    logging.debug('header size %d', size)
    fontdef = _BITMAP_FONT_DEF.read_from(instream)
    logging.debug(fontdef)
    if fontdef.descriptor_format not in (0, 5, 6, 7, 9, 12, 16, 20):
        raise FileFormatError('PCL soft font is not a bitmap font.')
    copyright, _ = read_until(instream, b'\x1b\x1a\0', 0)

    props = dict(
        name=fontdef.font_name.strip().decode('ascii', 'replace'),
        copyright=copyright.decode('ascii', 'replace'),
        x_height=fontdef.x_height//4,
        setwidth=_SETWIDTH_MAP.get(fontdef.width_type, ''),
        weight=_WEIGHT_MAP.get(fontdef.stroke_weight, ''),
        style=(
            'sans serif' if fontdef.serif_style & 64
            else 'serif' if fontdef.serif_style & 128 else ''
        ),
        cap_height=(fontdef.cap_height / 65536) * fontdef.height//4 or None,
        line_height=fontdef.text_height//4 or None,
        fontdef=Props(**vars(fontdef))
    )

    glyphs = []
    while True:
        skipped, esc_cmd = read_until(instream, b'\x1b', 3)
        if skipped:
            logging.debug('Skipped bytes: %s', skipped)
        if not esc_cmd:
            break
        if esc_cmd != b'\x1b*c':
            raise FileFormatError(f'Expected character code, got {esc_cmd}')
        codestr, _ = read_until(instream, b'Ee', 1)
        code = bytestr_to_int(codestr)
        skipped, esc_cmd = read_until(instream, b'\x1b', 3)
        if skipped:
            logging.debug('Skipped bytes: %s', skipped)
        if esc_cmd != b'\x1b(s':
            raise FileFormatError(f'Expected glyph definition, got {esc_cmd}')
        sizestr, _ = read_until(instream, b'W', 1)
        size = bytestr_to_int(sizestr)
        chardef = _LASERJET_CHAR_DEF.read_from(instream)
        glyphbytes = instream.read(size - _LASERJET_CHAR_DEF.size)
        glyph = Glyph.from_bytes(
            glyphbytes, width=chardef.character_width,
            left_bearing=chardef.left_offset,
            shift_up=chardef.top_offset-chardef.character_height,
            right_bearing=max(0, chardef.delta_x//4 - chardef.character_width - chardef.left_offset),
            codepoint=code,
            chardef=Props(**vars(chardef)),
        )
        glyphs.append(glyph)
    return Font(glyphs, **props)


_BITMAP_FONT_DEF = be.Struct(
    font_descriptor_size='uint16',
    descriptor_format='uint8',
    symbol_set_type='uint8',
    style_msb='uint8',
    reserved='uint8',
    baseline_position='uint16',
    cell_width='uint16',
    cell_height='uint16',
    orientation='uint8',
    spacing='uint8',
    symbol_set='uint16',
    pitch='uint16',
    height='uint16',
    x_height='uint16',
    width_type='uint8',
    style_lsb='uint8',
    stroke_weight='int8',
    typeface_lsb='uint8',
    typeface_msb='uint8',
    serif_style='uint8',
    quality='uint8',
    placement='int8',
    underline_position='int8',
    underline_thickness='uint8',
    text_height='uint16',
    text_width='uint16',
    first_code='uint16',
    last_code='uint16',
    pitch_extended='uint8',
    height_extended='uint8',
    cap_height='uint16',
    font_number='uint32',
    font_name='16s',
    # followed by optional copyright notice
)

_LASERJET_CHAR_DEF = be.Struct(
    format='uint8',
    continuation='uint8',
    descriptor_size='uint8',
    class_='uint8',
    orientation='uint8',
    reserved='uint8',
    left_offset='int16',
    top_offset='int16',
    character_width='uint16',
    character_height='uint16',
    delta_x='int16',
    # followed by character data
)

_LASERJET_CHAR_CONT = be.Struct(
    format='uint8',
    continuation='uint8',
    # followed by character data
)

_SETWIDTH_MAP = {
    -5: 'ultra-compressed',
    -4: 'ultra-condensed', # extra compressed
    -3: 'extra-condensed', # compressed
    -2: 'condensed',
    -1: 'semi-condensed',
    0: 'medium',
    1: 'semi-expanded',
    2: 'expanded',
    3: 'extra-expanded',
}

_WEIGHT_MAP = {
    -7: 'ultra-thin',
    -6: 'extra-thin',
    -5: 'thin',
    -4: 'extra-light',
    -3: 'light',
    -2: 'demi-light',
    -1: 'semi-light',
    0: 'regular', #Medium, Book, or Text
    1: 'semi-bold',
    2: 'demi-bold',
    3: 'bold',
    4: 'extra-bold',
    5: 'heavy', # Black
    6: 'extra-heavy', # Extra Black
    7: 'ultra-heavy', # Ultra Black
}


def read_until(instream, break_char, then_read=1):
    """Read bytes from stream until a given sentinel."""
    out = []
    c = instream.peek(1)[:1]
    while c and c not in break_char:
        out.append(instream.read(1))
        c = instream.peek(1)[:1]
    sep = instream.read(then_read)
    return b''.join(out), sep


def bytestr_to_int(bytestr):
    return int(bytestr.decode('ascii', 'replace'), 10)
