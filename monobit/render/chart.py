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
from monobit.storage.utils.limitations import ensure_single
from .glyphmap import GlyphMap


DEFAULT_IMAGE_FORMAT = 'png'


@savers.register(name='chart')
def save_chart(
        fonts, outstream,
        columns:int=16, margin:Coord=(0, 0), padding:Coord=(0, 0),
        direction:str='left-to-right top-to-bottom',
        codepoint_range:tuple[Codepoint]=None, style:str='text',
        **kwargs
    ):
    """
    Export font to text- or image-based chart.
    """
    font = ensure_single(fonts)
    font = prepare_for_grid_map(font, columns, codepoint_range)
    output = grid_map(
        font,
        columns=columns, rows=ceildiv(len(font.glyphs), columns),
        margin=margin, padding=padding,
        direction=direction,
    )
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
        font, *,
        columns=32, rows=8,
        margin=(0, 0), padding=(0, 0),
        direction='left-to-right top-to-bottom',
        invert_y=False,
    ):
    """Create glyph map for font chart matrix."""
    padding = Coord(*padding)
    margin = Coord(*margin)
    # work out image geometry
    step_x = font.raster_size.x + padding.x
    step_y = font.raster_size.y + padding.y
    # rows = ceildiv(len(font.glyphs), columns)
    # output glyph map
    traverse = grid_traverser(columns, rows, direction, invert_y)
    return GlyphMap(
        Props(
            glyph=_glyph, sheet=0,
            x=margin.x + col*step_x, y=margin.y + row*step_y,
        )
        for _glyph, (row, col) in zip(font.glyphs, traverse)
    )


def grid_traverser(columns, rows, direction, invert_y=False):
    """
    Traverse a glyph chart in the specified order and directions.

    direction: a pair of characters of the form 'a b'
               where a, b can be 'l', 'r', 't', 'b'
    invert_y: positive is down
    """
    glyph_dir, _, line_dir = direction.lower().partition(' ')
    glyph_dir = glyph_dir[:1] or 'l'
    line_dir = line_dir[:1] or 't'
    vertical = glyph_dir in ('t', 'b')
    if vertical:
        dir_y, dir_x = glyph_dir, line_dir
    else:
        dir_x, dir_y = glyph_dir, line_dir
    if dir_x == 'l':
        x_traverse = range(columns)
    else:
        x_traverse = range(columns-1, -1, -1)
    if dir_y == 't':
        y_traverse = range(rows-1, -1, -1)
    else:
        y_traverse = range(rows)
    if invert_y:
        y_traverse = reversed(y_traverse)
    if vertical:
        return (reversed(_p) for _p in product(x_traverse, y_traverse))
    else:
        return product(y_traverse, x_traverse)
