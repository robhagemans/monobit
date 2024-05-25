"""
monobit.render.chart - create font chart

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from itertools import product
from pathlib import Path

from ..base.binary import ceildiv
from ..base import Props, Coord
from ..core import Codepoint
from ..storage import savers
from ..plumbing import scriptable
from .glyphmap import GlyphMap


@savers.register(name='chart')
def save_chart(
        fonts, outstream,
        columns:int=16, margin:Coord=(0, 0), padding:Coord=(0, 0),
        order:str='row-major', direction:Coord=(1, -1),
        codepoint_range:tuple[Codepoint]=None, style:str='text',
        **kwargs
    ):
    """
    Export font to text- or image-based chart.
    """
    font, *more_than_one = fonts
    if more_than_one:
        raise ValueError('Can only chart a single font.')
    font = prepare_for_grid_map(font, columns, codepoint_range)
    output = grid_map(font, columns, margin, padding, order, direction)
    if style == 'text':
        outstream.text.write(output.as_text(**kwargs))
    elif style == 'blocks':
        outstream.text.write(output.as_blocks(**kwargs))
    elif style == 'image':
        img = output.as_image(**kwargs)
        try:
            img.save(outstream, format=Path(outstream.name).suffix[1:])
        except (KeyError, ValueError, TypeError):
            img.save(outstream, format=DEFAULT_IMAGE_FORMAT)
    else:
        raise ValueError(
            f"`style` must be one of 'text', 'blocks', 'image's; not {style!r}"
        )


def prepare_for_grid_map(font, columns=32, codepoint_range=None):
    """Resample and equalise font for grid representation."""
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
    return font


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
