"""
monobit.hex - Unifont Hex format
(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging
import string

from .text import clean_comment, split_global_comment, write_comments
from .typeface import Typeface
from .font import Font
from .glyph import Glyph


@Typeface.loads('hex', name='Unifont HEX', encoding='utf-8-sig')
def load(instream):
    """Load font from a .hex file."""
    glyphs = {}
    comments = {}
    global_comment = []
    key = None
    current_comment = []
    for line in instream:
        line = line.rstrip('\r\n')
        if not line:
            # preserve empty lines if they separate comments
            if current_comment and current_comment[-1] != '':
                current_comment.append('')
            continue
        if line[0] not in string.hexdigits:
            current_comment.append(line)
            continue
        if key is None:
            global_comment, current_comment = split_global_comment(current_comment)
            global_comment = clean_comment(global_comment)
        # parse code line
        key, value = line.split(':', 1)
        value = value.strip()
        # may be on one of next lines
        while not value:
            value = instream.readline.strip()
        if (set(value) | set(key)) - set(string.hexdigits):
            raise ValueError('Keys and values must be hexadecimal.')
        key = int(key, 16)
        if len(value) == 32:
            width, height = 8, 16
        elif len(value) == 64:
            width, height = 16, 16
        else:
            raise ValueError('Hex strings must be 32 or 64 characters long.')
        glyphs[key] = Glyph.from_hex(value, width, height)
        comments[key] = clean_comment(current_comment)
        current_comment = []
    comments[None] = global_comment
    # preserve any comment at end of file
    comments[key].extend(clean_comment(current_comment))
    # convert to unicode labels
    labels = {'u+{:04x}'.format(_key): _i for _i, _key in enumerate(glyphs.keys())}
    glyphs = list(glyphs.values())
    return Typeface([Font(glyphs, labels, comments=comments)])


@Typeface.saves('hex', encoding='utf-8', multi=False)
def save(font, outstream):
    """Write font to a .hex file."""
    write_comments(outstream, font.get_comments(), comm_char='#', is_global=True)
    for label, char in font.iter_unicode():
        write_comments(outstream, char.comments, comm_char='#')
        if char.height != 16 or char.width not in (8, 16):
            raise ValueError(
                'Hex format only supports 8x16 or 16x16 glyphs, not {}x{}.'.format(
                    char.width, char.height
                )
            )
        # omit the 'u+' for .hex
        outstream.write('{}:{}'.format(label[2:].upper(), char.as_hex().upper()))
        outstream.write('\n')
    return font
