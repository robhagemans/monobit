"""
monobit.figlet - FIGlet .flf format

(c) 2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..matrix import to_text
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..struct import Props
from ..taggers import extend_string


# note that we won't be able to use the "subcharacters" that are the defining feature of FIGlet
# as we only work with monochrome bitmaps

SIGNATURE = 'flf2a'
CODEPOINTS = list(range(32, 127)) + [196, 214, 220, 228, 246, 252, 223]
ENCODING = 'latin-1'


##############################################################################
# interface


@loaders.register('flf', magic=(b'flf2a',), name='figlet')
def load_flf(instream, where=None, *, ink:str=''):
    """Load font from a FIGlet .flf file."""
    flf_glyphs, flf_props, comments = _read_flf(instream.text, ink=ink)
    for line in str(flf_props).splitlines():
        logging.info('    ' + line)
    glyphs, props = _convert_from_flf(flf_glyphs, flf_props)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    return Font(glyphs, properties=vars(props), comments=comments)

@savers.register(linked=load_flf)
def save_flf(fonts, outstream, where=None):
    """Write fonts to a FIGlet .flf file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to .flf file.')
    font, = fonts
    _save_flf(font, outstream.text)


##############################################################################
# loader

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

def _read_flf(instream, ink=None):
    """Read font from a FIGlet .flf file."""
    props = _read_props(instream)
    comments = _read_comments(instream, props)
    glyphs = _read_glyphs(instream, props, ink=ink)
    return glyphs, props, comments

def _read_props(instream):
    """Read .flf property header."""
    metrics = instream.readline().strip()
    if not metrics.startswith(SIGNATURE):
        raise FileFormatError('Not a FIGlet .flf file: does not start with `flf2a`.')
    metrics = metrics[len(SIGNATURE):]
    metrics = metrics.split()
    props = Props()
    # > The first seven parameters are required.
    # > The last three (Direction, Full_Layout, and Codetag_Count, are not.
    (
        props.hardblank,
        props.height,
        props.baseline,
        props.max_length,
        props.old_layout,
        props.comment_lines,
    ) = metrics[:6]
    metrics = metrics[6:]
    try:
        props.print_direction = metrics.pop(0)
        props.full_layout = metrics.pop(0)
        props.codetag_count = metrics.pop(0)
    except IndexError:
        pass
    return props

def _read_comments(instream, props):
    """Parse comments at start."""
    return '\n'.join(
        line.rstrip()
        for _, line in zip(range(int(props.comment_lines)), instream)
    )

def _read_glyphs(instream, props, ink=''):
    """Parse glyphs."""
    glyphs = [_read_glyph(instream, props, codepoint=_i) for _i in CODEPOINTS]
    for line in instream:
        line = line.rstrip()
        # codepoint, unicode name label
        codepoint, _, tag = line.partition(' ')
        glyphs.append(_read_glyph(instream, props, codepoint=int(codepoint, 0), tag=tag, ink=ink))
    return glyphs

def _read_glyph(instream, props, codepoint, tag='', ink=''):
    glyph_lines = [_line.rstrip() for _, _line, in zip(range(int(props.height)), instream)]
    # > In most FIGfonts, the endmark character is either "@" or "#".  The FIGdriver
    # > will eliminate the last block of consecutive equal characters from each line
    # > of sub-characters when the font is read in.  By convention, the last line of
    # > a FIGcharacter has two endmarks, while all the rest have one. This makes it
    # > easy to see where FIGcharacters begin and end.  No line should have more
    # > than two endmarks.
    glyph_lines = [_line.rstrip(_line[-1]) for _line in glyph_lines]
    # check number of characters excluding spaces
    paper = [' ', props.hardblank]
    charset = set(''.join(glyph_lines)) - set(paper)
    # if multiple characters per glyph found, ink characters must be specified explicitly
    if len(charset) > 1:
        if not ink:
            raise FileFormatError(
                'Multiple ink characters not supported: '
                f'encountered {list(charset)}.'
            )
        else:
            paper += list(charset - set(ink))
    return Glyph.from_matrix(glyph_lines, paper=paper).modify(
        codepoint=codepoint, tags=[tag]
    )

def _convert_from_flf(glyphs, props):
    """Convert figlet glyphs and properties to monobit."""
    descent = int(props.height)-int(props.baseline)
    properties = Props(
        descent=descent,
        offset=(0, -descent),
        ascent=int(props.baseline),
        direction={
            '0': 'left-to-right',
            '1': 'right-to-left'
        }[props.print_direction],
        encoding=ENCODING,
        default_char=0,
    )
    return glyphs, properties


##############################################################################
# saver
