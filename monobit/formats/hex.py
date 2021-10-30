"""
monobit.hex - Unifont Hex format

(c) 2019--2021 Rob Hagemans
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
from .yaff import write_comments


@loaders.register('hext', name='PC-BASIC Extended HEX')
def load_hext(instream, where=None):
    """Load 8xN multi-cell font from PC-BASIC extended .HEX file."""
    return load(instream.text)

@loaders.register('hex', name='Unifont HEX')
def load_hex(instream, where=None):
    """Load 8x16 multi-cell font from Unifont .HEX file."""
    return load(instream.text)

def load(instream):
    """Load font from a .hex file."""
    global_comment = []
    glyphs = []
    current_comment = []
    for line in instream:
        line = line.rstrip('\r\n')
        if not line:
            # preserve empty lines if they separate comments
            if current_comment and current_comment[-1] != '':
                current_comment.append('')
            continue
        # pass through lines without : as comments - allows e.g. to convert diffs, like hexdraw
        if line[0] == '#' or ':' not in line:
            current_comment.append(line)
            continue
        # parse code line
        key, value = line.rsplit(':', 1)
        value = value.strip()
        # may be on one of next lines
        while not value:
            value = instream.readline().strip()
        if len(value) < 64:
            # must be less than 32 pixels high, or we confuse it with 16-pixels wide standard
            width, height = 8, int(len(value)/2)
        else:
            width, height = 16, int(len(value)/4)
        if set(value) - set(string.hexdigits + ','):
            # not a valid line, treat as comment
            current_comment.append(line)
            #raise ValueError(f'Keys and values must be hexadecimal, found {key}:{value}')
            continue
        if not glyphs and current_comment:
            global_comment, current_comment = split_global_comment(current_comment)
            global_comment = clean_comment(global_comment)
        try:
            char = ''.join(chr(int(_key, 16)) for _key in key.split(','))
        except ValueError:
            char = ''
        current_glyph = Glyph.from_hex(value, width, height)
        current_glyph = current_glyph.set_annotations(
            char=char, tags=([key] if not char else []),
            comments=clean_comment(current_comment)
        )
        glyphs.append(current_glyph)
        current_comment = []
    comments = global_comment
    # preserve any comment at end of file as part of global comment
    comments.extend(clean_comment(current_comment))
    return Font(glyphs, comments=comments, properties=dict(encoding='unicode'))


def clean_comment(comment):
    """Remove leading characters from comment."""
    while comment and not comment[-1]:
        comment = comment[:-1]
    if not comment:
        return []
    comment = [(_line if _line else '') for _line in comment]
    # remove "comment char" - non-alphanumeric shared first character
    firsts = [_line[0:1] for _line in comment if _line]
    if len(set(firsts)) == 1 and firsts[0] not in string.ascii_letters + string.digits:
        comment = [_line[1:] for _line in comment]
    # normalise leading whitespace
    if all(_line.startswith(' ') for _line in comment if _line):
        comment = [_line[1:] for _line in comment]
    return comment

def split_global_comment(comment):
    while comment and not comment[-1]:
        comment = comment[:-1]
    try:
        splitter = comment[::-1].index('')
    except ValueError:
        global_comment = comment
        comment = []
    else:
        global_comment = comment[:-splitter-1]
        comment = comment[-splitter:]
    return global_comment, comment


##############################################################################
# saver

@savers.register(linked=load_hex)
def save_hex(fonts, outstream, where=None):
    """Save 8x16 multi-cell font to Unifont .HEX file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to hex file.')
    font = fonts[0]
    if font.spacing not in ('character-cell', 'multi-cell'):
        raise FileFormatError(
            'This format only supports character-cell or multi-cell fonts.'
        )
    outstream = outstream.text
    write_comments(outstream, font.get_comments(), comm_char='#', is_global=True)
    for glyph in font.glyphs:
        if len(glyph.char) > 1:
            logging.warning(
                "Can't encode grapheme cluster %s in .hex file; skipping.",
                ascii(glyph.char)
            )
            continue
        if glyph.height != 16 or glyph.width not in (8, 16):
            logging.warning(
                'Hex format only supports 8x16 or 16x16 glyphs, not {}x{}; skipping.'.format(
                    glyph.width, glyph.height
                )
            )
            logging.warning('%s %s', glyph.char, glyph.as_hex())
            continue
        _write_hex_extended(outstream, glyph.char, glyph)


@savers.register(linked=load_hext)
def save_hext(fonts, outstream, where=None):
    """Save 8xN multi-cell font to PC-BASIC extended .HEX file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to hex file.')
    font = fonts[0]
    if font.spacing not in ('character-cell', 'multi-cell'):
        raise FileFormatError(
            'This format only supports character-cell or multi-cell fonts.'
        )
    outstream = outstream.text
    write_comments(outstream, font.get_comments(), comm_char='#', is_global=True)
    for glyph in font.glyphs:
        if glyph.width not in (8, 16):
            logging.warning(
                'Hex format only supports 8x or 16x glyphs, not {}x{}; skipping.'.format(
                    glyph.width, glyph.height
                )
            )
            logging.warning('%s %s', glyph.char, glyph.as_hex())
            continue
        _write_hex_extended(outstream, glyph.char, glyph)

def _write_hex_extended(outstream, unicode, glyph):
    """Write character to a .hex file, extended syntax."""
    write_comments(outstream, glyph.comments, comm_char='#')
    hexlabel = u','.join(f'{ord(_c):04X}' for _c in unicode)
    hex = glyph.as_hex().upper()
    outstream.write('{}:{}'.format(hexlabel, hex))
    outstream.write('\n')
