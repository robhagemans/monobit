"""
monobit.formats.svg - svg writer for vector fonts

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from math import ceil

from ..storage import savers
from ..streams import FileFormatError

_HEADER = """\
<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" >
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
<defs>
"""

_FOOTER = """\
</defs>
</svg>
"""

@savers.register('svg', name='svg')
def save_svg(
        fonts, outfile, where=None,
    ):
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
            svgpath = ' '.join(glyph.path.split('\n'))
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
