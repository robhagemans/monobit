"""
monobit.render.glyphmap - glyph maps

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.base.blocks import matrix_to_blocks, blockstr
from ..base import Props, Coord
from ..core.raster import turn_method
from ..plumbing import convert_arguments


def glyph_to_image(glyph, paper, ink):
    """Create image of single glyph."""
    image_mode = _get_image_mode(paper, ink, paper)
    charimg = Image.new(image_mode, (glyph.width, glyph.height))
    # create ink gradient
    if isinstance(ink, int):
        ink = (ink,)
        paper = (paper,)
    maxlevel = glyph.levels - 1
    inklevels = tuple(
        tuple(
            (_i * _ink + (maxlevel - _i) * _paper) // maxlevel
            for _ink, _paper in zip(ink, paper)
        )
        for _i in range(glyph.levels)
    )
    data = glyph.as_bits(inklevels=inklevels)
    if image_mode in ('RGB', 'RGBA'):
        # itertools grouper idiom, split in groups of 3 or 4 bytes
        iterators = [iter(data)] * len(image_mode)
        # strict=True requires python 3.10 or above
        data = tuple(zip(*iterators)) #, strict=True))
    charimg.putdata(data)
    return charimg


def _get_image_mode(*colourspec):
    if not Image:
        raise ImportError('Rendering to image requires PIL module.')
    if len(set(type(_c) for _c in colourspec)) > 1:
        raise TypeError(
            'paper, ink and border must be of the same type; '
            f'got {colourspec}'
        )
    paper, ink, border = colourspec
    if paper == border == 0 and ink == 1:
        image_mode = '1'
    elif isinstance(paper, int):
        image_mode = 'L'
    elif isinstance(paper, tuple) and len(paper) == 3:
        image_mode = 'RGB'
    elif isinstance(paper, tuple) and len(paper) == 4:
        image_mode = 'RGBA'
    else:
        raise TypeError('paper, ink and border must be either int or RGB(A) tuple')
    return image_mode


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
        canvas = _Canvas.blank(max_x - min_x, max_y - min_y)
        for entry in self._map:
            if entry.sheet == sheet:
                canvas.blit(entry.glyph, entry.x - min_x, entry.y - min_y)
        return canvas.stretch(self._scale_x, self._scale_y).turn(self._turns)

    def to_images(
            self, *, paper=0, ink=255, border=0, invert_y=False,
            transparent=True,
        ):
        """Draw images based on sheets in glyph map."""
        image_mode = _get_image_mode(paper, ink, border)
        last, min_x, min_y, max_x, max_y = self.get_bounds()
        # no +1 as bounds are inclusive
        width, height = max_x - min_x, max_y - min_y
        images = [Image.new(image_mode, (width, height), border) for _ in range(last+1)]
        for entry in self._map:
            # we need to treat the background colour as transparent
            # we create the glyph as a mask and cut it from a solid ink-colour
            if transparent:
                mask = glyph_to_image(entry.glyph, 0, 255)
                colour = Image.new(image_mode, mask.size, ink)
            else:
                mask = None
                colour = glyph_to_image(entry.glyph, paper, ink)
            if invert_y:
                target = (entry.x, entry.y)
            else:
                # Image has ttb y coords, we have btt
                # our character origin is bottom left
                target = (entry.x-min_x, height-entry.glyph.height+min_y-entry.y)
            images[entry.sheet].paste(colour, target, mask)
        images = tuple(
            _im.resize((self._scale_x*_im.width, self._scale_y*_im.height))
                .rotate(-90 * self._turns, expand=True)
            for _im in images
        )
        return images

    def as_image(
            self, *,
            ink=255, paper=0, border=0,
            sheet=0, invert_y=False,
        ):
        """Convert glyph map to image."""
        images = self.to_images(
            ink=ink, paper=paper, border=border, invert_y=invert_y,
        )
        return images[sheet]

    def as_text(
            self, *,
            ink='@', paper='.', border='.',
            start='', end='\n',
            sheet=0,
        ):
        """Convert glyph map to text."""
        canvas = self.to_canvas(sheet=sheet)
        return canvas.as_text(
            ink=ink, paper=paper, border=border, start=start, end=end
        )

    @convert_arguments
    def as_blocks(self, resolution:Coord=(2, 2)):
        """Convert glyph map to a string of quadrant block characters."""
        canvas = self.to_canvas(sheet=0)
        return canvas.as_blocks(resolution)


class _Canvas:
    """Blittable raster for glyph maps."""

    def __init__(self, pixels):
        """Create raster from tuple of tuples of string."""
        self._pixels = pixels
        self.height = len(pixels)
        self.width = 0 if not pixels else len(pixels[0])

    @classmethod
    def blank(cls, width, height, fill=-1):
        """Create a canvas in background colour."""
        canvas = [[fill]*width for _ in range(height)]
        return cls(canvas)

    def blit(self, raster, grid_x, grid_y):
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
                        row[grid_x + work_x] = max(ink, row[grid_x + work_x])
        return self

    def as_text(
            self, *,
            ink='@', paper='.', border='.',
            start='', end='\n'
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

    def as_blocks(self, resolution=(2, 2)):
        """Convert glyph to a string of block characters."""
        if not self.height:
            return ''
        return matrix_to_blocks(self._pixels, *resolution)

    def stretch(self, factor_x:int=1, factor_y:int=1):
        """
        Repeat rows and/or columns.

        factor_x: number of times to repeat horizontally
        factor_y: number of times to repeat vertically
        """
        # vertical stretch
        pixels = (_row for _row in self._pixels for _ in range(factor_y))
        # horizontal stretch
        pixels = [
            [_col for _col in _row for _ in range(factor_x)]
            for _row in pixels
        ]
        return type(self)(pixels)

    def flip(self):
        """Reverse pixels vertically."""
        return type(self)(self._pixels[::-1])

    def transpose(self):
        """Transpose glyph."""
        return type(self)([list(_r) for _r in zip(*self._pixels)])

    turn = turn_method
