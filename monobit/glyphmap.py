"""
monobit.glyphmap - glyph maps

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

try:
    from PIL import Image
except ImportError:
    Image = None

from .properties import Props
from .raster import Raster
from .blocks import  blockstr


class GlyphMap:

    def __init__(self, map=()):
        self._map = list(map)
        self._turns = 0
        self._scale_x = 1
        self._scale_y = 1

    def __iter__(self):
        return iter(self._map)

    def __contains__(self, item):
        return item in self._map

    def turn(self, clockwise=1, *, anti=0):
        turns = clockwise - anti
        if turns%2:
            self._scale_x, self._scale_y = self._scale_y, self._scale_x
        self._turns += turns

    def stretch(self, scale_x=1, scale_y=1):
        self._scale_x *= scale_x
        self._scale_y *= scale_y

    def append_glyph(self, glyph, x, y, sheet=0):
        """Insert glyph in glyph map."""
        self._map.append(Props(glyph=glyph, x=x, y=y, sheet=sheet))

    def reorder(self, mapping):
        """Rearrange glyphs through index mapping."""
        self._map = [
            self._map[mapping[_i]]
            for _i in range(len(self._map))
        ]

    def get_bounds(self):
        """Get extreme coordinates across all sheets. Bounds are inclusive."""
        last = max(_entry.sheet for _entry in self._map)
        min_x = min(_entry.x for _entry in self._map)
        min_y = min(_entry.y for _entry in self._map)
        # inclusive bounds - we included the width/height of the glyphs
        # e.g. if I have a 2-pixel wide glyph at x=0, I need a 2-pixel image
        max_x = max(_entry.x + _entry.glyph.width for _entry in self._map)
        max_y = max(_entry.y + _entry.glyph.height for _entry in self._map)
        return last, min_x, min_y, max_x, max_y

    def to_canvas(self, sheet=0):
        """Convert one sheet of the glyph map to canvas."""
        # note that this gives the bounds across *all* sheets
        _, min_x, min_y, max_x, max_y = self.get_bounds()
        # no +1 as bounds are inclusive
        canvas = Canvas.blank(max_x - min_x, max_y - min_y)
        for entry in self._map:
            if entry.sheet == sheet:
                canvas.blit(
                    entry.glyph, entry.x - min_x, entry.y - min_y, operator=max
                )
        return canvas.stretch(self._scale_x, self._scale_y).turn(self._turns)

    def to_images(
            self, *, paper, ink, border, invert_y=False,
            transparent=True
        ):
        """Draw images based on shhets in glyph map."""
        if not Image:
            raise ImportError('Rendering to image requires PIL module.')
        paper, ink, border = 0, 255, 32
        last, min_x, min_y, max_x, max_y = self.get_bounds()
        # no +1 as bounds are inclusive
        width, height = max_x - min_x, max_y - min_y
        images = [Image.new('L', (width, height), border) for _ in range(last+1)]
        for entry in self._map:
            charimg = Image.new('L', (entry.glyph.width, entry.glyph.height))
            data = entry.glyph.as_bits(ink, paper)
            charimg.putdata(data)
            if invert_y:
                target = (entry.x, entry.y)
            else:
                # Image has ttb y coords, we have btt
                # our character origin is bottom left
                target = (entry.x-min_x, height-entry.glyph.height+min_y-entry.y)
            if transparent:
                mask = charimg
            else:
                mask = None
            images[entry.sheet].paste(charimg, target, mask)
        images = tuple(
            _im.resize((self._scale_x*_im.width, self._scale_y*_im.height))
                .rotate(-90 * self._turns, expand=True)
            for _im in images
        )
        return images

    def as_image(
            self, *,
            ink=(255, 255, 255), paper=(0, 0, 0), border=(0, 0, 0),
            sheet=0,
        ):
        """Convert glyph map to image."""
        images = self.to_images(ink=ink, paper=paper, border=border)
        return images[sheet]

    def as_text(
            self, *,
            ink='@', paper='.', border='.',
            start='', end='',
            sheet=0,
        ):
        """Convert glyph map to text."""
        canvas = self.to_canvas(sheet=sheet)
        return canvas.as_text(
            ink=ink, paper=paper, border=border, start=start, end=end
        )

    def as_blocks(self, resolution=(2, 2)):
        """Convert glyph map to a string of quadrant block characters."""
        canvas = self.to_canvas(sheet=0)
        return canvas.as_blocks(resolution)


class Canvas(Raster):
    """Mutable raster for glyph maps."""

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

    def blit(self, raster, grid_x, grid_y, operator):
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
