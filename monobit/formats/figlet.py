"""
monobit.formats.figlet - FIGlet .flf format

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from typing import NamedTuple

from ..storage import loaders, savers
from ..magic import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..properties import Props, reverse_dict, extend_string
from ..taggers import tagmaps


# note that we won't be able to use the "subcharacters" that are the defining feature of FIGlet
# as we only work with monochrome bitmaps


##############################################################################
# interface

@loaders.register(
    name='figlet',
    magic=(b'flf2a',),
    patterns=('*.flf',),
)
def load_figlet(instream, *, ink:str=''):
    """Load font from a FIGlet .flf file."""
    flf_glyphs, flf_props, comments = _read_flf(instream.text, ink=ink)
    logging.info('figlet properties:')
    for line in str(flf_props).splitlines():
        logging.info('    ' + line)
    glyphs, props = _convert_from_flf(flf_glyphs, flf_props)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    return Font(glyphs, comment=comments, **vars(props))

@savers.register(linked=load_figlet)
def save_figlet(fonts, outstream):
    """Write fonts to a FIGlet .flf file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to .flf file.')
    font, = fonts
    flf_glyphs, flf_props, comments = _convert_to_flf(font)
    logging.info('figlet properties:')
    for line in str(flf_props).splitlines():
        logging.info('    ' + line)
    _write_flf(outstream.text, flf_glyphs, flf_props, comments)


##############################################################################
# structure definitions

_CODEPOINTS = list(range(32, 127)) + [196, 214, 220, 228, 246, 252, 223]

_DIRECTIONS = {
    0: 'left-to-right',
    1: 'right-to-left'
}

_SIGNATURE = 'flf2a'

# http://www.jave.de/docs/figfont.txt
#
# >          flf2a$ 6 5 20 15 3 0 143 229    NOTE: The first five characters in
# >            |  | | | |  |  | |  |   |     the entire file must be "flf2a".
# >           /  /  | | |  |  | |  |   \
# >  Signature  /  /  | |  |  | |   \   Codetag_Count
# >    Hardblank  /  /  |  |  |  \   Full_Layout*
# >         Height  /   |  |   \  Print_Direction
# >         Baseline   /    \   Comment_Lines
# >          Max_Length      Old_Layout*

class _FLF_HEADER(NamedTuple):
    signature_hardblank: str
    height: int
    baseline: int
    max_length: int
    old_layout: int
    comment_lines: int
    print_direction: int = 0
    full_layout: int = 0
    codetag_count: int = 0



##############################################################################
# loader

def _read_flf(instream, ink=None):
    """Read font from a FIGlet .flf file."""
    props = _read_props(instream)
    comments = _read_comments(instream, props)
    glyphs, props = _read_glyphs(instream, props, ink=ink)
    return glyphs, props, comments

def _read_props(instream):
    """Read .flf property header."""
    header = _FLF_HEADER(*instream.readline().strip().split())
    if not header.signature_hardblank.startswith(_SIGNATURE):
        raise FileFormatError('Not a FIGlet .flf file: does not start with `flf2a` signature.')
    return Props(
        hardblank = header.signature_hardblank[-1],
        **header._asdict()
    )

def _read_comments(instream, props):
    """Parse comments at start."""
    return '\n'.join(
        line.rstrip()
        for _, line in zip(range(int(props.comment_lines)), instream)
    )

def _read_glyphs(instream, props, ink=''):
    """Parse glyphs."""
    # glyphs in default repertoire
    glyphs = [_read_glyph(instream, props, codepoint=_i) for _i in _CODEPOINTS]
    # code-tagged glyphs
    for line in instream:
        line = line.rstrip()
        # codepoint, unicode name label
        codepoint, _, tag = line.partition(' ')
        codepoint = int(codepoint, 0)
        if codepoint < 0:
            # codepoints below zero are used for things like "KATAMAP" which we can't parse
            content = '\n'.join(_read_glyph_lines(instream, props))
            # should preserve as unparsed content
            props[tag.strip()] = content
        else:
            glyphs.append(_read_glyph(instream, props, codepoint=codepoint, tag=tag, ink=ink))
    return glyphs, props


def _read_glyph_lines(instream, props):
    """Read the lines in the file for a single figlet glyph."""
    return [_line.rstrip() for _, _line, in zip(range(int(props.height)), instream)]


def _read_glyph(instream, props, codepoint, tag='', ink=''):
    """Read a single figlet glyph."""
    glyph_lines = _read_glyph_lines(instream, props)
    # > In most FIGfonts, the endmark character is either "@" or "#".  The FIGdriver
    # > will eliminate the last block of consecutive equal characters from each line
    # > of sub-characters when the font is read in.  By convention, the last line of
    # > a FIGcharacter has two endmarks, while all the rest have one. This makes it
    # > easy to see where FIGcharacters begin and end.  No line should have more
    # > than two endmarks.
    glyph_lines = (
        (_line.rstrip(_line[-1]) if _line else '')
        for _line in glyph_lines
    )
    # apply hardblanks
    glyph_lines = tuple(_line.replace(props.hardblank, ' ') for _line in glyph_lines)
    # check number of characters excluding spaces
    charset = set(''.join(glyph_lines)) - set(' ')
    # if multiple characters per glyph found, ink characters must be specified explicitly
    if len(charset) > 1:
        if not ink:
            raise FileFormatError(
                'Multiple ink characters not supported: '
                f'encountered {list(charset)}.'
            )
    elif charset:
        ink = charset.pop()
        for c in charset:
            if c != ink:
                glyph_lines = (_line.replace(c, ' ') for _line in glyph_lines)
        glyph_lines = tuple(glyph_lines)
    elif not ink:
        # glyph only has ' '
        # anything but ' ' goes here
        ink = '#'
    char = chr(codepoint)
    glyph = Glyph(
        glyph_lines, _0=' ', _1=ink,
        char=char, tag=tag
    )
    return glyph

def _convert_from_flf(glyphs, props):
    """Convert figlet glyphs and properties to monobit."""
    properties = Props(
        shift_up=-int(props.height)+int(props.baseline),
        direction=_DIRECTIONS[int(props.print_direction)],
        encoding='unicode',
    )
    # > If a FIGcharacter with code 0 is present, it is treated
    # > specially.  It is a FIGfont's "missing character".
    if any(_g.char == '\0' for _g in glyphs):
        properties.default_char = '\0'
    # keep uninterpreted parameters in namespace
    properties.figlet = ' '.join(
        f'{_k}={_v}' for _k, _v in vars(props).items() if _k not in (
            'baseline', 'print_direction',
            'hardblank', 'signature_hardblank', 'height', 'max_length',
            'comment_lines', 'codetag_count'
        )
    )
    return glyphs, properties


##############################################################################
# saver

def _convert_to_flf(font, hardblank='$'):
    """Convert monobit glyphs and properties to figlet."""
    # ensure we have unicode labels where possible
    font = font.label()
    # count glyphs outside the default set
    # we can only encode glyphs that have chars
    # latin-1 codepoints, so we can just use chr()
    flf_chars = tuple(chr(_cp) for _cp in _CODEPOINTS)
    # exclude NULL which is used for the default char
    coded_chars = set(font.get_chars()) - set(flf_chars) - set('\0')
    if not font.get_chars():
        raise FileFormatError('No figlet-storable codepoints in font.')
    # construct flf properties
    props = Props(
        signature_hardblank=_SIGNATURE + hardblank,
        height=font.line_height,
        baseline=font.ascent,
        # > The Max_Length parameter is the maximum length of any line describing a
        # > FIGcharacter.  This is usually the width of the widest FIGcharacter, plus 2
        # > (to accommodate endmarks as described later.)
        max_length=2 + max(_g.advance_width for _g in font.glyphs),
        # get length of global comment
        comment_lines=len(font.get_comment().splitlines()),
        # > The Print_Direction parameter tells which direction the font is to be
        # > printed by default.  A value of 0 means left-to-right, and 1 means
        # > right-to-left.  If this parameter is absent, 0 (left-to-right) is assumed.
        print_direction=reverse_dict(_DIRECTIONS).get(font.direction, 0),
        codetag_count = len(coded_chars)
    )
    # keep namespace properties
    if 'figlet' in font.get_properties():
        propsplit = (item.partition('=') for item in font.figlet.split())
        figprops = {_k: _v for _k, _, _v in propsplit}
    else:
        figprops = {}
    props.old_layout = figprops.get('old_layout', 0)
    props.full_layout = figprops.get('full_layout', 0)
    # first get glyphs in default repertoire
    # fill missing glyphs with empties
    glyphs = [font.get_glyph(_chr, missing='empty') for _chr in flf_chars]
    # code-tagged glyphs
    glyphs.extend(font.get_glyph(_chr) for _chr in sorted(coded_chars))
    # map default glyph to codepoint zero
    # > If a FIGcharacter with code 0 is present, it is treated
    # > specially.  It is a FIGfont's "missing character".  Whenever
    # > the FIGdriver is told to print a character which doesn't exist
    # > in the current FIGfont, it will print FIGcharacter 0.  If there
    # > is no FIGcharacter 0, nothing will be printed.
    glyphs.append(font.get_default_glyph().modify(char='\0'))
    font = font.modify(glyphs)
    # expand glyphs by bearings
    font = font.equalise_horizontal()
    return font.glyphs, props, font.get_comment()

def _write_flf(
        outstream, flf_glyphs, flf_props, comments,
        ink='#', paper=' ', hardblank='$'
    ):
    """Write out a figlet font file."""
    # header
    header = _FLF_HEADER(**vars(flf_props))
    outstream.write(' '.join(str(_elem) for _elem in header) + '\n')
    # global comment
    if comments:
        outstream.write(comments + '\n')
    # use hardblank for space char (first char)
    outstream.write(_format_glyph(flf_glyphs[0], ink=ink, paper=hardblank))
    for glyph in flf_glyphs[1:len(_CODEPOINTS)]:
        outstream.write(_format_glyph(glyph, ink=ink, paper=paper))
    for glyph in flf_glyphs[len(_CODEPOINTS):]:
        tag = glyph.tags[0] if glyph.tags else tagmaps['name'].tag(*glyph.get_labels()).value
        if glyph.char > chr(255):
            outstream.write(f'{ord(glyph.char):#04x} {tag}\n')
        else:
            outstream.write(f'{ord(glyph.char)} {tag}\n')
        outstream.write(_format_glyph(glyph, ink=ink, paper=paper))


def _format_glyph(glyph, ink='#', paper=' ', end='@'):
    lines = [
        f'{_line}{end}'
        for _line in glyph.as_text(ink=ink, paper=paper).splitlines()
    ]
    if lines:
        lines[-1] += end + '\n'
    return '\n'.join(lines)
