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
from .canvas import Canvas


class GlyphMap:

    def __init__(self, map=()):
        self._map = list(map)

    def __iter__(self):
        return iter(self._map)

    def __contains__(self, item):
        return item in self._map

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
        return canvas

    def to_images(self, *, paper, ink, border, invert_y=False):
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
                target = (entry.x, height-entry.glyph.height-entry.y)
            images[entry.sheet].paste(charimg, target)
        return images
