"""
monobit.storage.formats.text.draw - hexdraw format

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string

from monobit.storage.base import loaders, savers
from monobit.storage import FileFormatError
from monobit.core import Font, Glyph, Tag, Char
from monobit.encoding import encodings
from monobit.base.binary import align

from monobit.storage.utils.limitations import ensure_single


##############################################################################
# hexdraw

@loaders.register(
    name='hexdraw',
    patterns=('*.draw',),
    text=True,
)
def load_hexdraw(
        instream, ink:str='#', paper:str='-', unicode:bool=True, base:int=16,
    ):
    """
    Load font from a hexdraw or similar text-based file.

    ink: character used for inked/foreground pixels (default #)
    paper: character used for uninked/background pixels (default -)
    unicode: interpret codepoint as Unicode (default: True)
    base: representational base for codepoint (default: 16 for hexadecimal)
    """
    class CustomGlyph(DrawGlyph): pass
    CustomGlyph.ink = ink
    CustomGlyph.paper = paper
    CustomGlyph.base = base
    return load_draw(
        instream.text, blocktypes=(CustomGlyph, DrawComment, Empty),
        unicode=unicode
    )


@savers.register(linked=load_hexdraw)
def save_hexdraw(fonts, outstream, ink:str='#', paper:str='-', unicode:bool=True):
    """
    Save font to a hexdraw file.

    ink: character to use for inked/foreground pixels (default #)
    paper: character to use for uninked/background pixels (default -)
    unicode: use unicode char labels for codepoints (default: True)
    """
    font = ensure_single(fonts)
    _save_draw(font, outstream.text, ink=ink, paper=paper, unicode=unicode)


# read hexdraw file

def load_draw(text_stream, *, blocktypes, unicode):
    """Parse a hexdraw-style file."""
    glyphs = []
    font_comments = []
    current_comment = []
    for block in iter_blocks(text_stream, blocktypes):
        if isinstance(block, DrawComment):
            if not glyphs:
                font_comments.extend(current_comment)
                current_comment = []
            current_comment.append(block.get_value())
        elif isinstance(block, DrawGlyph):
            if not glyphs and not font_comments:
                font_comments.extend(current_comment)
                current_comment = []
            glyphs.append(block.get_value().modify(
                comment='\n\n'.join(current_comment),
            ))
            current_comment = []
        elif isinstance(block, Unparsed):
            logging.debug('Unparsed lines: %s', block.get_value())
    font_comments.extend(current_comment)
    if unicode:
        encoding = 'unicode'
    else:
        encoding = ''
        glyphs = tuple(
            _g.label(codepoint_from=encodings['unicode']).modify(char=None)
            for _g in glyphs
        )
    font = Font(
        glyphs,
        encoding=encoding,
        comment='\n\n'.join(font_comments)
    )
    return font


# write hexdraw file

def _save_draw(font, outstream, *, ink, paper, unicode):
    """Write one font to a plaintext stream as hexdraw."""
    font = font.equalise_horizontal()
    if unicode:
        # ensure char labels are set
        font = font.label(char_from=font.encoding, match_whitespace=False, match_graphical=False)
    # write global comment
    if font.get_comment():
        outstream.write(
            format_comment(font.get_comment(), comment_char='%') + '\n'
        )
    # write glyphs
    for i, glyph in enumerate(font.glyphs):
        if unicode:
            char = glyph.char
        else:
            cpbytes = bytes(glyph.codepoint)
            cpbytes = cpbytes.rjust(align(len(cpbytes), 2), b'\0')
            char = cpbytes.decode('utf-32-be')
        if not char:
            logging.warning(
                "Can't encode glyph without Unicode character label in .draw file;"
                " skipping index %d", i
            )
        elif len(char) > 1:
            logging.warning(
                "Can't encode grapheme cluster %s in .draw file; skipping.",
                ascii(char)
            )
        else:
            glyphtxt = glyph.as_text(start='\t', ink=ink, paper=paper, end='\n')
            outstream.write(f'\n{ord(char):04x}:')
            outstream.write(glyphtxt)


def format_comment(comments, comment_char):
    """Format a multiline comment."""
    return '\n'.join(
        f'{comment_char} {_line}'
        for _line in comments.splitlines()
    )


##############################################################################
# common utilities and reader classes

def iter_blocks(text_stream, classes):
    block = BlockBuilder(classes)
    for line in text_stream:
        while not block.append(line.rstrip('\r\n')):
            yield block.emit()
            block = BlockBuilder(classes)
    if block:
        yield block.emit()


class BlockBuilder:

    def __init__(self, classes):
        self.block = None
        self.classes = (*classes, Unparsed)

    def __bool__(self):
        return self.block is not None

    def append(self, line):
        if not self.block:
            for blocktype in self.classes:
                try:
                    self.block = blocktype(line)
                    return True
                except ValueError:
                    pass
            else:
                # this should not happen - BaseBlock absorbs
                raise ValueError('unparsed block')
        if self.block.ends(line):
            return False
        self.block.append(line)
        return True

    def emit(self):
        return self.block


class BaseBlock:

    def __init__(self, line):
        if not self.starts(line):
            raise ValueError(f'{line:r} cannot start a {type(self).__name__}')
        self.lines = []
        self.append(line)

    def __repr__(self):
        return f'{type(self).__name__}({repr(self.lines)})'

    def starts(self, line):
        return True

    def ends(self, line):
        return True

    def append(self, line):
        self.lines.append(line)

    def get_value(self):
        return tuple(self.lines)


class Unparsed(BaseBlock):
    pass


class Empty(BaseBlock):

    def starts(self, line):
        return not line


class NonEmptyBlock(BaseBlock):

    def append(self, line):
        line = line.rstrip()
        if line:
            self.lines.append(line)


# draw format block readers


class DrawComment(NonEmptyBlock):

    notcomment = string.hexdigits + string.whitespace

    def starts(self, line):
        return line[:1] not in self.notcomment

    def ends(self, line):
        return not self.starts(line)

    def get_value(self):
        lines = tuple(self.lines)
        first = equal_firsts(lines)
        if first and first not in string.ascii_letters + string.digits:
            lines = tuple(_line[1:] for _line in lines)
        if equal_firsts(lines) == ' ':
            lines = (_line[1:] for _line in lines)
        return '\n'.join(lines)

def equal_firsts(lines):
    first_chars = set(_line[:1] for _line in lines if _line)
    if len(first_chars) == 1:
        return first_chars.pop()
    return None


class DrawGlyph(NonEmptyBlock):
    paper = '-'
    ink = '#'

    # base for codepoint. default: hexadecimal
    base = 16

    def starts(self, line):
        return line and line[:1] in string.hexdigits

    def ends(self, line):
        # empty or non-indented
        return not line[:1] in string.whitespace

    def get_value(self):
        key, _, value =  self.lines[0].partition(':')
        value = value.strip()
        lines = self.lines[1:]
        if value:
            lines = [value] + lines
        lines = tuple(_l.strip() for _l in lines)
        return Glyph(
            lines, _0=self.paper, _1=self.ink,
            labels=(self.convert_key(key),),
        )

    @classmethod
    def convert_key(cls, key):
        """Convert keys on input from .draw."""
        key = key.strip()
        try:
            return Char(''.join(
                chr(int(_key, cls.base))
                for _key in key.split(',')
            ))
        except (TypeError, ValueError):
            return Tag(key)
