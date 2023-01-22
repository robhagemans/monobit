"""
monobit.formats.svg - svg writer for vector fonts

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from math import ceil
import xml.etree.ElementTree as etree

from ..storage import loaders, savers
from ..streams import FileFormatError
from ..vector import StrokePath
from ..font import Font


_HEADER = """\
<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
<defs>
"""

_FOOTER = """\
</defs>
</svg>
"""


@loaders.register('svg', name='svg')
def load_svg(instream, where=None):
    """Load vector font from Scalable Vector Graphics font."""
    root = etree.parse(instream).getroot()
    if not root.tag.endswith('svg'):
        raise FileFormatError(f'Not an SVG file: root tag is {root.tag}')
    # the <font> may optionally be enclosed in a <defs> block
    root = root.find('{*}defs') or root
    font = root.find('{*}font')
    if not font:
        raise FileFormatError('Not an SVG font file')
    glyph_elems = tuple(font.iterfind('{*}glyph'))
    # get the element containing the path definition
    # either the <glyph> element itself or an enclosed <path>
    path_elems = tuple(
        _g if 'd' in _g.attrib else _g.find('{*}path')
        for _g in glyph_elems
    )
    paths = tuple(
        _g.attrib.get('d', '') if _g is not None else ''
        for _g in path_elems
    )
    chars = tuple(
        _g.attrib.get('unicode', '')
        for _g in glyph_elems
    )
    glyphs = tuple(
        # .shift(0, font.line_height-font.descent)
        StrokePath.from_string(_path).flip().as_glyph(char=_char)
        for _path, _char in zip(paths, chars)
    )
    return Font(glyphs)


@savers.register(linked=load_svg)
def save_svg(fonts, outfile, where=None):
    """Export vector font to Scalable Vector Graphics font."""
    if len(fonts) > 1:
        raise FileFormatError('Can only export one font to SVG file.')
    font = fonts[0]
    # matching whitespace doesn't work as label thinks path-only glyphs are empty
    font = font.label(match_whitespace=False)
    if not any('path' in _g.properties for _g in font.glyphs):
        logging.warning(
            "SVG file will have empty glyphs: no stroke path found"
        )
    outfile = outfile.text
    outfile.write(_HEADER)
    outfile.write(f'<font id="{font.family}" horiz-adv-x="{ceil(font.average_width)}">\n')
    outfile.write(f'<font-face font-family="{font.family}" units-per-em="{font.line_height}" />\n')
    for i, glyph in enumerate(font.glyphs):
        if glyph.path:
            svgpath = StrokePath.from_string(glyph.path).flip().shift(0, font.line_height-font.descent).as_svg()
            d = f' d="{svgpath}"'
        else:
            d = ''
        charstr = ''.join(f'&#{ord(_c)};' for _c in glyph.char)
        if charstr:
            unicode = f' unicode="{charstr}"'
        else:
            unicode = ''
        outfile.write(f'  <glyph{unicode} horiz-adv-x="{glyph.advance_width}">')
        outfile.write(f'<path{d} fill="none" stroke="currentColor" stroke-width="1"/>')
        outfile.write(f'</glyph>\n')
        # this is shorter but not recognised as single-stroke font by FontForge
        #outfile.write(f'  <glyph{unicode} horiz-adv-x="{glyph.advance_width}"{d}/>\n')
    outfile.write('</font>\n')
    outfile.write(_FOOTER)
