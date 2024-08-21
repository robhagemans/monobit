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
from .chart import prepare_for_grid_map, grid_map


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
            columns:int=16,
            padding:Coord=Coord(3, 3),
            direction:str='left-to-right top-to-bottom',
            codepoint_range:tuple[Codepoint]=None,
            rows_per_page:int=16,
            max_labels:int=1,
        ):
        """
        Export font to chart in Portable Document Format (PDF).
        """
        font = ensure_single(fonts)
        font = prepare_for_grid_map(font, columns, codepoint_range)

        canvas = Canvas(outstream)
        # assume A4
        # note mm is a constant defining number of points in a millimetre
        # 1 point = 1/72 in
        page_x, page_y = 210*mm, 297*mm
        # margins and title position
        margin_x, margin_y = 28*mm, 30*mm
        title_y = 5*mm

        # width and height of usable area, in points
        chart_width = page_x - 2*margin_x
        chart_height = page_y - 2*margin_y - title_y

        # width and height of glyph box, in "pixels"
        padding = Coord(padding.x, padding.y + max_labels)
        width = font.raster_size.x + padding.x
        height = font.raster_size.y + padding.y

        # FIXME assumes horizontal-first
        rows = ceildiv(len(font.glyphs), columns)
        # use rows_per_page=None or 0 to force all glyphs on one page
        rows_per_page = rows_per_page or rows

        # width and height of a pixel, in points
        xpix = chart_width / columns / width
        ypix = chart_height / rows_per_page / height

        glyphs_per_page = rows_per_page * columns
        glyph_groups = (
            font.glyphs[_s : _s + glyphs_per_page]
            for _s in range(0, len(font.glyphs), glyphs_per_page)
        )

        # draw title on first page
        canvas.translate(margin_x, margin_y)
        canvas.setFont('Helvetica-Bold', title_y)
        canvas.drawString(0, chart_height + title_y, font.name)
        canvas.translate(-margin_x, -margin_y)

        # draw pages
        for group in glyph_groups:
            canvas.translate(margin_x, margin_y)
            canvas.setLineWidth(xpix / 10)
            canvas.setStrokeColorRGB(0.5, 0.5, 0.5)
            canvas.setFillColorRGB(0, 0, 0)
            # text is the height of one glyph pixel
            canvas.setFont('Helvetica', ypix)

            # output glyph map
            glyph_map = grid_map(
                Font(group),
                columns=columns,
                rows=rows_per_page,
                direction=direction,
                padding=padding,
            )
            for record in glyph_map.get_records():
                # draw label
                for count, label in enumerate(record.glyph.get_labels()):
                    if count >= max_labels:
                        break
                    canvas.drawString(
                        record.x * xpix,
                        (record.y + font.raster_size.y + count + 1) * ypix,
                        _format_label(label)
                    )
                # draw glyph
                pixels = record.glyph.as_matrix()
                for y in range(len(pixels)):
                    for x in range(len(pixels[y])):
                        canvas.rect(
                            (record.x + x) * xpix,
                            (record.y + record.glyph.height - y - 1) * ypix,
                            xpix, ypix,
                            fill=pixels[y][x]
                        )
            canvas.showPage()
        canvas.save()
