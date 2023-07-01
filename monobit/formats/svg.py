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
from ..magic import FileFormatError
from ..vector import StrokePath
from ..font import Font
from ..glyph import Glyph
from ..properties import Props, reverse_dict
from .windows import WEIGHT_MAP, WEIGHT_REVERSE_MAP


_STYLE_MAP = {
    'normal': 'roman',
    'italic': 'italic',
    'oblique': 'oblique'
}
_STYLE_REVERSE_MAP = reverse_dict(_STYLE_MAP)

DEFAULT_NAME = 'missing'


@loaders.register(
    name='svg',
    patterns=('*.svg',),
    magic=(
        b'<svg>',
        b'<?xml version="1.0" standalone="yes"?>\n<svg'
    ),
)
def load_svg(instream):
    """Load vector font from Scalable Vector Graphics font."""
    root = etree.parse(instream).getroot()
    if not root.tag.endswith('svg'):
        raise FileFormatError(f'Not an SVG file: root tag is {root.tag}')
    # the <font> may optionally be enclosed in a <defs> block
    font = root.find('.//{*}font')
    if not font:
        raise FileFormatError('Not an SVG font file')
    props = Props(
        font_id=font.attrib.get('id'),
    )
    font_face = font.find('{*}font-face')
    if font_face is not None:
        weight = max(100, min(900, int(font_face.attrib.get('font-weight', 400))))
        props |= Props(
            ascent=int(font_face.attrib.get('ascent')),
            descent=-int(font_face.attrib.get('descent')),
            family=font_face.attrib.get('font-family'),
            line_height=int(font_face.attrib.get('font-size', font_face.attrib.get('units-per-em'))),
            underline_thickness=int(font_face.attrib.get('underline-thickness')),
            underline_descent=-int(font_face.attrib.get('underline-position')),
            weight=WEIGHT_MAP[round(weight, -2)],
            slant=_STYLE_MAP.get(font_face.attrib.get('font-style')),
        )
    glyph_elems = list(font.iterfind('{*}glyph'))
    missing_glyph = font.find('{*}missing-glyph')
    if missing_glyph is not None:
        glyph_elems.append(missing_glyph)
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
    glyph_props = tuple(
        dict(
            char=_g.attrib.get('unicode', ''),
            advance_width=int(_g.attrib.get('horiz-adv-x', 0)),
            tag=_g.attrib.get('glyph-name', '')
        )
        for _g in glyph_elems
    )
    if missing_glyph is not None:
        glyph_props[-1].update(tag=DEFAULT_NAME)
        props |= Props(default_char=DEFAULT_NAME)
    glyphs = tuple(
        Glyph.from_path(
            _path.shift(0, -props.line_height + props.descent).flip(),
            **_gprop
        )
        for _path, _gprop in zip(paths, glyph_props)
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
        for item in pathit:
            if not item:
                continue
            # if it's a number group, the last character must be a digit
            # a number group here mean's we're repeating the last svg path command
            if item[-1].isdigit():
                ds = int(item)
            else:
                svgcommand = item
                ds = None
            if svgcommand in ('m', 'l', 'M', 'L'):
                dx = ds if ds is not None else int(next(pathit))
                dy = int(next(pathit))
                if svgcommand in ('M', 'L'):
                    dx -= x
                    dy -= y
                if svgcommand in ('m', 'M'):
                    command = StrokePath.MOVE
                else:
                    command = StrokePath.LINE
            elif svgcommand in ('h', 'v', 'H', 'V'):
                command = StrokePath.LINE
                if ds is None:
                    ds = int(next(pathit))
                if svgcommand == 'H':
                    ds -= x
                elif svgcommand == 'V':
                    ds -= y
                if svgcommand in ('H', 'h'):
                    dx, dy = ds, 0
                elif svgcommand in ('V', 'v'):
                    dx, dy = 0, ds
            elif svgcommand in ('z', 'Z'):
                # close subpath
                # we asssume that's from the start or the latest move
                command = StrokePath.LINE
                dx, dy = startx - x, starty - y
            else:
                raise ValueError('Curves in paths are not supported.')
            path.append((command, dx, dy))
            x += dx
            y += dy
            if command == StrokePath.MOVE:
                startx, starty = x, y
    except StopIteration:
        logging.warning('Truncated SVG path')
    return StrokePath(path)


def attr_str(attr_dict, indent=0, sep='\n'):
    """Convert a dict to svg element attributes."""
    sep += ' ' * indent
    return sep + sep.join(f'{_k}="{_v}"' for _k, _v in attr_dict.items())


@savers.register(linked=load_svg)
def save_svg(fonts, outfile):
    """Export vector font to Scalable Vector Graphics font."""
    if len(fonts) > 1:
        raise FileFormatError('Can only export one font to SVG file.')
    font = fonts[0]
    # matching whitespace doesn't work as label thinks path-only glyphs are empty
    font = font.label(match_whitespace=False)
    if not any('path' in _g.get_properties() for _g in font.glyphs):
        logging.warning(
            "SVG file will have empty glyphs: no stroke path found"
        )
    outfile = outfile.text
    outfile.write('<svg>\n')
    font_attr = {
        'id': font.font_id or font.family or '0',
        # default advance
        'horiz-adv-x': ceil(font.average_width),
    }
    outfile.write(f'<font{attr_str(font_attr, indent=4)}>\n')
    font_face = {
        'font-family': font.family,
        'units-per-em': font.line_height,
        'font-size': font.line_height,
        'ascent': font.ascent,
        'descent': -font.descent,
        'cap-height': font.cap_height,
        'x-height': font.x_height,
        'underline-thickness': font.underline_thickness,
        'underline-position': -font.underline_descent,
        'font-weight': WEIGHT_REVERSE_MAP.get(font.weight, 400),
        'font-style': _STYLE_REVERSE_MAP.get(font.slant, 'normal'),
    }
    outfile.write(f'  <font-face{attr_str(font_face, indent=6)}/>\n')
    if font.default_char:
        _write_glyph(outfile, font, font.get_default_glyph(), tag='missing-glyph')
    for i, glyph in enumerate(font.glyphs):
        if font.default_char in glyph.tags and len(glyph.get_labels()) == 1:
            # this is *only* the default char, we keep it as missing-glyph
            logging.debug('Skipping default-only glyph `%s`', font.default_char)
            continue
        _write_glyph(outfile, font, glyph)
    outfile.write('</font>\n')
    outfile.write('</svg>\n')


def _write_glyph(outfile, font, glyph, tag='glyph'):
    """Write out a glyph to SVG."""
    if glyph.path:
        path = glyph.path.flip().shift(0, font.line_height-font.descent)
        svgpath = path.as_svg()
        d = f'\n      d="{svgpath}"'
    else:
        d = ''
    charstr = ''.join(f'&#{ord(_c)};' for _c in glyph.char)
    glyphprops = {
        'horiz-adv-x': glyph.advance_width,
    }
    if tag != 'missing-glyph':
        if charstr:
            glyphprops.update({'unicode': charstr})
        if glyph.tags:
            glyphprops.update({'glyph-name': glyph.tags[0]})
    outfile.write(f'  <{tag}{attr_str(glyphprops, indent=0, sep=" ")}>\n')
    outfile.write(f'    <path{d}\n      fill="none" stroke="currentColor" stroke-width="1"/>\n')
    outfile.write(f'  </{tag}>\n')
    # this is shorter but not recognised as single-stroke font by FontForge
    #outfile.write(f'  <{tag}{unicode} horiz-adv-x="{glyph.advance_width}"{d}/>\n')
