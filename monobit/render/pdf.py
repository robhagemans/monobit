"""
monobit.render.pdf - pdf chart output

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base import safe_import
reportlab = safe_import('reportlab')
if reportlab:
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas

from monobit.storage import savers
from monobit.base import Coord
from monobit.base.binary import ceildiv
from monobit.core import Font, Codepoint, Char, Tag
from monobit.encoding.unicode import is_printable
from monobit.storage.utils.limitations import ensure_single
from .chart import create_chart


def _format_label(label):
    if isinstance(label, Char):
        if is_printable(label.value):
            return f'u+{ord(label):04x} {label.value}'
        else:
            return f'u+{ord(label):04x}'
    return str(label)


if reportlab:

    @savers.register(
        name='pdf',
        patterns=('*.pdf',),
    )
    def save_pdf(
            fonts, outstream, *,
            glyphs_per_line:int=16,
            lines_per_page:int=16,
            padding:Coord=Coord(3, 3),
            direction:str='left-to-right top-to-bottom',
            codepoint_range:tuple[Codepoint]=None,
            max_labels:int=1,
            page_size:Coord=Coord(210, 297),
            margin:Coord=Coord(25, 25),
            title:str='{name}',
            fill_page:bool=False,
        ):
        """
        Export font to chart in Portable Document Format (PDF).

        glyphs_per_line: number of glyphs in primary direction (default: 16)
        lines_per_page: number of lines in secondary direction (default: 16)
        padding: number of pixels in X,Y direction between glyphs (default: 3x3)
        direction: two-part string, default 'left-to-right top-to-bottom'
        codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepoints)
        max_labels: maximum number of labels to show per glyph (default: 1)
        page_size: page size X,Y in millimetres (default 210x297 for A4)
        margin: margin X,Y in millimetres (default 25x25)
        title: title template, using font properties (default: '{name}')
        fill_page: fill out usable space, ignoring pixel aspect ratio (default: False)
        """
        # create extra padding space to allow for labels
        padding = Coord(padding.x, padding.y + max_labels)
        # construct grid pages
        glyph_map = create_chart(
            fonts,
            glyphs_per_line=glyphs_per_line,
            lines_per_page=lines_per_page,
            direction=direction,
            padding=padding,
            codepoint_range=codepoint_range,
            margin=(0, 0),
            scale=(1, 1),
        )
        max_sheet, min_x, min_y, max_x, max_y = glyph_map.get_bounds()
        font, *_ = fonts

        # assume A4
        # note mm is a constant defining number of points in a millimetre
        # 1 point = 1/72 in
        page_x, page_y = page_size.x*mm, page_size.y*mm
        # margins and title position
        title_y = (margin.y // 5)*mm
        margin_x, margin_y = margin.x*mm, margin.y*mm + title_y

        # width and height of usable area, in points
        chart_width = page_x - 2*margin_x
        chart_height = page_y - 2*margin_y - title_y
        # width and height of a pixel, in points
        xpix = chart_width / (max_x - min_x)
        # reserve space for labels at the top (min and max exclude padding)
        ypix = chart_height / (max_y - min_y + max_labels + 1)

        if not fill_page:
            # enforce pixel aspect ratio
            xpix_aspect = (ypix * font.pixel_aspect.x) / font.pixel_aspect.y
            ypix_aspect = (xpix * font.pixel_aspect.y) / font.pixel_aspect.x
            if ypix_aspect <= ypix:
                margin_y += chart_height * (1 - ypix_aspect / ypix)
                chart_height *= ypix_aspect / ypix
                ypix = ypix_aspect
            else:
                margin_x += 0.5 * chart_width * (1 - xpix_aspect / xpix)
                chart_width *= xpix_aspect / xpix
                xpix = xpix_aspect

        # horizontal alignment
        # note that prepare_for_grid_map has equallised glyphs horizontally
        dir_0, _, dir_1 = direction.partition(' ')
        right_align = dir_0[:1] == 'r' or dir_1[:1] == 'r'

        canvas = Canvas(outstream)
        # draw title on first page
        canvas.translate(margin_x, margin_y)
        canvas.setFont('Helvetica-Bold', title_y)
        if right_align:
            canvas.drawRightString(
                chart_width, chart_height + title_y,
                font.format_properties(title),
            )
        else:
            canvas.drawString(
                0, chart_height + title_y,
                font.format_properties(title),
            )
        canvas.translate(-margin_x, -margin_y)

        # draw pages
        for sheet in range(max_sheet+1):
            canvas.setPageSize((page_x, page_y))
            canvas.translate(margin_x, margin_y)
            canvas.setLineWidth(xpix / 10)
            canvas.setStrokeColorRGB(0.5, 0.5, 0.5)
            canvas.setFillColorRGB(0, 0, 0)
            # text is the height of one glyph pixel
            canvas.setFont('Helvetica', ypix)

            # output glyph grid
            for record in glyph_map.get_sheet(sheet):
                # draw label
                for count, label in enumerate(record.glyph.get_labels()):
                    if count >= max_labels:
                        break
                    if right_align:
                        canvas.drawRightString(
                            (record.x + font.raster_size.x) * xpix,
                            (record.y + font.raster_size.y + count + 1) * ypix,
                            _format_label(label)
                        )
                    else:
                        canvas.drawString(
                            record.x * xpix,
                            (record.y + font.raster_size.y + count + 1) * ypix,
                            _format_label(label)
                        )
                # draw glyph
                pixels = record.glyph.as_matrix()
                for y in range(len(pixels)):
                    for x in range(len(pixels[y])):
                        fill = 1 - pixels[y][x] / (font.levels-1)
                        canvas.setFillColorRGB(fill, fill, fill)
                        canvas.rect(
                            (record.x + x) * xpix,
                            (record.y + record.glyph.height - y - 1) * ypix,
                            xpix, ypix,
                            fill=bool(pixels[y][x])
                        )
                        canvas.setFillColorRGB(0, 0, 0)
            canvas.showPage()
        canvas.save()
