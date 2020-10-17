"""
monobit.hex - Unifont Hex format
(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# HEX format documentation
# http://czyborra.com/unifont/

import os
import logging
import string

from .text import clean_comment, split_global_comment, write_comments
from .formats import Loaders, Savers
from .font import Font, Label
from .glyph import Glyph


@Loaders.register('hext', name='PC-BASIC Extended HEX')
def load_hext(instream):
    return load(instream)

@Loaders.register('hex', name='Unifont HEX')
def load_hex(instream):
    return load(instream)

def load(instream):
    """Load font from a .hex file."""
    label = None
    glyphs = []
    comments = {}
    labels = {}
    global_comment = []
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
        if label is None:
            global_comment, current_comment = split_global_comment(current_comment)
            global_comment = clean_comment(global_comment)
        # parse code line
        key, value = line.split(':', 1)
        value = value.strip()
        # may be on one of next lines
        while not value:
            value = instream.readline.strip()
        if len(value) < 64:
            # must be less than 32 pixels high, or we confuse it with 16-pixels wide standard
            width, height = 8, int(len(value)/2)
        else:
            width, height = 16, int(len(value)/4)
        current = len(glyphs)
        if (set(value) | set(key)) - set(string.hexdigits + ','):
            raise ValueError(f'Keys and values must be hexadecimal, found {key}:{value}')
        # unicode label
        label = Label.from_unicode(''.join(chr(int(_key, 16)) for _key in key.split(',')))
        labels[label] = len(glyphs)
        glyphs.append(Glyph.from_hex(value, width, height))
        comments[label] = clean_comment(current_comment)
        current_comment = []
    comments[None] = global_comment
    # preserve any comment at end of file
    comments[label].extend(clean_comment(current_comment))
    return Font(glyphs, labels, comments=comments)


@Savers.register('hex', multi=False)
def save(font, outstream):
    """Write font to a .hex file."""
    write_comments(outstream, font.get_comments(), comm_char='#', is_global=True)
    for label, char in font.iter_unicode():
        if len(label.unicode) > 1:
            logging.warning("Can't encode grapheme cluster %s in .hex file; skipping.", str(label))
            continue
        if char.height != 16 or char.width not in (8, 16):
            logging.warning(
                'Hex format only supports 8x16 or 16x16 glyphs, not {}x{}; skipping.'.format(
                    char.width, char.height
                )
            )
            logging.warning('%s %s', label, char.as_hex())
            continue
        _write_hex_extended(outstream, label, char)
    return font


@Savers.register('hext', multi=False)
def save_hext(font, outstream):
    """Write font to a .hex file."""
    write_comments(outstream, font.get_comments(), comm_char='#', is_global=True)
    for label, char in font.iter_unicode():
        if char.width not in (8, 16):
            logging.warning(
                'Hex format only supports 8x or 16x glyphs, not {}x{}; skipping.'.format(
                    char.width, char.height
                )
            )
            logging.warning('%s %s', label, char.as_hex())
            continue
        _write_hex_extended(outstream, label, char)
    return font

def _write_hex_extended(outstream, label, char):
    """Write font to a .hex file, extended syntax."""
    write_comments(outstream, char.comments, comm_char='#')
    hexlabel = u','.join(f'{ord(_c):04X}' for _c in label.unicode)
    hex = char.as_hex().upper()
    outstream.write('{}:{}'.format(hexlabel, hex))
    outstream.write('\n')
