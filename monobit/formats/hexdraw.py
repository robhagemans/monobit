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

class DrawParams:
    """Parameters for hexdraw format."""
    separator = ':'
    comment = '%'
    tab = '\t'
    #ink = '#'
    #paper = '-'


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


# read hexdraw file

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


# write hexdraw file

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
        glyphtext, _0='.', _1='#', codepoint=f'0x{codepoint}'
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
    """Load font from apsftoools .txt file."""
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
        # print(repr(line))
        if not line:
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
        # print(current_glyph)
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
    mb_glyphs = tuple(
        Glyph(_rows, _0='-', _1='#', comment=_props.Unicode)
        for _rows, _props in glyphs
    )
    return Font(mb_glyphs, **mb_props)
