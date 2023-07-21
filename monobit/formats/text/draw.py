"""
monobit.formats.text.draw - visual-text formats

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string

from ...storage import loaders, savers
from ...font import Font
from ...glyph import Glyph
from ...labels import Tag, Char
from ...magic import FileFormatError
from ...encoding import charmaps
from ...binary import align


##############################################################################
# hexdraw

@loaders.register(
    name='hexdraw',
    patterns=('*.draw',),
)
def load_hexdraw(instream, ink:str='#', paper:str='-', unicode:bool=True):
    """
    Load font from a hexdraw file.

    ink: character used for inked/foreground pixels (default #)
    paper: character used for uninked/background pixels (default -)
    unicode: interpret codepoint as Unicode (default: True)
    """
    DrawGlyph.ink = ink
    DrawGlyph.paper = paper
    return load_draw(
        instream.text, blocktypes=(DrawGlyph, DrawComment, Empty),
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
    if len(fonts) > 1:
        raise FileFormatError("Can only save one font to hexdraw file.")
    _save_draw(fonts[0], outstream.text, ink=ink, paper=paper, unicode=unicode)


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
    if not unicode:
        glyphs = tuple(
            _g.label(codepoint_from=charmaps['unicode']).modify(char=None)
            for _g in glyphs
        )
    font = Font(
        glyphs,
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


###############################################################################
# mkwinfon .fd

from ...properties import Props
from ..windows import WEIGHT_MAP, CHARSET_MAP


FD_KEYS = {
    'facename',
    'copyright',
    'height',
    'ascent',
    'pointsize',
    'weight',
    'charset',
    'italic',
    'underline',
    'strikeout',
}

FD_CHAR_KEYS = {
    'char',
    'width',
}

@loaders.register(
    name='mkwinfon',
    patterns=('*.fd',),
)
def load_mkwinfon(instream):
    """Load font from a mkwinfon .fd file."""
    properties, glyphs, comments = _read_mkwinfon(instream.text)
    return _convert_mkwinfon(properties, glyphs, comments)


def _read_mkwinfon(text_stream):
    """Read a mkwinfon file into a properties object."""
    # this will be a list of tuples
    font_props = {_k: None for _k in FD_KEYS}
    font_comments = []
    glyphs = []
    glyph_props = {}
    current_comment = []
    for block in iter_blocks(text_stream, (MWFGlyph, MWFProperties, MWFComment, Empty)):
        if isinstance(block, MWFComment):
            if not glyphs:
                font_comments.extend(current_comment)
                current_comment = []
            current_comment.append(block.get_value())
        elif isinstance(block, MWFProperties):
            properties = block.get_value()
            if glyphs or 'char' in properties:
                glyph_props.update(properties)
            else:
                font_props.update(properties)
                if current_comment:
                    font_comments.extend(current_comment)
                    current_comment = []
        elif isinstance(block, MWFGlyph):
            if not glyphs and not font_comments:
                font_comments.extend(current_comment)
                current_comment = []
            glyphs.append(Glyph(
                block.get_value(), _0='0', _1='1',
                codepoint=glyph_props.pop('char', b''),
                comment='\n\n'.join(current_comment),
            ))
            glyph_props = {}
            current_comment = []
        elif isinstance(block, Unparsed):
            logging.debug('Unparsed lines: %s', block.get_value())
    font_comments.extend(current_comment)
    return Props(**font_props), glyphs, font_comments

def _convert_mkwinfon(props, glyphs, comments):
    mb_props = dict(
        name=props.facename,
        copyright=props.copyright,
        descent=int(props.height)-int(props.ascent),
        ascent=props.ascent,
        point_size=props.pointsize,
        weight=(
            None if props.weight is None else
            WEIGHT_MAP.get(round(max(100, min(900, int(props.weight))), -2), None)
        ),
        encoding=(
            None if props.charset is None else
            CHARSET_MAP.get(int(props.charset), None)
        ),
        comment='\n\n'.join(comments),
    )
    return Font(glyphs, **mb_props).label()


###############################################################################
# consoleet / vfontas / hxtools

from pathlib import Path
from ...containers.directory import Directory

@loaders.register(
    name='consoleet',
)
def load_clt(instream):
    """Load font from consoleet files."""
    # this format consists of separate image files, without a manifest
    # instream.where does not give the nearest enclosing container but the root where we're calling!
    # we also can't use a directory as instream as it would be recursively read
    container = instream.where
    glyphs = []
    for name in sorted(container):
        if Path(name).parent != Path(instream.name).parent:
            continue
        with container.open(name, mode='r') as stream:
            glyphs.append(_read_clt_glyph(stream))
    return Font(glyphs, source_name=Path(instream.name).parent)

def _read_clt_glyph(instream):
    text = instream.text
    name = instream.name
    codepoint = Path(name).stem
    magic = text.readline().strip()
    if magic != 'PCLT':
        return Glyph()
    width, _, height = text.readline().strip().partition(' ')
    glyphtext = text.read().splitlines()
    return Glyph(
        glyphtext, _0='.', _1='#',
        # encoding is not specified by spec or file - can be unicode or codepage
        codepoint=f'0x{codepoint}'
    ).shrink(factor_x=2)


###############################################################################
# psf2txt

PSFT_KEYS = {
    'Version',
    'Flags',
    'Length',
    'Width',
    'Height',
}

PSFT_CHAR_KEYS = {
    'Unicode',
}

@loaders.register(
    name='psf2txt',
    magic=(b'%PSF2',),
    patterns=('*.txt',),
)
def load_psf2txt(instream):
    """Load font from a psf2txt .txt file."""
    properties, glyphs, comments = _read_psf2txt(instream.text)
    return _convert_psf2txt(properties, glyphs, comments)


def _read_psf2txt(text_stream):
    """Read a psf2txt file into a properties object."""
    if text_stream.readline().strip() != '%PSF2':
        raise FileFormatError('Not a PSF2TXT file.')
    properties = {_k: None for _k in PSFT_KEYS}
    comment = []
    glyphs = []
    current_comment = comment
    current_props = properties
    for block in iter_blocks(text_stream, (PTSeparator, PTComment, PTGlyph, PTLabel, PTProperties, Empty)):
        if isinstance(block, PTSeparator):
            if glyphs:
                glyphs[-1] = glyphs[-1].modify(
                    comment='\n\n'.join(current_comment),
                    **current_props
                )
            else:
                properties.update(current_props)
            current_comment = []
            current_props = {}
        elif isinstance(block, PTComment):
            current_comment.append(block.get_value())
        elif isinstance(block, PTProperties):
            current_props.update(block.get_value())
        elif isinstance(block, PTGlyph):
            glyphs.append(Glyph(block.get_value(), _0='-', _1='#'))
        elif isinstance(block, PTLabel):
            glyphs[-1] = glyphs[-1].modify(labels=block.get_value())
        elif isinstance(block, Unparsed):
            logging.debug('Unparsed lines: %s', block.get_value())
    if current_comment or current_props:
        glyphs[-1] = glyphs[-1].modify(
            comment='\n\n'.join(current_comment),
            **current_props
        )
    return Props(**properties), glyphs, comment

def _convert_psf2txt(props, glyphs, comment):
    mb_props = dict(
        revision=props.Version,
        # ignore Flags, we don't need the others
    )
    return Font(glyphs, **mb_props, comment='\n\n'.join(comment))


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

    @staticmethod
    def convert_key(key):
        """Convert keys on input from .draw."""
        key = key.strip()
        try:
            return Char(''.join(chr(int(_key, 16)) for _key in key.split(',')))
        except (TypeError, ValueError):
            return Tag(key)


# mkwinfont block readers

class MWFGlyph(NonEmptyBlock):

    def starts(self, line):
        return line[:1] in ('0', '1')

    def ends(self, line):
        return line[:1] not in ('0', '1')

    def get_value(self):
        return tuple(_l.strip() for _l in self.lines)


class MWFProperties(NonEmptyBlock):

    def starts(self, line):
        return line[:1] in string.ascii_letters and ' ' in line

    def ends(self, line):
        return not self.starts(line)

    def get_value(self):
        return dict(_l.split(' ', 1) for _l in self.lines)

class MWFComment(DrawComment):
    pass


# psf2txt block readers

class PTSeparator(NonEmptyBlock):

    def starts(self, line):
        return line[:1] == '%'


class PTComment(NonEmptyBlock):

    def starts(self, line):
        return line.startswith('//')

    def ends(self, line):
        return not self.starts(line)

    def get_value(self):
        lines = tuple(_l.removeprefix('//') for _l in self.lines)
        if equal_firsts(lines) == ' ':
            lines = (_line[1:] for _line in lines)
        return '\n'.join(lines)


class PTGlyph(NonEmptyBlock):

    def starts(self, line):
        return line.startswith('Bitmap:')

    def ends(self, line):
        return line[:1] not in string.whitespace

    def append(self, line):
        line = line.rstrip('\\').strip()
        if line:
            self.lines.append(line)

    def get_value(self):
        _, _, value =  self.lines[0].partition(':')
        value = value.strip()
        lines = self.lines[1:]
        if value:
            lines = [value] + lines
        lines = tuple(_l.strip() for _l in lines)
        return lines


class PTProperties(NonEmptyBlock):

    def starts(self, line):
        return line[:1] in string.ascii_letters and ':' in line

    def ends(self, line):
        return not self.starts(line)

    def get_value(self):
        return dict((_e.strip() for _e in _l.split(':', 1)) for _l in self.lines)


class PTLabel(NonEmptyBlock):

    def starts(self, line):
        return line.startswith('Unicode:')

    def get_value(self):
        _, _, value =  self.lines[0].partition(':')
        value = value.strip()[1:-2].split('];[')
        return tuple(
            Char(''.join(
                chr(int(_cp, 16)) for _cp in _l.split('+'))
            )
            for _l in value
        )
