"""
monobit.render.glyphmap - glyph maps

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.base.blocks import matrix_to_blocks, matrix_to_shades, blockstr
from ..base import Props, Coord, RGB
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
    data = glyph.as_pixels(inklevels=inklevels)
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
        self._labels = []
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

    def append_label(self, text, x, y, *, sheet=0, right_align=False):
        """Insert glyph in glyph map."""
        self._labels.append(Props(text=text, x=x, y=y, sheet=sheet, right_align=right_align))

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
        for entry in self._labels:
            if entry.sheet == sheet:
                canvas.write(entry.text, entry.x - min_x, entry.y - min_y, entry.right_align)
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
            inklevels=' @',
            border=None,
            start='', end='\n',
            sheet=0,
        ):
        """Convert glyph map to text."""
        canvas = self.to_canvas(sheet=sheet)
        return canvas.as_text(
            inklevels=inklevels, border=border, start=start, end=end
        )

    @convert_arguments
    def as_blocks(self, resolution:Coord=Coord(2, 2), *, sheet=0):
        """Convert glyph map to a string of quadrant block characters."""
        canvas = self.to_canvas(sheet=sheet)
        return canvas.as_blocks(resolution)

    def as_shades(
            self, *,
            paper=RGB(0, 0, 0), ink=RGB(255, 255, 255), border=None, sheet=0,
        ):
        """Convert glyph map to ansi coloured block characters."""
        canvas = self.to_canvas(sheet=sheet)
        return canvas.as_shades(paper=paper, ink=ink, border=border)

    def get_sheet(self, sheet=0):
        """Return glyph records for a given sheet."""
        return tuple(_e for _e in self._map if _e.sheet == sheet)

    def get_sheet_labels(self, sheet=0):
        """Return labels for a given sheet."""
        return tuple(_e for _e in self._labels if _e.sheet == sheet)


class _Canvas:
    """Blittable raster for glyph maps."""

    def __init__(self, pixels, levels=2, labels=()):
        """Create raster from tuple of tuples of string."""
        self._pixels = pixels
        self._labels = list(labels)
        self.height = len(pixels)
        self.width = 0 if not pixels else len(pixels[0])
        self.levels = levels

    @classmethod
    def blank(cls, width, height, fill=-1):
        """Create a canvas in background colour."""
        canvas = [[fill]*width for _ in range(height)]
        return cls(canvas)

    def blit(self, raster, grid_x, grid_y):
        """Draw a matrix onto a canvas, leaving existing ink in place."""
        if not raster.width or not self.width:
            return self
        matrix = raster.as_matrix()
        self.levels = max(self.levels, raster.levels)
        for work_y in reversed(range(raster.height)):
            if 0 <= grid_y + work_y < self.height:
                row = self._pixels[self.height - (grid_y + work_y) - 1]
                for work_x, ink in enumerate(matrix[raster.height - work_y - 1]):
                    if 0 <= grid_x + work_x < self.width:
                        # grayscale will be additive until full-ink level
                        row[grid_x + work_x] = min(
                            self.levels - 1,
                            max(0, ink) + max(0, row[grid_x + work_x]),
                        )
        return self

    def write(self, text, x, y, right_align=False):
        """Add a text label onto the canvas"""
        self._labels.append((text, x, y, right_align))

    def _write_labels_to_matrix(self, matrix, resolution=Coord(1, 1)):
        """Write labels to text or blocks matrix."""
        if not matrix:
            return
        for text, x, y, right_align in self._labels:
            x //= resolution.x
            y //= resolution.y
            if y < 0 or y > len(matrix) - 1:
                continue
            width = len(matrix[0])
            text = list(text)
            if right_align:
                if x - len(text) < 0:
                    text = text[:-x+len(text)]
                matrix[len(matrix) - y - 1][x-len(text) : x] = text
            else:
                if x + len(text) > self.width:
                    text = text[:self.width-x-len(text)]
                matrix[len(matrix) - y - 1][x : x+len(text)] = text

    def as_text(
            self, *,
            inklevels=' @', border=None,
            start='', end='\n'
        ):
        """Convert glyph map to text."""
        if not self.height:
            return ''
        if self.levels > len(inklevels):
            raise ValueError(f'Requires at least {self.levels} greyscale levels.')
        if not border:
            border = inklevels[0]
        colourdict = {-1: border} | {
            _i: _v for _i, _v in enumerate(inklevels)
        }
        matrix = [
            [colourdict[_pix] for _pix in _row]
            for _row in self._pixels
        ]
        # write out labels
        self._write_labels_to_matrix(matrix)
        # join all text together
        contents = '\n'.join(''.join(_row) for _row in matrix)
        return blockstr(''.join((start, contents, end)))

    def as_blocks(self, resolution=Coord(2, 2)):
        """Convert glyph map to a string of block characters."""
        if not self.height:
            return ''
        # replace background with paper
        pixels = tuple(
            tuple(
                0 if _pix == -1 else _pix
                for _pix in _row
            )
            for _row in self._pixels
        )
        block_matrix = matrix_to_blocks(pixels, *resolution, levels=self.levels)
        self._write_labels_to_matrix(block_matrix, resolution=resolution)
        blocks = '\n'.join(''.join(_row) for _row in block_matrix)
        return blockstr(blocks + '\n')

    def as_shades(self, *, paper, ink, border):
        """Convert glyph map to a string of block characters with ansi colours."""
        if not self.height:
            return ''
        block_matrix = matrix_to_shades(
            self._pixels, levels=self.levels,
            paper=paper, ink=ink, border=border,
        )
        self._write_labels_to_matrix(block_matrix)
        blocks = '\n'.join(''.join(_row) for _row in block_matrix)
        return blockstr(blocks + '\n')

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
        # adjust labels
        labels = [
            (_text, _x*factor_x, _y*factor_y, _ralign)
            for _text, _x, _y, _ralign in self._labels
        ]
        return type(self)(pixels, levels=self.levels, labels=labels)

    def flip(self):
        """Reverse pixels vertically."""
        # adjust labels
        labels = [
            (_text, _x, self.height-_y-1, _ralign)
            for _text, _x, _y, _ralign in self._labels
        ]
        return type(self)(self._pixels[::-1], levels=self.levels, labels=labels)

    def transpose(self):
        """Transpose glyph."""
        # adjust labels
        labels = [
            (_text, _y, _x, _ralign)
            for _text, _x, _y, _ralign in self._labels
        ]
        return type(self)(
            [list(_r) for _r in zip(*self._pixels)],
            levels=self.levels,
            labels=labels,
        )

    turn = turn_method
