"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..labels import Tag, Char
from ..streams import FileFormatError
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

@loaders.register('draw', 'text', 'txt', name='hexdraw')
def load_hexdraw(
        instream, where=None,
        ink:str='#', paper:str='-'
    ):
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
def save_hexdraw(
        fonts, outstream, where=None,
        ink:str='#', paper:str='-'
    ):
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
        if line.startswith(comment):
            comments.append(line[len(comment):])
        line = line.rstrip()
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
        if len(line) != len(stripline):
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
    # ensure char labels are set
    font = font.label(char_from=font.encoding)
    # write global comment
    if font.get_comment():
        outstream.write(
            format_comment(font.get_comment(), comment_char='#') + '\n',
            comment
        )
    # write glyphs
    for glyph in font.glyphs:
        if not glyph.char:
            logging.warning(
                "Can't encode glyph without Unicode character label in .draw file;"
                " skipping\n%s\n",
                glyph
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
