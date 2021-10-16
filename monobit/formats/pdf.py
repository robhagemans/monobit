"""
monobit.pdf - pdf chart output

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

try:
    import reportlab
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
except ImportError:
    reportlab = None

from ..formats import savers
from ..streams import FileFormatError


if reportlab:
    @savers.register('pdf')
    def save(
            fonts, outfile, where=None,
            format:str='png',
            columns:int=16,
            rows:int=16,
            encoding:str=None,
        ):
        """Export font to pdf chart."""
        if len(fonts) > 1:
            raise FileFormatError('Can only save one font to PDF file.')
        font = fonts[0]
        canvas = Canvas(outfile)
        # assume A4
        page_x, page_y = 210*mm, 297*mm
        margin_x, margin_y = 28*mm, 30*mm
        # work with maximum raster size
        width = font.max_raster_size.x + 2
        height = font.max_raster_size.y + 4
        xpix, ypix = (page_x-2*margin_x)/columns/width, (page_y-2*margin_y)/rows/height
        canvas.translate(margin_x, margin_y)
        canvas.setLineWidth(xpix/10)
        canvas.setStrokeColorRGB(0.5, 0.5, 0.5)
        canvas.setFillColorRGB(0, 0, 0)
        canvas.setFont('Helvetica', ypix)
        if encoding is not None:
            #FIXME
            pass
        for col in range(columns):
            for row in range(rows):
                orig_x, orig_y = col*xpix*width, (rows-row-1)*ypix*height
                n = columns * row + col
                if n < len(font.glyphs):
                    canvas.drawString(orig_x, orig_y+font.max_raster_size.y*ypix + 3, f'{n:02X}: {font.glyphs[n].char}')
                    glyph = font.glyphs[n].as_matrix()
                    for y in range(len(glyph)):
                        for x in range(len(glyph[y])):
                            canvas.rect(orig_x+x*xpix, orig_y+(len(glyph)-y-1)*ypix, xpix, ypix, fill=glyph[y][x])
        canvas.showPage()
        canvas.save()
