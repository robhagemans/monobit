"""
monobit.render.chart - create font chart

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from itertools import product, chain
from pathlib import Path

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.base.binary import ceildiv
from monobit.base import Props, Coord, RGB, Any
from monobit.core import Codepoint, Glyph, Char
from monobit.plumbing import scriptable
from monobit.storage.magic import MagicRegistry
from monobit.storage.fontfiles import output_pack_or_font
from monobit.encoding.unicode import is_showable
from monobit.storage.utils.limitations import ensure_single
from .glyphmap import GlyphMap


DEFAULT_IMAGE_FORMAT = 'png'

charters = MagicRegistry(default_text='text')


@scriptable(passthrough=charters, pack_operation=True, output=True)
def chart(
        pack_or_font,
        outfile:Any='', *,
        format:str='', overwrite:bool=False,
        container_format:str='',
        **kwargs
    ):
    """
    Write font chart(s) to file.

    outfile: output file or path (default: stdout)
    format: font file format (default: infer from filename)
    container_format: container/wrapper formats separated by . (default: infer from filename)
    overwrite: if outfile is a path, allow overwriting existing file
    """
    return output_pack_or_font(
        pack_or_font, outfile,
        format=format, overwrite=overwrite,
        container_format=container_format, registry=charters,
        **kwargs
    )


@charters.register(name='text')
def chart_text(
        fonts, outstream, *,
        glyphs_per_line:int=16,
        margin:Coord=Coord(0, 0),
        padding:Coord=Coord(1, 1),
        scale:Coord=Coord(1, 1),
        direction:str=None,
        border:str='\xa0',
        inklevels:tuple[str]=('\xa0', '@'),
        codepoint_range:tuple[Codepoint]=None,
        grid_positioning:bool=True,
        skip_empty_lines:bool=True,
        max_labels:int=1,
    ):
    """
    Export font to text chart.

    glyphs_per_line: number of glyphs per line in glyph chart (default: 16)
    margin: number of pixels in X,Y direction around glyph chart (default: 0x0)
    padding: number of pixels in X,Y direction between glyphs (default: 1x1)
    scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
    direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
    border: character to use for border pixels (default: space)
    inklevels: characters to use for pixels (default: space, '2')
    codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepoints)
    grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: true)
    skip_empty_lines: if -grid-positioning is used, skip lines that have no glyphs (default: true)
    max_labels: maximum number of labels to show per glyph (default: 1)
    """
    glyph_map = create_chart(
        fonts,
        glyphs_per_line=glyphs_per_line,
        margin=margin,
        padding=padding,
        scale=scale,
        direction=direction,
        codepoint_range=codepoint_range,
        grid_positioning=grid_positioning,
        skip_empty_lines=skip_empty_lines,
        max_labels=max_labels,
    )
    outstream.text.write(
        glyph_map.as_text(border=border, inklevels=inklevels)
    )


@charters.register(name='blocks')
def chart_blocks(
        fonts, outstream, *,
        glyphs_per_line:int=16,
        margin:Coord=Coord(0, 0),
        padding:Coord=Coord(1, 1),
        scale:Coord=Coord(1, 1),
        direction:str=None,
        resolution:Coord=Coord(1, 1),
        codepoint_range:tuple[Codepoint]=None,
        grid_positioning:bool=True,
        skip_empty_lines:bool=True,
        max_labels:int=1,
    ):
    """
    Export font to blocks chart.

    glyphs_per_line: number of glyphs per line in glyph chart (default: 16)
    margin: number of pixels in X,Y direction around glyph chart (default: 0x0)
    padding: number of pixels in X,Y direction between glyphs (default: 1x1)
    scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
    direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
    resolution: blocks per text character; 1x1 (default), 1x2, 1x3, 1x4, 2x1, 2x3, 2x4
    codepoint_range: range of codepoints to include (includes bounds; default: all codepoints)
    grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: true)
    skip_empty_lines: if -grid-positioning is used, skip lines that have no glyphs (default: true)
    max_labels: maximum number of labels to show per glyph (default: 1)
    """
    glyph_map = create_chart(
        fonts,
        glyphs_per_line=glyphs_per_line,
        margin=margin,
        padding=padding,
        scale=scale,
        direction=direction,
        codepoint_range=codepoint_range,
        max_labels=max_labels,
        grid_positioning=grid_positioning,
        skip_empty_lines=skip_empty_lines,
        label_height=resolution.y,
    )
    outstream.text.write(glyph_map.as_blocks(resolution=resolution))


@charters.register(name='shades')
def chart_shades(
        fonts, outstream, *,
        glyphs_per_line:int=16,
        margin:Coord=Coord(0, 0),
        padding:Coord=Coord(1, 1),
        scale:Coord=Coord(1, 1),
        direction:str=None,
        border:RGB=None,
        paper:RGB=RGB(0, 0, 0),
        ink:RGB=RGB(255, 255, 255),
        codepoint_range:tuple[Codepoint]=None,
        grid_positioning:bool=True,
        skip_empty_lines:bool=True,
        max_labels:int=1,
    ):
    """
    Export font to ansi-coloured blocks chart.

    glyphs_per_line: number of glyphs per line in glyph chart (default: 16)
    margin: number of pixels in X,Y direction around glyph chart (default: 0x0)
    padding: number of pixels in X,Y direction between glyphs (default: 1x1)
    scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
    direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
    paper: background colour R,G,B 0--255 (default: 0,0,0)
    ink: full-intensity foreground colour R,G,B 0--255 (default: 255,255,255)
    border: border colour R,G,B 0--255 (default: terminal background)
    codepoint_range: range of codepoints to include (includes bounds; default: all codepoints)
    grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: true)
    skip_empty_lines: if -grid-positioning is used, skip lines that have no glyphs (default: true)
    max_labels: maximum number of labels to show per glyph (default: 1)
    """
    glyph_map = create_chart(
        fonts,
        glyphs_per_line=glyphs_per_line,
        margin=margin,
        padding=padding,
        scale=scale,
        direction=direction,
        codepoint_range=codepoint_range,
        max_labels=max_labels,
        grid_positioning=grid_positioning,
        skip_empty_lines=skip_empty_lines,
    )
    outstream.text.write(glyph_map.as_shades(
        paper=paper, border=border, ink=ink,
    ))



@charters.register(name='sixel')
def chart_sixel(
        fonts, outstream, *,
        glyphs_per_line:int=16,
        margin:Coord=Coord(0, 0),
        padding:Coord=Coord(1, 1),
        scale:Coord=Coord(1, 1),
        direction:str=None,
        border:RGB=None,
        paper:RGB=RGB(0, 0, 0),
        ink:RGB=RGB(255, 255, 255),
        codepoint_range:tuple[Codepoint]=None,
        grid_positioning:bool=True,
        skip_empty_lines:bool=True,
        # max_labels:int=1,
    ):
    """
    Export font to chart as sixel image.

    glyphs_per_line: number of glyphs per line in glyph chart (default: 16)
    margin: number of pixels in X,Y direction around glyph chart (default: 0x0)
    padding: number of pixels in X,Y direction between glyphs (default: 1x1)
    scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
    direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
    paper: background colour R,G,B 0--255 (default: 0,0,0)
    ink: full-intensity foreground colour R,G,B 0--255 (default: 255,255,255)
    border: border colour R,G,B 0--255 (default: terminal background)
    codepoint_range: range of codepoints to include (includes bounds; default: all codepoints)
    grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: true)
    skip_empty_lines: if -grid-positioning is used, skip lines that have no glyphs (default: true)
    """
    # max_labels: maximum number of labels to show per glyph (default: 1)
    glyph_map = create_chart(
        fonts,
        glyphs_per_line=glyphs_per_line,
        margin=margin,
        padding=padding,
        scale=scale,
        direction=direction,
        codepoint_range=codepoint_range,
        # max_labels=max_labels,
        grid_positioning=grid_positioning,
        skip_empty_lines=skip_empty_lines,
    )
    outstream.text.write(
        glyph_map.as_sixel(paper=paper, border=border, ink=ink)
    )

if Image:

    @charters.register(name='image')
    def chart_image(
            fonts, outfile, *,
            image_format:str='png',
            image_mode:str='RGB',
            glyphs_per_line:int=16,
            margin:Coord=Coord(0, 0),
            padding:Coord=Coord(1, 1),
            scale:Coord=Coord(1, 1),
            direction:str='left-to-right top-to-bottom',
            border:RGB=RGB(32, 32, 32),
            paper:RGB=RGB(0, 0, 0),
            ink:RGB=RGB(255, 255, 255),
            codepoint_range:tuple[Codepoint]=None,
            grid_positioning:bool=True,
            skip_empty_lines:bool=True,
        ):
        """
        Export font to chart image.

        image_format: image file format (default: 'png')
        image_mode: image colour mode. 'mono', 'grey' or 'rgb' (default)
        glyphs_per_line: number of glyphs per line in glyph chart (default: 32)
        margin: number of pixels in X,Y direction around glyph grid (default: 0x0)
        padding: number of pixels in X,Y direction between glyphs (default: 1x1)
        scale: number of pixels in X,Y direction per glyph bit (default: 1x1)
        direction: two-part string, default 'left-to-right top-to-bottom'
        paper: background colour R,G,B 0--255 (default: 0,0,0)
        ink: full-intensity foreground colour R,G,B 0--255 (default: 255,255,255)
        border: border colour R,G,B 0--255 (default 32,32,32)
        codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepsoints)
        grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: true)
        skip_empty_lines: if -grid-positioning is used, skip lines that have no glyphs (default: true)
        """
        # NOTE 'imagechart' and 'image' are the same but with different defaults
        glyph_map = create_chart(
            fonts,
            glyphs_per_line=glyphs_per_line,
            margin=margin,
            padding=padding,
            scale=scale,
            direction=direction,
            codepoint_range=codepoint_range,
            grid_positioning=grid_positioning,
            skip_empty_lines=skip_empty_lines,
        )
        img, = glyph_map.to_images(
            border=border, paper=paper, ink=ink,
            transparent=False,
            image_mode=image_mode,
        )
        write_imagefile(outfile, img, image_format)


def write_imagefile(outfile, img, image_format):
    """Write a PIL image to file."""
    try:
        img.save(outfile, format=image_format or Path(outfile).suffix[1:])
    except (KeyError, ValueError, TypeError):
        img.save(outfile, format=DEFAULT_IMAGE_FORMAT)


###############################################################################

def create_chart(
        fonts, *,
        glyphs_per_line,
        margin,
        padding,
        scale,
        direction,
        codepoint_range,
        lines_per_page=None,
        max_labels=0,
        label_height=1,
        grid_positioning=False,
        skip_empty_lines=False,
    ):
    """Create chart glyph map of font."""
    font = ensure_single(fonts)
    font = font.equalise_horizontal()
    if grid_positioning:
        font = grid_resample(font, glyphs_per_line, codepoint_range, skip_empty_lines)
    elif codepoint_range:
        font = font.subset(codepoint_range)
    font = font.stretch(*scale)
    # create extra padding space to allow for labels
    if max_labels:
        label_padding = (max_labels+1) * label_height
    else:
        label_padding = 0
    padding = Coord(padding.x, padding.y + label_padding)
    margin = Coord(margin.x, margin.y + label_padding)
    glyph_map = grid_map(
        font,
        glyphs_per_line=glyphs_per_line,
        lines_per_page=lines_per_page,
        margin=margin, padding=padding,
        direction=direction,
    )
    right_align = aligns_right(direction)
    for entry in glyph_map:
        for count, label in enumerate(entry.glyph.get_labels()):
            if count >= max_labels:
                break
            if right_align:
                x = entry.x + entry.glyph.width
            else:
                x = entry.x
            glyph_map.append_label(
                format_label(label),
                x,
                label_height * (ceildiv(entry.y + entry.glyph.height, label_height) + (count + 1)),
                sheet=entry.sheet,
                right_align=right_align,
            )
    return glyph_map


def aligns_right(direction):
    """Determine if a given direction is right-aligning."""
    if not direction:
        return False
    dir_0, _, dir_1 = direction.lower().partition(' ')
    return dir_0[:1] == 'r' or dir_1[:1] == 'r'


def format_label(label):
    """Format glyph label for charts."""
    if isinstance(label, Char):
        ucstr = ', '.join(f'u+{ord(_uc):04x}' for _uc in label.value)
        if all(is_showable(_uc) for _uc in label.value):
            return f'{ucstr} {label.value}'
        return ucstr
    return str(label)


###############################################################################
# grid functions

def grid_resample(font, glyphs_per_line, codepoint_range, skip_empty_lines):
    """Resample font for grid representation."""
    if codepoint_range:
        codepoint_range = tuple(codepoint_range)
        # limit to only the glyphs in range
        font = font.resample(codepoint_range, missing=None, relabel=False)
        # don't bring in more codepoints through charmap
        font = font.label(codepoint_from=font.encoding)
        font = font.modify(encoding=None)
    # fill up all contiguous grid positions
    try:
        codepoints = font.get_codepoints()
    except ValueError:
        # empty sequence
        raise ValueError('No codepoint labels found.')
    if skip_empty_lines:
        lines = {int(_cp) // glyphs_per_line for _cp in codepoints}
        grid_range = chain(*(
            range(glyphs_per_line*_l, glyphs_per_line*(_l+1))
            for _l in sorted(lines)
        ))
    else:
        # start at a codepoint that is a multiple of the number of columns
        grid_range = range(
            glyphs_per_line * (int(min(codepoints, default=0)) // glyphs_per_line),
            int(max(codepoints, default=0)) + 1,
        )
    font = font.resample(grid_range, missing='empty', relabel=False)
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
    if not glyphs_per_page:
        glyph_map = ()
    else:
        glyph_pages = tuple(
            font.glyphs[_s : _s + glyphs_per_page]
            for _s in range(0, len(font.glyphs), glyphs_per_page)
        )
        # horizontal alignment (left or right)
        # note that we have equalised glyphs to the same height
        # so vertical alignment is not needed
        right_align = aligns_right(direction)
        # output glyph maps
        glyph_map = (
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
    glyph_map = GlyphMap(
        glyph_map, levels=font.levels,
        rgb_table=font.rgb_table,
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
