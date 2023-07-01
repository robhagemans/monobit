"""
monobit.formats.text.hex - Unifont Hex format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# HEX format documentation
# http://czyborra.com/unifont/

import logging
import string

from ...storage import loaders, savers
from ...magic import FileFormatError
from ...font import Font
from ...glyph import Glyph
from .draw import load_draw, DrawGlyph, DrawComment, Empty


@loaders.register(name='pcbasic',)
def load_hext(instream):
    """Load 8xN multi-cell font from PC-BASIC extended .HEX file."""
    return _load_hex(instream)

@loaders.register(
    name='unifont',
    patterns=('*.hex',),
)
def load_hex(instream):
    """Load 8x16 multi-cell font from Unifont .HEX file."""
    return _load_hex(instream)

@savers.register(linked=load_hex)
def save_hex(fonts, outstream):
    """Save 8x16 multi-cell font to Unifont .HEX file."""
    font = _validate(fonts)
    _save_hex(font, outstream.text, _fits_in_hex)

@savers.register(linked=load_hext)
def save_hext(fonts, outstream):
    """Save 8xN multi-cell font to PC-BASIC extended .HEX file."""
    font = _validate(fonts)
    _save_hex(font, outstream.text, _fits_in_hext)


# loader

def _load_hex(instream):
    """Load 8x16 multi-cell font from Unifont .HEX file."""
    return load_draw(
        instream.text, blocktypes=(HexGlyph, DrawComment, Empty), unicode=True
    )


class HexGlyph(DrawGlyph):

    def ends(self, line):
        # single line per glyph
        return True

    def get_value(self):
        key, _, value =  self.lines[0].partition(':')
        value = value.strip()
        num_bytes = len(value) // 2
        if num_bytes < 32:
            width, height = 8, num_bytes
        else:
            width, height = 16, num_bytes // 2
        return Glyph.from_hex(
            value, width, height,
            labels=(self.convert_key(key),),
        )


# saver

def _validate(fonts):
    """Check if font fits in file format."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to hex file.')
    font, = fonts
    if font.spacing not in ('character-cell', 'multi-cell'):
        raise FileFormatError(
            'This format only supports character-cell or multi-cell fonts.'
        )
    return font

def _save_hex(font, outstream, fits):
    """Save 8x16 multi-cell font to Unifont or PC-BASIC Extended .HEX file."""
    # fill out character cell including shifts, bearings and line height
    font = font.equalise_horizontal()
    # global comment
    if font.get_comment():
        outstream.write(_format_comment(font.get_comment(), comm_char='#') + '\n\n')
    # ensure unicode labels exist if encoding is defined
    font = font.label()
    # glyphs
    for glyph in font.glyphs:
        if not glyph.char:
            logging.warning('Skipping glyph without character label: %s', glyph.as_hex())
        elif not fits(glyph):
            logging.warning('Skipping %s: %s', glyph.char, glyph.as_hex())
        else:
            outstream.write(_format_glyph(glyph))

def _fits_in_hex(glyph):
    """Check if glyph fits in Unifont Hex format."""
    if len(glyph.char) > 1:
        logging.warning('Hex format does not support multi-codepoint grapheme clusters.')
        return False
    if glyph.height != 16 or glyph.width not in (8, 16):
        logging.warning(
            'Hex format only supports 8x16 or 16x16 glyphs, '
            f'glyph {glyph.char} is {glyph.width}x{glyph.height}.'
        )
        return False
    return True

def _fits_in_hext(glyph):
    """Check if glyph fits in PC-BASIC Extended Hex format."""
    if glyph.width not in (8, 16):
        logging.warning(
            'Extended Hex format only supports glyphs of width 8 or 16 pixels, '
            f'glyph {glyph.char} is {glyph.width}x{glyph.height}.'
        )
        return False
    if glyph.height >= 32:
        logging.warning(
            'Extended Hex format only supports glyphs less than 32 pixels high, '
            f'glyph {glyph.char} is {glyph.width}x{glyph.height}.'
        )
        return False
    return True

def _format_glyph(glyph):
    """Format glyph line for hex file."""
    return (
        # glyph comment
        ('' if not glyph.comment else '\n' + _format_comment(glyph.comment, comm_char='#') + '\n')
        + '{}:{}\n'.format(
            # label
            u','.join(f'{ord(_c):04X}' for _c in glyph.char),
            # hex code
            glyph.as_hex().upper()
        )
    )

def _format_comment(comment, comm_char):
    """Format a multiline comment."""
    return '\n'.join(f'{comm_char} {_line}' for _line in comment.splitlines())
