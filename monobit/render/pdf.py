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
from monobit.base import Coord, RGB
from monobit.base.binary import ceildiv
from monobit.core import Font, Codepoint
from monobit.storage.utils.limitations import ensure_single
from .chart import create_chart, aligns_right


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
            direction:str=None,
            pixel_border:RGB=RGB(127, 127, 127),
            ink:RGB=RGB(0, 0, 0),
            paper:RGB=RGB(255, 255, 255),
            codepoint_range:tuple[Codepoint]=None,
            grid_positioning:bool=False,
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
        direction: two-part string such as 'left-to-right top-to-bottom'. Default: font direction.
        pixel_border: colour of lines around pixel squares R,G,B, 0--255. use -1,-1,-1 for no border (default: 127,127,127)
        paper: background colour R,G,B 0--255 (default: 255,255,255)
        ink: full-intensity foreground colour R,G,B 0--255 (default: 0,0,0)
        codepoint_range: range of codepoints to include (includes bounds and undefined codepoints; default: all codepoints)
        grid_positioning: place codepoints on corresponding grid positions, leaving gaps if undefined (default: false)
        max_labels: maximum number of labels to show per glyph (default: 1)
        page_size: page size X,Y in millimetres (default 210x297 for A4)
        margin: margin X,Y in millimetres (default 25x25)
        title: title template, using font properties (default: '{name}')
        fill_page: fill out usable space, ignoring pixel aspect ratio (default: False)
        """
        # construct grid pages
        glyph_map = create_chart(
            fonts,
            glyphs_per_line=glyphs_per_line,
            lines_per_page=lines_per_page,
            direction=direction,
            padding=padding,
            codepoint_range=codepoint_range,
            grid_positioning=grid_positioning,
            margin=Coord(0, 0),
            scale=Coord(1, 1),
            max_labels=max_labels,
        )
        max_sheet, min_x, min_y, max_x, max_y = glyph_map.get_bounds()
        font, *_ = fonts

        # assume A4
        # note mm is a )constant defining number of points in a millimetre
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
        # note that create_chart has equalised glyphs horizontally
        direction = direction or font.direction
        right_align = aligns_right(direction)

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
            # text is the height of one glyph pixel
            canvas.setFont('Helvetica', ypix)

            # output glyph grid
            for record in glyph_map.get_sheet(sheet):
                # draw glyph
                pixels = record.glyph.as_matrix()
                for y in range(len(pixels)):
                    for x in range(len(pixels[y])):
                        fill = pixels[y][x] / (font.levels-1)
                        fill_rgb = tuple(
                            _i * fill/255 + _p * (1-fill)/255
                            for _i, _p in zip(ink, paper)
                        )
                        if all(_c > 0 for _c in pixel_border):
                            stroke_rgb = tuple(_c / 255 for _c in pixel_border)
                        else:
                            stroke_rgb = fill_rgb
                        canvas.setStrokeColorRGB(*stroke_rgb)
                        canvas.setFillColorRGB(*fill_rgb)
                        canvas.rect(
                            (record.x + x) * xpix,
                            (record.y + record.glyph.height - y - 1) * ypix,
                            xpix, ypix,
                            fill=True,
                        )
                        canvas.setFillColorRGB(0, 0, 0)
            canvas.setStrokeColorRGB(0, 0, 0)
            for label in glyph_map.get_sheet_labels(sheet):
                # draw label
                if label.right_align:
                    canvas.drawRightString(label.x*xpix, label.y*ypix, label.text)
                else:
                    canvas.drawString(label.x*xpix, label.y*ypix, label.text)
            canvas.showPage()
        canvas.save()
