"""
monobit.chart - create font chart

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .renderer import Canvas
from .binary import ceildiv


def chart(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        order='row-major', direction=(1, -1),
    ):
    """Create font chart matrix."""
    scale_x, scale_y = scale
    padding_x, padding_y = padding
    margin_x, margin_y = margin
    # work out image geometry
    step_x = font.raster_size.x * scale_x + padding_x
    step_y = font.raster_size.y * scale_y + padding_y
    rows = ceildiv(len(font.glyphs), columns)
    # determine image geometry
    width = columns * step_x + 2 * margin_x - padding_x
    height = rows * step_y + 2 * margin_y - padding_y
    canvas = Canvas.blank(width, height)
    # output glyphs
    traverse = traverse_chart(columns, rows, order, direction)
    for glyph, pos in zip(font.glyphs, traverse):
        if not glyph.width or not glyph.height:
            continue
        row, col = pos
        left = margin_x + col*step_x + glyph.left_bearing
        top = margin_y + row*step_y
        mx = glyph.stretch(scale_x, scale_y)
        canvas.blit(mx, left, top, operator=max)
    return canvas


def traverse_chart(columns, rows, order, direction):
    """Traverse a glyph chart in the specified order and directions."""
    dir_x, dir_y = direction
    x_traverse = range(columns)
    if dir_x < 0:
        x_traverse = reversed(x_traverse)
    y_traverse = range(rows)
    if dir_y < 0:
        y_traverse = reversed(y_traverse)
    if order.startswith('r'):
        # row-major left-to-right top-to-bottom
        x_traverse = list(x_traverse)
        return (
            (_row, _col)
            for _row in y_traverse
            for _col in x_traverse
        )
    elif order.startswith('c'):
        # row-major top-to-bottom left-to-right
        y_traverse = list(y_traverse)
        return (
            (_row, _col)
            for _col in x_traverse
            for _row in y_traverse
        )
    else:
        raise ValueError(
            f'order should start with one of `r`, `c`, not `{order}`.'
        )
