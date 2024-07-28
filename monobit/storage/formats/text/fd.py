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
from ..common import (
    WEIGHT_MAP, CHARSET_MAP, WEIGHT_REVERSE_MAP, CHARSET_REVERSE_MAP
)
from .draw import DrawComment, NonEmptyBlock, Empty, Unparsed, iter_blocks
from monobit.storage.utils.limitations import ensure_single


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
    text=True,
)
def load_mkwinfont(instream):
    """Load font from a mkwinfont .fd file."""
    properties, glyphs, comments = _read_mkwinfont(instream.text)
    return _convert_mkwinfont(properties, glyphs, comments)


@savers.register(linked=load_mkwinfont)
def save_mkwinfont(fonts, outstream):
    font = ensure_single(fonts)
    return _write_mkwinfont(font, outstream)



###############################################################################
# reader

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
        # .fd doesn't store internal/external leading, so it gets included in descent
        descent=int(props.height)-int(props.ascent),
        ascent=props.ascent,
        point_size=props.pointsize,
        slant='italic' if props.italic else '',
        decoration=''.join((
            ('strikethrough ' if props.strikeout else ''),
            ('underline ' if props.underline else ''),
        )).strip(),
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
    glyphs = (_g.modify(shift_up=-mb_props['descent']) for _g in glyphs)
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
        return dict(_l.partition(' ')[::2] for _l in self.lines)


class MWFComment(DrawComment):
    pass


###############################################################################
# writer

def _write_mkwinfont(font, outstream):
    outstream = outstream.text
    font = font.equalise_horizontal()
    props = _convert_to_mkwinfont_props(font)

    def _write_prop(key):
        if props[key] is not None and props[key] != '':
            outstream.write(f'{key} {props[key]}\n')

    if font.get_comment():
        outstream.write('# ' + '\n# '.join(font.get_comment().splitlines()) + '\n\n')
    _write_prop('facename')
    _write_prop('copyright')
    outstream.write('\n')
    _write_prop('height')
    _write_prop('ascent')
    if props['height'] != props['pointsize']:
        _write_prop('pointsize')
    if props['italic']:
        _write_prop('italic')
    if props['underline']:
        _write_prop('underline')
    if props['strikeout']:
        _write_prop('strikeout')
    if props['weight'] != 400:
        _write_prop('weight')
    outstream.write('\n')
    _write_prop('charset')
    outstream.write('\n')
    for codepoint in range(256):
        try:
            glyph = font.get_glyph(codepoint)
        except KeyError:
            pass
        else:
            outstream.write(f'char {codepoint}\n')
            outstream.write(f'width {glyph.advance_width}\n')
            outstream.write(glyph.as_text(paper='0', ink='1'))
            outstream.write('\n')



def _convert_to_mkwinfont_props(font):
    return dict(
        facename=font.name,
        copyright=font.copyright,
        # .fd doesn't store internal/external leading, so we include everything
        height=font.line_height,
        ascent=font.ascent,
        pointsize=font.point_size,
        italic=font.slant == 'italic',
        strikeout='strikethrough' in font.decoration,
        underline='underline' in font.decoration,
        weight=WEIGHT_REVERSE_MAP.get(font.weight, None),
        charset=CHARSET_REVERSE_MAP.get(font.encoding, None),
    )
