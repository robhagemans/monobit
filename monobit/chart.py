"""
monobit.chart - create font chart

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from itertools import product

from .canvas import Canvas
from .binary import ceildiv
from .properties import Props
from .basetypes import Coord


def chart(
        font,
        columns=32, margin=(0, 0), padding=(0, 0),
        order='row-major', direction=(1, -1),
    ):
    """Create font chart matrix."""
    glyph_map, _, _ = grid_map(
        font, columns, margin, padding, order, direction,
    )
    canvas = Canvas.from_glyph_map(glyph_map)
    return canvas


def grid_map(
        font,
        columns=32, margin=(0, 0), padding=(0, 0),
        order='row-major', direction=(1, -1),
    ):
    """Create glyph map for font chart matrix."""
    font = font.equalise_horizontal()
    padding = Coord(*padding)
    margin = Coord(*margin)
    # work out image geometry
    step_x = font.raster_size.x + padding.x
    step_y = font.raster_size.y + padding.y
    rows = ceildiv(len(font.glyphs), columns)
    # output glyph map
    traverse = grid_traverser(columns, rows, order, direction)
    glyph_map = tuple(
        Props(
            glyph=_glyph, sheet=0,
            x=margin.x + col*step_x, y=margin.y + row*step_y,
        )
        for _glyph, (row, col) in zip(font.glyphs, traverse)
    )
    # determine image geometry
    width = columns * step_x + 2 * margin.x - padding.x
    height = rows * step_y + 2 * margin.y - padding.y
    return glyph_map, width, height


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
