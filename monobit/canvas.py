"""
monobit.canvas - bitmap drawing operations

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


try:
    from PIL import Image
except ImportError:
    Image = None

from .raster import Raster, blockstr


class Canvas(Raster):
    """Mutable raster."""

    _inner = list
    _outer = list
    _0 = 0
    _1 = 1
    _itemtype = int

    @classmethod
    def blank(cls, width, height, fill=-1):
        """Create a canvas in background colour."""
        canvas = [[fill]*width for _ in range(height)]
        # setting 0 and 1 will make Raster init leave the input alone
        return cls(canvas, _0=0, _1=1)


    default_blit_operator = lambda _m, _c: 1 if (_m==1 or _c==1) else _c

    @classmethod
    def from_glyph_map(cls, glyph_map):
        """Create canvas froom glyph map."""
        min_x = min(_entry.x for _entry in glyph_map)
        min_y = min(_entry.y for _entry in glyph_map)
        max_x = max(_entry.x + _entry.glyph.width for _entry in glyph_map)
        max_y = max(_entry.y + _entry.glyph.height for _entry in glyph_map)
        # we don't need +1 as we already included the width/height of the glyphs
        # e.g. if I have a 2-pixel wide glyph at x=0, I need a 2-pixel image
        canvas = cls.blank(max_x - min_x, max_y - min_y)
        for entry in glyph_map:
            canvas.blit(
                entry.glyph, entry.x - min_x, entry.y - min_y, operator=max
            )
        return canvas

    def blit(self, raster, grid_x, grid_y, operator=default_blit_operator):
        """
        Draw a matrix onto a canvas
        (leaving exising ink in place, depending on operator).
        """
        if not raster.width or not self.width:
            return self
        matrix = raster.as_matrix()
        for work_y in reversed(range(raster.height)):
            if 0 <= grid_y + work_y < self.height:
                row = self._pixels[self.height - (grid_y + work_y) - 1]
                for work_x, ink in enumerate(matrix[raster.height - work_y - 1]):
                    if 0 <= grid_x + work_x < self.width:
                        row[grid_x + work_x] = operator(ink, row[grid_x + work_x])
        return self

    def as_image(
            self, *,
            ink=(255, 255, 255), paper=(0, 0, 0), border=(0, 0, 0)
        ):
        """Convert raster to image."""
        if not Image:
            raise ImportError('Rendering to image requires PIL module.')
        if not self.height:
            return Image.new('RGB', (0, 0))
        img = Image.new('RGB', (self.width, self.height), border)
        img.putdata([
            {-1: border, 0: paper, 1: ink}[_pix]
            for _row in self._pixels for _pix in _row
        ])
        return img

    def as_text(
            self, *,
            ink='@', paper='.', border='.',
            start='', end=''
        ):
        """Convert raster to text."""
        if not self.height:
            return ''
        colourdict = {-1: border, 0: paper, 1: ink}
        contents = '\n'.join(
            ''.join(colourdict[_pix] for _pix in _row)
            for _row in self._pixels
        )
        return blockstr(''.join((start, contents, end)))

    def draw_pixel(self, x, y):
        """Draw a pixel."""
        self._pixels[self.height - y - 1][x] = 1

    def draw_line(self, x0, y0, x1, y1):
        """Draw a line between the given points."""
        # Bresenham algorithm
        dx, dy = abs(x1-x0), abs(y1-y0)
        steep = dy > dx
        if steep:
            x0, y0, x1, y1 = y0, x0, y1, x1
            dx, dy = dy, dx
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1
        line_error = dx // 2
        x, y = x0, y0
        for x in range(x0, x1+sx, sx):
            if steep:
                self.draw_pixel(y, x)
            else:
                self.draw_pixel(x, y)
            line_error -= dy
            if line_error < 0:
                y += sy
                line_error += dx
