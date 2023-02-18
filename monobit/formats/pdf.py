"""
monobit.formats.pdf - pdf chart output

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

try:
    import reportlab
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
except ImportError:
    reportlab = None

from ..storage import savers
from ..magic import FileFormatError


if reportlab:

    @savers.register(
        name='pdf',
        patterns=('*.pdf',),
    )
    def save_pdf(
            fonts, outfile,
            columns:int=16,
            rows:int=16,
        ):
        """
        Export font to chart in Portable Document Format (PDF).

        columns: number of columns in chart
        rows: number of rows in chart
        """
        if len(fonts) > 1:
            raise FileFormatError('Can only export one font to PDF file.')
        font = fonts[0]
        font = font.equalise_horizontal()
        canvas = Canvas(outfile)
        # assume A4
        page_x, page_y = 210*mm, 297*mm
        margin_x, margin_y = 28*mm, 30*mm
        title_y = 5*mm
        chart_width = page_x - 2*margin_x
        chart_height = page_y - 2*margin_y - title_y
        # work with maximum raster size
        width = font.raster_size.x + 2
        height = font.raster_size.y + 4
        xpix = chart_width / columns / width
        ypix = chart_height / rows / height
        canvas.translate(margin_x, margin_y)
        canvas.setLineWidth(xpix/10)
        canvas.setStrokeColorRGB(0.5, 0.5, 0.5)
        canvas.setFillColorRGB(0, 0, 0)
        canvas.setFont('Helvetica-Bold', title_y)
        canvas.drawString(0, chart_height + title_y, font.name)
        canvas.setFont('Helvetica', ypix)
        for col in range(columns):
            for row in range(rows):
                orig_x, orig_y = col*xpix*width, (rows-row-1)*ypix*height
                n = columns * row + col
                if n < len(font.glyphs):
                    glyph = font.glyphs[n]
                    label = (
                        f'{str(glyph.codepoint)}: {glyph.char} '
                        + ' '.join(
                            f'[{_tag}]' for _tag in glyph.tags
                        )
                    )
                    canvas.drawString(orig_x, orig_y+font.raster_size.y*ypix + 3, label)
                    pixels = glyph.as_matrix()
                    for y in range(len(pixels)):
                        for x in range(len(pixels[y])):
                            canvas.rect(
                                orig_x+x*xpix, orig_y+(len(pixels)-y-1)*ypix, xpix, ypix,
                                fill=pixels[y][x]
                            )
        canvas.showPage()
        canvas.save()
