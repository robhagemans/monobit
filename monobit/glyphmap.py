"""
monobit.glyphmap - glyph maps

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

try:
    from PIL import Image
except ImportError:
    Image = None

from .canvas import Canvas


class GlyphMap:

    @staticmethod
    def to_canvas(glyph_map):
        """Convert glyph map to canvas."""
        min_x = min(_entry.x for _entry in glyph_map)
        min_y = min(_entry.y for _entry in glyph_map)
        max_x = max(_entry.x + _entry.glyph.width for _entry in glyph_map)
        max_y = max(_entry.y + _entry.glyph.height for _entry in glyph_map)
        # we don't need +1 as we already included the width/height of the glyphs
        # e.g. if I have a 2-pixel wide glyph at x=0, I need a 2-pixel image
        canvas = Canvas.blank(max_x - min_x, max_y - min_y)
        for entry in glyph_map:
            canvas.blit(
                entry.glyph, entry.x - min_x, entry.y - min_y, operator=max
            )
        return canvas

    @staticmethod
    def to_images(glyph_map, *, paper, ink, border, invert_y=False):
        """Draw images based on glyph map."""
        if not Image:
            raise ImportError('Rendering to image requires PIL module.')
        paper, ink, border = 0, 255, 32
        last = max(_entry.sheet for _entry in glyph_map)
        min_x = min(_entry.x for _entry in glyph_map)
        min_y = min(_entry.y for _entry in glyph_map)
        max_x = max(_entry.x + _entry.glyph.width for _entry in glyph_map)
        max_y = max(_entry.y + _entry.glyph.height for _entry in glyph_map)
        # we don't need +1 as we already included the width/height of the glyphs
        # e.g. if I have a 2-pixel wide glyph at x=0, I need a 2-pixel image
        width, height = max_x - min_x, max_y - min_y
        images = [Image.new('L', (width, height), border) for _ in range(last+1)]
        for entry in glyph_map:
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
