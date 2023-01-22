"""
monobit.formats.svg - svg writer for vector fonts

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import re
import logging
from math import ceil
import xml.etree.ElementTree as etree

from ..storage import loaders, savers
from ..streams import FileFormatError
from ..vector import StrokePath
from ..font import Font
from ..properties import Props


@loaders.register('svg', name='svg')
def load_svg(instream, where=None):
    """Load vector font from Scalable Vector Graphics font."""
    root = etree.parse(instream).getroot()
    if not root.tag.endswith('svg'):
        raise FileFormatError(f'Not an SVG file: root tag is {root.tag}')
    # the <font> may optionally be enclosed in a <defs> block
    font = root.find('.//{*}font')
    if not font:
        raise FileFormatError('Not an SVG font file')
    props = {}
    font_face = font.find('{*}font-face')
    if font_face is not None:
        props = Props(
            ascent=int(font_face.attrib.get('ascent')),
            descent=-int(font_face.attrib.get('descent')),
            family=font_face.attrib.get('font-family'),
            ##
            line_height=int(font_face.attrib.get('units-per-em')),
        )
    glyph_elems = tuple(font.iterfind('{*}glyph'))
    # get the first element containing a path definition
    # either the <glyph> element itself or an enclosed <path>
    # or that path enclosed in <g>s etc
    path_elems = (
        _g.find('.//*[@d]')
        for _g in glyph_elems
    )
    orig_paths = tuple(
        _g.attrib.get('d', '') if _g is not None else ''
        for _g in path_elems
    )
    # convert path to monobit notation
    paths = tuple(convert_path(_p) for _p in orig_paths)
    chars = tuple(
        _g.attrib.get('unicode', '')
        for _g in glyph_elems
    )
    glyphs = tuple(
        _path.shift(0, -props.line_height + props.descent)
            .flip()
            .as_glyph(char=_char, code=_code)
        for _path, _code, _char in zip(paths, orig_paths, chars)
    )
    return Font(glyphs, **vars(props))

def convert_path(svgpath):
    """Convert SVG path to monobit path."""
    # split into individual letters and groups of digits (including minus sign)
    splitgroups = re.compile('[-0-9]+|[a-zA-Z]').findall
    pathit = iter(splitgroups(svgpath))
    x, y = 0, 0
    startx, starty = 0, 0
    path = []
    try:
        # todo: repeats
        for item in pathit:
            if item in ('m', 'l', 'M', 'L'):
                dx = int(next(pathit))
                dy = int(next(pathit))
                if item in ('M', 'L'):
                    dx -= x
                    dy -= y
                command = item.lower()
            elif item in ('h', 'v', 'H', 'V'):
                command = 'l'
                ds = int(next(pathit))
                if item == 'H':
                    ds -= x
                elif item == 'V':
                    ds -= y
                if item in ('H', 'h'):
                    dx, dy = ds, 0
                elif item in ('V', 'v'):
                    dx, dy = 0, ds
            elif item in ('z', 'Z'):
                # close subpath
                # we asssume that's from the start or the latest move
                command = 'l'
                dx, dy = startx - x, starty - y
            else:
                raise ValueError('Curves in paths are not supported.')
            path.append((command, dx, dy))
            x += dx
            y += dy
            if command == 'm':
                startx, starty = x, y
    except StopIteration:
        logging.warning('Truncated SVG path')
    return StrokePath(path)


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
    outfile.write('<svg>\n')
    outfile.write(f'<font id="{font.family}" horiz-adv-x="{ceil(font.average_width)}">\n')
    font_face = {
        'font-family': font.family,
        'units-per-em': font.line_height,
        'ascent': font.ascent,
        'descent': -font.descent,
    }
    attrib = ' '.join(f'{_k}="{_v}"' for _k, _v in font_face.items())
    outfile.write(f'  <font-face {attrib}/>\n')
    for i, glyph in enumerate(font.glyphs):
        if glyph.path:
            path = StrokePath.from_string(glyph.path).flip().shift(0, font.line_height-font.descent)
            svgpath = path.as_svg()
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
    outfile.write('</svg>\n')
