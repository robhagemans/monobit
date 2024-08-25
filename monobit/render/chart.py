"""
monobit.render.chart - create font chart

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from itertools import product
from pathlib import Path

from ..base.binary import ceildiv
from ..base import Props, Coord
from ..core import Codepoint, Glyph
from ..storage import savers
from ..plumbing import scriptable
from monobit.storage.utils.limitations import ensure_single
from .glyphmap import GlyphMap


@savers.register(name='chart')
def save_chart(
        fonts, outstream, *,
        glyphs_per_line:int=16,
        margin:Coord=(0, 0),
        padding:Coord=(1, 1),
        scale:Coord=Coord(1, 1),
        direction:str=None,
        border:str=' ',
        inklevels:tuple[str]=(' ', '@'),
        codepoint_range:tuple[Codepoint]=None,
    ):
    """
    Export font to text- or image-based chart.

    glyphs_per_line: number of glyphs per line in glyph chart (default: 16)
    margin: number of pixels in X,Y direction around glyph chart (default: 0x0)
    padding: number of pixels in X,Y direction between glyphs (default: 1x1)
    scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
    direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
    border: character to use for border pixels (default: space)
    inklevels: characters to use for pixels (default: space, '2')
    codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepoints)
    """
    glyph_map = create_chart(
        fonts,
        glyphs_per_line=glyphs_per_line,
        margin=margin,
        padding=padding,
        scale=scale,
        direction=direction,
        codepoint_range=codepoint_range,
    )
    outstream.text.write(
        glyph_map.as_text(border=border, inklevels=inklevels)
    )


@savers.register(name='blocks')
def save_blocks(
        fonts, outstream, *,
        glyphs_per_line:int=16,
        margin:Coord=(0, 0),
        padding:Coord=(1, 1),
        scale:Coord=Coord(1, 1),
        direction:str=None,
        resolution:Coord=Coord(1, 1),
        codepoint_range:tuple[Codepoint]=None,
    ):
    """
    Export font to text- or image-based chart.

    glyphs_per_line: number of glyphs per line in glyph chart (default: 16)
    margin: number of pixels in X,Y direction around glyph chart (default: 0x0)
    padding: number of pixels in X,Y direction between glyphs (default: 1x1)
    scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
    direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
    resolution: blocks per text character; 1x1 (default), 1x2, 1x3, 1x4, 2x1, 2x3, 2x4
    codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepoints)
    """
    glyph_map = create_chart(
        fonts,
        glyphs_per_line=glyphs_per_line,
        margin=margin,
        padding=padding,
        scale=scale,
        direction=direction,
        codepoint_range=codepoint_range,
    )
    outstream.text.write(glyph_map.as_blocks(resolution=resolution))


def create_chart(
        fonts, *,
        glyphs_per_line,
        margin,
        padding,
        scale,
        direction,
        codepoint_range,
        lines_per_page=None,
    ):
    """Create chart glyph map of font."""
    font = ensure_single(fonts)
    font = prepare_for_grid_map(font, glyphs_per_line, codepoint_range)
    font = font.stretch(*scale)
    return grid_map(
        font,
        glyphs_per_line=glyphs_per_line,
        lines_per_page=lines_per_page,
        margin=margin, padding=padding,
        direction=direction,
    )


def prepare_for_grid_map(font, glyphs_per_line, codepoint_range):
    """Resample and equalise font for grid representation."""
    font = font.equalise_horizontal()
    if not codepoint_range:
        try:
            codepoint_range = range(
                # start at a codepoint that is a multiple of the number of columns
                glyphs_per_line * (int(min(font.get_codepoints())) // glyphs_per_line),
                int(max(font.get_codepoints()))+1
            )
        except ValueError:
            # empty sequence
            raise ValueError('No codepoint labels found.')
    font = font.resample(codepoint_range, missing='empty', relabel=False)
    return font


def grid_map(
        font, *,
        # glyphs_per_line chooses rows/cols depending on render direction
        # set to None or 0 to mean 'as many as needed'
        glyphs_per_line=None,
        lines_per_page=None,
        margin=(0, 0), padding=(0, 0),
        direction=None,
        invert_y=False,
    ):
    """
    Create glyph grid(s) for font charts.
    """
    padding = Coord(*padding)
    margin = Coord(*margin)
    # work out image geometry
    step_x = font.raster_size.x + padding.x
    step_y = font.raster_size.y + padding.y
    direction = direction or font.direction
    if direction[:1].lower() in ('t', 'b'):
        rows, columns = glyphs_per_line, lines_per_page
    else:
        columns, rows = glyphs_per_line, lines_per_page
    # at most one of these may be None or 0
    rows = rows or ceildiv(len(font.glyphs), columns)
    columns = columns or ceildiv(len(font.glyphs), rows)
    glyphs_per_page = rows * columns
    glyph_pages = tuple(
        font.glyphs[_s : _s + glyphs_per_page]
        for _s in range(0, len(font.glyphs), glyphs_per_page)
    )
    # horizontal alignment (left or right)
    # note that prepare_for_grid_map has equalised glyphs to the same height
    # so vertical alignment is not needed
    dir_0, _, dir_1 = direction.partition(' ')
    right_align = dir_0[:1] == 'r' or dir_1[:1] == 'r'
    # output glyph maps
    glyph_map = GlyphMap(
        Props(
            glyph=_glyph, sheet=_sheet,
            x=(
                margin.x + col*step_x
                + (font.raster_size.x - _glyph.width if right_align else 0)
            ),
            y=margin.y + row*step_y,
        )
        for _sheet, _glyph_page in enumerate(glyph_pages)
        for _glyph, (row, col) in zip(
            _glyph_page,
            grid_traverser(columns, rows, direction, invert_y)
        )
    )
    # use blank glyphs for grid bounds
    glyph_map.append_glyph(Glyph(), 0, 0, sheet=0)
    glyph_map.append_glyph(
        Glyph(),
        2 * margin.x + columns*step_x - padding.x,
        2 * margin.y + rows*step_y - padding.y,
        sheet=0
    )
    return glyph_map


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
