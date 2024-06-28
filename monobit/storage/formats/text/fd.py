"""
monobit.storage.formats.text.fd - mkwinfont .fd format

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import string

from monobit.storage.base import loaders, savers
from monobit.storage import FileFormatError
from monobit.core import Font, Glyph
from monobit.base import Props
from ..common import WEIGHT_MAP, CHARSET_MAP
from .draw import DrawComment, NonEmptyBlock, Empty, Unparsed, iter_blocks


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
    name='mkwinfont',
    patterns=('*.fd',),
)
def load_mkwinfont(instream):
    """Load font from a mkwinfont .fd file."""
    properties, glyphs, comments = _read_mkwinfont(instream.text)
    return _convert_mkwinfont(properties, glyphs, comments)


def _read_mkwinfont(text_stream):
    """Read a mkwinfont file into a properties object."""
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

def _convert_mkwinfont(props, glyphs, comments):
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
