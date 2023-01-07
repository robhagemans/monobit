"""
monobit.hex - Unifont Hex format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# HEX format documentation
# http://czyborra.com/unifont/

import logging
import string

from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph



@loaders.register('hext', name='hext')
def load_hext(instream, where=None):
    """Load 8xN multi-cell font from PC-BASIC extended .HEX file."""
    return _load_hex(instream.text)

@loaders.register('hex', name='hex')
def load_hex(instream, where=None):
    """Load 8x16 multi-cell font from Unifont .HEX file."""
    return _load_hex(instream.text)

@savers.register(linked=load_hex)
def save_hex(fonts, outstream, where=None):
    """Save 8x16 multi-cell font to Unifont .HEX file."""
    font = _validate(fonts)
    _save_hex(font, outstream.text, _fits_in_hex)

@savers.register(linked=load_hext)
def save_hext(fonts, outstream, where=None):
    """Save 8xN multi-cell font to PC-BASIC extended .HEX file."""
    font = _validate(fonts)
    _save_hex(font, outstream.text, _fits_in_hext)


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


##############################################################################
# loader

def _load_hex(instream):
    """Load font from a .hex file."""
    global_comment = []
    glyphs = []
    comment = []
    for line in instream:
        line = line.rstrip('\r\n')
        if (
                # preserve empty lines if they separate comments
                (not line and comment and comment[-1] != '')
                or line and (
                    # marked as comment
                    line[0] == '#'
                    # pass through lines without : as comments -
                    # allows e.g. to convert diffs, like hexdraw
                    or ':' not in line
                )
            ):
            comment.append(line)
        elif line:
            # parse code line
            key, value = line.rsplit(':', 1)
            value = value.strip()
            if set(value) - set(string.hexdigits + ','):
                # not a valid line, treat as comment
                comment.append(line)
            else:
                # when first glyph is found,
                # split comment lines between global and glyph
                if not glyphs and comment:
                    global_comment, comment = split_global_comment(comment)
                glyphs.append(_convert_glyph(key, value, comment))
                comment = []
    # preserve any comment at end of file as part of global comment
    global_comment = '\n'.join([*_clean_comment(global_comment), *_clean_comment(comment)])
    return Font(glyphs, comment=global_comment, encoding='unicode')


def _convert_label(key):
    """Ctreate char label from key string."""
    try:
        return ''.join(chr(int(_key, 16)) for _key in key.split(','))
    except ValueError:
        return ''

def _convert_glyph(key, value, comment):
    """Create Glyph object from key string and hex value."""
    # determine geometry
    # two standards: 8-pix wide, or 16-pix wide
    # if height >= 32, they conflict
    num_bytes = len(value) // 2
    if num_bytes < 32:
        width, height = 8, num_bytes
    else:
        width, height = 16, num_bytes // 2
    # get labels
    char = _convert_label(key)
    return Glyph.from_hex(value, width, height,
        char=char, tag=(key if not char else ''),
        comment='\n'.join(_clean_comment(comment))
    )


def _clean_comment(lines):
    """Remove leading characters from comment."""
    while lines and not lines[-1]:
        lines = lines[:-1]
    if not lines:
        return []
    lines = [_line or '' for _line in lines]
    # remove "comment char" - non-alphanumeric shared first character
    firsts = tuple(set(_line[:1] for _line in lines if _line))
    if len(firsts) == 1 and firsts[0] not in string.ascii_letters + string.digits:
        lines = [_line[1:] for _line in lines]
    # remove one leading space
    if all(_line.startswith(' ') for _line in lines if _line):
        lines = [_line[1:] for _line in lines]
    return lines

def split_global_comment(lines):
    """Split top comments into global and first glyph comment."""
    while lines and not lines[-1]:
        lines = lines[:-1]
    try:
        splitter = lines[::-1].index('')
    except ValueError:
        global_comment = lines
        lines = []
    else:
        global_comment = lines[:-splitter-1]
        lines = lines[-splitter:]
    return global_comment, lines


##############################################################################
# saver

def _save_hex(font, outstream, fits):
    """Save 8x16 multi-cell font to Unifont or PC-BASIC Extended .HEX file."""
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
