"""
monobit.formats.draw - Unifont HexDraw format

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


class DrawParams:
    """Parameters for hexdraw format."""
    separator = ':'
    comment = '%'
    tab = '\t'
    #ink = '#'
    #paper = '-'


##############################################################################
# interface

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
    return _load_text(
        instream.text,
        ink=ink, paper=paper,
        comment=DrawParams.comment,
        separator=DrawParams.separator
    )

@savers.register(linked=load_hexdraw)
def save_hexdraw(fonts, outstream, ink:str='#', paper:str='-'):
    """
    Save font to a hexdraw file.

    ink: character to use for inked/foreground pixels (default #)
    paper: character to use for uninked/background pixels (default -)
    """
    if len(fonts) > 1:
        raise FileFormatError("Can only save one font to hexdraw file.")
    _save_text(
        fonts[0], outstream.text,
        ink=ink, paper=paper, comment=DrawParams.comment
    )


##############################################################################
##############################################################################
# read file


def _load_text(text_stream, *, ink, paper, comment, separator):
    """Parse a hexdraw-style file."""
    comments = []
    glyphs = []
    label = ''
    glyphlines = []
    for line in text_stream:
        line = line.rstrip()
        # anything not starting with whitespace or a number is a comment
        if line and line[:1] not in string.hexdigits + string.whitespace:
            if line.startswith(comment):
                line = line[len(comment):]
            comments.append(line)
            continue
        stripline = line.lstrip()
        # no leading whitespace?
        if line and len(line) == len(stripline):
            if glyphlines:
                glyphs.append(Glyph(
                    tuple(glyphlines), _0=paper, _1=ink,
                    labels=(convert_key(label),)
                ))
                glyphlines = []
            label, _, stripline = line.partition(separator)
            stripline = stripline.lstrip()
        if stripline and len(line) != len(stripline):
            glyphlines.append(stripline)
    if glyphlines:
        glyphs.append(Glyph(
            tuple(glyphlines), _0=paper, _1=ink,
            labels=(convert_key(label),)
        ))
    comments = normalise_comment(comments)
    return Font(glyphs, comment=comments)


def convert_key(key):
    """Convert keys on input from .draw."""
    try:
        return Char(chr(int(key, 16)))
    except (TypeError, ValueError):
        return Tag(key)


##############################################################################
##############################################################################
# write file


def _save_text(font, outstream, *, ink, paper, comment):
    """Write one font to a plaintext stream as hexdraw."""
    font = font.equalise_horizontal()
    # ensure char labels are set
    font = font.label(char_from=font.encoding)
    # write global comment
    if font.get_comment():
        outstream.write(
            format_comment(font.get_comment(), comment_char='#') + '\n',
            comment
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
            glyphtxt = glyph.as_text(
                start=DrawParams.tab, ink=ink, paper=paper, end='\n'
            )
            outstream.write(f'\n{ord(glyph.char):04x}{DrawParams.separator}')
            outstream.write(glyphtxt)


###############################################################################
# mkwinfont .fd

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


def _add_key_value(line, keyset, target):
    for key in keyset:
        if line.startswith(key):
            _, _, value = line.partition(' ')
            target[key] = value
            return True
    return False

@loaders.register(
    name='mkwinfont',
    patterns=('*.fd',),
)
def load_mkwinfont(instream):
    """Load font from a mkwinfont .fd file."""
    properties, glyphs, comments = _read_mkwinfont(instream.text)
    return _convert_mkwinfont(properties, glyphs, comments)


def _read_mkwinfont(text_stream):
    """Read a mkwinfont file into a properties object."""
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
            current_glyph.append(line)
            line = text_stream.readline()
        if current_glyph:
            glyphs.append((current_glyph, Props(**current_props)))
            current_glyph = []
            current_props = {}
    return Props(**properties), glyphs, comments

def _convert_mkwinfont(props, glyphs, comments):
    mb_props = dict(
        name=props.facename,
        copyright=props.copyright,
        descent=int(props.height)-int(props.ascent),
        ascent=props.ascent,
        point_size=props.pointsize,
        weight=_WEIGHT_MAP.get(round(max(100, min(900, props.weight or 400)), -2), ''),
        encoding=CHARSET_MAP.get(props.charset, None),
        comment=normalise_comment(comments),
    )
    mb_glyphs = tuple(
        Glyph(_rows, _0='0', _1='1', codepoint=_props['char'])
        for _rows, _props in glyphs
    )
    return Font(mb_glyphs, **mb_props)
