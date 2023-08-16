"""
monobit.render.chart - create font chart

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from itertools import product

from ..base.binary import ceildiv
from ..base import Props, Coord
from ..core import Codepoint
from ..storage import savers
from ..plumbing import scriptable
from .glyphmap import GlyphMap


@savers.register(name='chart', wrapper=True)
def save_chart(
        fonts, outstream,
        columns:int=32, margin:Coord=(0, 0), padding:Coord=(0, 0),
        order:str='row-major', direction:Coord=(1, -1),
        codepoint_range:tuple[Codepoint]=None, style:str='text',
        **kwargs
    ):
    output = (
        chart(
            font, columns, margin, padding, order, direction, codepoint_range,
        )
        for font in fonts
    )
    if style == 'text':
        outstream.text.write(
            '\n\n'.join(_gm.as_text(**kwargs) for _gm in output)
        )
    elif style == 'blocks':
        outstream.text.write(
            '\n\n'.join(_gm.as_blocks(**kwargs) for _gm in output)
        )
    else:
        raise ValueError(f"`style` must be one of 'text', 'blocks'; not {style!r}")




def chart(
        font,
        columns=32, margin=(0, 0), padding=(0, 0),
        order='row-major', direction=(1, -1),
        codepoint_range=None,
    ):
    """Create font chart matrix."""
    font = font.equalise_horizontal()
    if not codepoint_range:
        try:
            codepoint_range = range(
                # start at a codepoint that is a multiple of the number of columns
                columns * (int(min(font.get_codepoints())) // columns),
                int(max(font.get_codepoints()))+1
            )
        except ValueError:
            # empty sequence
            raise ValueError('No codepoint labels found.')
    font = font.resample(codepoint_range, missing='empty', relabel=False)
    glyph_map = grid_map(font, columns, margin, padding, order, direction)
    return glyph_map


def grid_map(
        font,
        columns=32, margin=(0, 0), padding=(0, 0),
        order='row-major', direction=(1, -1),
    ):
    """Create glyph map for font chart matrix."""
    padding = Coord(*padding)
    margin = Coord(*margin)
    # work out image geometry
    step_x = font.raster_size.x + padding.x
    step_y = font.raster_size.y + padding.y
    rows = ceildiv(len(font.glyphs), columns)
    # output glyph map
    traverse = grid_traverser(columns, rows, order, direction)
    glyph_map = GlyphMap(
        Props(
            glyph=_glyph, sheet=0,
            x=margin.x + col*step_x, y=margin.y + row*step_y,
        )
        for _glyph, (row, col) in zip(font.glyphs, traverse)
    )
    # determine image geometry
    width = columns * step_x + 2 * margin.x - padding.x
    height = rows * step_y + 2 * margin.y - padding.y
    return glyph_map


def grid_traverser(columns, rows, order, direction):
    """Traverse a glyph chart in the specified order and directions."""
    dir_x, dir_y = direction
    if not dir_x or not dir_y:
        raise ValueError('direction values must not be 0.')
    if dir_x > 0:
        x_traverse = range(columns)
    else:
        x_traverse = range(columns-1, -1, -1)
    if dir_y > 0:
        y_traverse = range(rows)
    else:
        y_traverse = range(rows-1, -1, -1)
    if order.startswith('r'):
        return product(y_traverse, x_traverse)
    elif order.startswith('c'):
        return product(x_traverse, y_traverse)
    raise ValueError(f'order should start with one of `r`, `c`, not `{order}`.')
