"""
monobit.storage.formats.text.psf2txt - PSF2TXT format

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string

from monobit.storage.base import loaders, savers
from monobit.storage import FileFormatError
from monobit.core import Font, Glyph, Char
from monobit.base import Props

from .draw import NonEmptyBlock, Empty, iter_blocks, equal_firsts
from monobit.storage.utils.limitations import ensure_single, ensure_charcell


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

PSFT_SIG = '%PSF2'


@loaders.register(
    name='psf2txt',
    magic=(PSFT_SIG.encode('ascii'),),
    patterns=('*.txt',),
    text=True,
)
def load_psf2txt(instream):
    """Load font from a psf2txt .txt file."""
    properties, glyphs, comments = _read_psf2txt(instream.text)
    return _convert_psf2txt(properties, glyphs, comments)

@savers.register(linked=load_psf2txt)
def save_psf2txt(fonts, outstream):
    """Save font to a psf2txt .txt file."""
    font = ensure_single(fonts)
    _write_psf2txt(font, outstream)


###############################################################################
# writer

def _write_psf2txt(font, outstream):
    font = ensure_charcell(font)
    font = font.label()
    outstream = outstream.text
    outstream.write(PSFT_SIG)
    outstream.write(f'\nVersion: {font.revision or 0}\n')
    # flag 1 means has-unicode-table
    outstream.write('Flags: 1\n')
    outstream.write(f'Length: {len(font.glyphs)}\n')
    outstream.write(f'Width: {font.cell_size.x}\n')
    outstream.write(f'Height: {font.cell_size.y}\n')
    for i, glyph in enumerate(font.glyphs):
        outstream.write(f'%\n// Character {i}\n')
        outstream.write('Bitmap: ')
        outstream.write(
            glyph.as_text(start='', end=' \\\n        ', paper='-', ink='#')
            .rstrip(' \\\n        ')
        )
        outstream.write('\n')
        if glyph.char:
            outstream.write('Unicode: ')
            for elem in glyph.char:
                outstream.write(f'[{ord(elem):08x}];')
            outstream.write('\n')


###############################################################################
# reader

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
