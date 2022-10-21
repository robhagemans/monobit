"""
monobit.yaff - monobit-yaff and Unifont HexDraw formats

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..storage import loaders, savers
from .yaff import TextReader, TextConverter, TextWriter


##############################################################################
# interface

@loaders.register('draw', 'text', 'txt', name='hexdraw')
def load_hexdraw(instream, where=None, ink:str='#', paper:str='-'):
    """
    Load font from a hexdraw file.

    ink: character used for inked/foreground pixels (default #)
    paper: character used for uninked/background pixels (default -)
    """
    return _load_draw(instream.text, _ink=ink, _paper=paper)

@savers.register(linked=load_hexdraw)
def save_hexdraw(fonts, outstream, where=None, ink:str='#', paper:str='-'):
    """
    Save font to a hexdraw file.

    ink: character to use for inked/foreground pixels (default #)
    paper: character to use for uninked/background pixels (default -)
    """
    if len(fonts) > 1:
        raise FileFormatError("Can only save one font to hexdraw file.")
    DrawWriter(ink=ink, paper=paper).save(fonts[0], outstream.text)


##############################################################################
# format parameters


class DrawParams:
    """Parameters for .draw format."""

    # first/second pass constants
    separator = ':'
    comment = '%'
    # output only
    tab = '\t'
    separator_space = ''
    # tuple of individual chars, need to be separate for startswith
    whitespace = tuple(' \t')

    # third-pass constants
    ink = '#'
    paper = '-'
    empty = '-'

    @staticmethod
    def convert_key(key):
        """Convert keys on input from .draw."""
        try:
            return chr(int(key, 16))
        except (TypeError, ValueError):
            return Tag(key)


##############################################################################
##############################################################################
# read file

def _load_draw(text_stream, _ink='', _paper=''):
    """Parse a hexdraw file."""

    class _Converter(DrawConverter):
        ink=_ink or DrawConverter.ink
        paper=_paper or DrawConverter.paper

    reader = DrawReader()
    for line in text_stream:
        reader.step(line)
    return _Converter.get_font_from(reader)



class DrawReader(DrawParams, TextReader):
    """Reader for .draw files."""

class DrawConverter(DrawParams, TextConverter):
    """Converter for .draw files."""


##############################################################################
##############################################################################
# write file

class DrawWriter(TextWriter, DrawParams):

    def __init__(self, ink='', paper=''):
        self.ink = ink or self.ink
        self.paper = paper or self.paper

    def save(self, font, outstream):
        """Write one font to a plaintext stream as hexdraw."""
        # ensure char labels are set
        font = font.label(char_from=font.encoding)
        # write global comment
        if font.get_comment():
            outstream.write(self._format_comment(font.get_comment()) + '\n\n')
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
                #FIXME- draw does not support glyph properties
                self._write_glyph(outstream, glyph, label=f'{ord(glyph.char):04x}')
