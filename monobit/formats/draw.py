"""
monobit.formats.draw - visual-text formats

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..labels import Tag, Char
from ..magic import FileFormatError
from .yaff import format_comment, normalise_comment


##############################################################################
# hexdraw

@loaders.register(
    name='hexdraw',
    patterns=('*.draw',),
)
def load_hexdraw(instream, ink:str='#', paper:str='-'):
    """
    Load font from a hexdraw file.

    ink: character used for inked/foreground pixels (default #)
    paper: character used for uninked/background pixels (default -)
    """
    return _load_draw(instream.text, ink=ink, paper=paper)

@savers.register(linked=load_hexdraw)
def save_hexdraw(fonts, outstream, ink:str='#', paper:str='-'):
    """
    Save font to a hexdraw file.

    ink: character to use for inked/foreground pixels (default #)
    paper: character to use for uninked/background pixels (default -)
    """
    if len(fonts) > 1:
        raise FileFormatError("Can only save one font to hexdraw file.")
    _save_draw(fonts[0], outstream.text, ink=ink, paper=paper)


# read hexdraw file

def _load_draw(text_stream, *, ink, paper):
    """Parse a hexdraw-style file."""
    blocks = tuple(iter_blocks(text_stream))
    comment = '\n'.join(
        _l
        for _b in blocks if _b.is_comment()
        for _l in _b.get_comment_value()
    )
    glyphs = (
        Glyph(
            _b.get_value(), _0=paper, _1=ink,
            labels=(convert_key(_b.get_key()),)
        )
        for _b in blocks if _b.is_glyph()
    )
    return Font(glyphs, comment=comment)


def convert_key(key):
    """Convert keys on input from .draw."""
    try:
        return Char(chr(int(key, 16)))
    except (TypeError, ValueError):
        return Tag(key)


# write hexdraw file

def _save_draw(font, outstream, *, ink, paper):
    """Write one font to a plaintext stream as hexdraw."""
    font = font.equalise_horizontal()
    # ensure char labels are set
    font = font.label(char_from=font.encoding, match_whitespace=False, match_graphical=False)
    # write global comment
    if font.get_comment():
        outstream.write(
            format_comment(font.get_comment(), comment_char='%') + '\n'
        )
    # write glyphs
    for i, glyph in enumerate(font.glyphs):
        if not glyph.char:
            logging.warning(
                "Can't encode glyph without Unicode character label in .draw file;"
                " skipping index %d", i
            )
        elif len(glyph.char) > 1:
            logging.warning(
                "Can't encode grapheme cluster %s in .draw file; skipping.",
                ascii(glyph.char)
            )
        else:
            glyphtxt = glyph.as_text(start='\t', ink=ink, paper=paper, end='\n')
            outstream.write(f'\n{ord(glyph.char):04x}:')
            outstream.write(glyphtxt)


###############################################################################
# mkwinfon .fd

from ..properties import Props
from .windows.fnt import _WEIGHT_MAP, CHARSET_MAP


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


def _add_key_value(line, keyset, target, sep=' '):
    for key in keyset:
        if line.startswith(key):
            _, _, value = line.partition(sep)
            target[key.strip()] = value.strip()
            return True
    return False

def _read_mkwinfon(text_stream):
    """Read a mkwinfon file into a properties object."""
    comment = '#'
    ink = '1'
    paper = '0'
    comments = []
    glyphs = []
    properties = {_k: None for _k in FD_KEYS}
    current_props = {}
    current_glyph = []
    while True:
        line = text_stream.readline()
        if not line:
            break
        line = line.rstrip()
        if not line:
            continue
        if line.startswith(comment):
            comments.append(line.removeprefix(comment))
            continue
        stripline = line.lstrip()
        if _add_key_value(line, FD_KEYS, properties):
            continue
        if _add_key_value(line, FD_CHAR_KEYS, current_props):
            continue
        while line[:1] in (paper, ink):
            current_glyph.append(line.strip())
            line = text_stream.readline()
        if current_glyph:
            glyphs.append((current_glyph, Props(**current_props)))
            current_glyph = []
            current_props = {}
    return Props(**properties), glyphs, comments

def _convert_mkwinfon(props, glyphs, comments):
    mb_props = dict(
        name=props.facename,
        copyright=props.copyright,
        descent=int(props.height)-int(props.ascent),
        ascent=props.ascent,
        point_size=props.pointsize,
        weight=(
            None if props.weight is None else
            _WEIGHT_MAP.get(round(max(100, min(900, int(props.weight))), -2), None)
        ),
        encoding=(
            None if props.charset is None else
            CHARSET_MAP.get(int(props.charset), None)
        ),
        comment=normalise_comment(comments),
    )
    mb_glyphs = tuple(
        Glyph(_rows, _0='0', _1='1', codepoint=_props['char'])
        for _rows, _props in glyphs
    )
    return Font(mb_glyphs, **mb_props).label()


###############################################################################
# consoleet / vfontas / hxtools

from pathlib import Path
from ..containers.directory import Directory

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
    comment = '//'
    ink = '#'
    paper = '-'
    comments = []
    glyphs = []
    properties = {_k: None for _k in PSFT_KEYS}
    if text_stream.readline().strip() != '%PSF2':
        raise FileFormatError('Not a PSF2TXT file.')
    while True:
        line = text_stream.readline()
        if not line or line.startswith('%'):
            break
        line = line.rstrip()
        if not line:
            continue
        if line.startswith(comment):
            comments.append(line.removeprefix(comment))
            continue
        stripline = line.lstrip()
        if _add_key_value(line, PSFT_KEYS, properties):
            continue
    current_props = {}
    current_glyph = []
    while True:
        line = text_stream.readline()
        if not line:
            glyphs.append((current_glyph, Props(**current_props)))
            break
        if line.startswith(comment):
            comments.append(line.removeprefix(comment))
            continue
        if line.startswith('Bitmap:'):
            line = line.removeprefix('Bitmap:')
            while line.strip()[:1] in (paper, ink):
                line = line.strip()
                line = line.rstrip('\\').strip()
                current_glyph.append(line)
                line = text_stream.readline()
        if _add_key_value(line, PSFT_CHAR_KEYS, current_props):
            continue
        if line.startswith('%'): # and current_glyph:
            glyphs.append((current_glyph, Props(**current_props)))
            current_glyph = []
            current_props = {}
    return Props(**properties), glyphs, comments


def _convert_psf2txt(props, glyphs, comments):
    mb_props = dict(
        revision=props.Version,
        # ignore Flags, we don't need the others
    )
    labels = tuple(
        _props.Unicode.strip()[1:-2].split('];[')
        for _, _props in glyphs
    )
    labels = tuple(
        tuple(
            Char(''.join(
                chr(int(_cp, 16)) for _cp in _l.split('+'))
            )
            for _l in _llist
        )
        for _llist in labels
    )
    mb_glyphs = tuple(
        Glyph(_rows, _0='-', _1='#', labels=_labels)
        for _labels, (_rows, _props) in zip(labels, glyphs)
    )
    return Font(mb_glyphs, **mb_props)


##############################################################################
# common utilities

def iter_blocks(text_stream):
    block = BlockBuilder()
    for line in text_stream:
        while not block.append(line):
            yield block
            block = BlockBuilder()
    yield block


class BlockBuilder:
    notcomment = string.hexdigits + string.whitespace

    def __init__(self):
        self.lines = []

    def append(self, line):
        if self.ends(line):
            return False
        line = line.rstrip()
        if line:
            self.lines.append(line)
        return True

    def ends(self, line):
        if not self.lines:
            return False
        if self.lines[-1][:1] not in self.notcomment:
            return not line[:1] not in self.notcomment
        return not line[:1] in string.whitespace


    def is_comment(self):
        return self.lines and self.lines[-1][:1] not in self.notcomment

    def get_comment_value(self):
        lines = tuple(self.lines)
        first = equal_firsts(lines)
        if first and first not in string.ascii_letters + string.digits:
            lines = (_line[1:] for _line in lines)
        if equal_firsts(lines) == ' ':
            lines = (_line[1:] for _line in lines)
        return lines

    def is_glyph(self):
        return self.lines and self.lines[0][0] in string.hexdigits

    def get_value(self):
        _, _, value =  self.lines[0].partition(':')
        value = value.strip()
        lines = self.lines[1:]
        if value:
            lines = [value] + lines
        lines = tuple(_l.strip() for _l in lines)
        return lines

    def get_key(self):
        key, _, _ =  self.lines[0].partition(':')
        return key


def equal_firsts(lines):
    first_chars = set(_line[:1] for _line in lines)
    if len(first_chars) == 1:
        return first_chars.pop()
    return None
