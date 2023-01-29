"""
monobit.renderer - render text to bitmaps using font

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from unicodedata import bidirectional, normalize, category

try:
    from bidi.algorithm import get_display, get_base_level
except ImportError:
    def _bidi_not_found(*args, **kwargs):
        raise ImportError(
            'Bidirectional text requires module `python-bidi`; not found.'
        )
    get_display = _bidi_not_found
    get_base_level = _bidi_not_found

try:
    from arabic_reshaper import reshape
except ImportError:
    def reshape(text):
        raise ImportError(
            'Arabic text requires module `arabic-reshaper`; not found.'
        )

try:
    from uniseg.graphemecluster import grapheme_clusters
except ImportError:
    logging.warning(
        'Module `uniseg` not found. Grapheme clusters may not render correctly.'
    )
    def grapheme_clusters(text):
        """Use NFC as poor-man's grapheme cluster. This works... sometimes."""
        for c in normalize('NFC', text):
            yield c

try:
    from PIL import Image
except ImportError:
    Image = None

from .binary import ceildiv
from .labels import Char, Codepoint
from .raster import Raster, blockstr



DIRECTIONS = {
    'n': 'normal',
    'l': 'left-to-right',
    'r': 'right-to-left',
    't': 'top-to-bottom',
    'b': 'bottom-to-top'
}

ALIGNMENTS = {
    'l': 'left',
    'r': 'right',
    't': 'top',
    'b': 'bottom'
}


###############################################################################
# canvas operations

class Canvas(Raster):
    """Mutable raster."""

    _sequence = list

    @classmethod
    def blank(cls, width, height, fill=-1):
        """Create a canvas in background colour."""
        canvas = [[fill]*width for _ in range(height)]
        # setting 0 and 1 will make Raster init leave the input alone
        return cls(canvas, _0=0, _1=1)

    def blit(self, raster, grid_x, grid_y, operator=lambda _m, _c: 1 if (_m==1 or _c==1) else _c):
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


###############################################################################
# text rendering

def render(
        font, text, *, margin=(0, 0), adjust_bearings=0,
        direction='', align='',
        missing='default'
    ):
    """Render text string to bitmap."""
    direction, line_direction, base_direction, align = _get_direction(
        font, text, direction, align
    )
    # get glyphs for rendering
    glyphs = _get_text_glyphs(
        font, text, direction, line_direction, base_direction, missing
    )
    margin_x, margin_y = margin
    if direction in ('top-to-bottom', 'bottom-to-top'):
        _get_canvas = _get_canvas_vertical
        _render = _render_vertical
    else:
        _get_canvas = _get_canvas_horizontal
        _render = _render_horizontal
    canvas = _get_canvas(font, glyphs, margin_x, margin_y, adjust_bearings)
    canvas = _render(
        font, glyphs, canvas, margin_x, margin_y, align, adjust_bearings
    )
    return canvas

def _render_horizontal(
        font, glyphs, canvas, margin_x, margin_y, align, adjust_bearings
    ):
    """Render text horizontally."""
    # descent-line of the bottom-most row is at bottom margin
    # if a glyph extends below the descent line or left of the origin,
    # it may draw into the margin
    baseline = canvas.height - margin_y - font.ascent
    for glyph_row in glyphs:
        # x, y are relative to the left margin & baseline
        x = 0
        grid_x, grid_y = [], []
        for count, glyph in enumerate(glyph_row):
            # adjust origin for kerning
            if count:
                x += adjust_bearings
                x += prev.right_kerning.get_for_glyph(glyph)
                x += glyph.left_kerning.get_for_glyph(prev)
            prev = glyph
            # offset + (x, y) is the coordinate of glyph matrix origin
            grid_x.append(glyph.left_bearing + x)
            grid_y.append(glyph.shift_up + baseline)
            # advance origin to next glyph
            x += glyph.advance_width
        if align == 'right':
            start = canvas.width - margin_x - x
        else:
            start = margin_x
        for glyph, x, y in zip(glyph_row, grid_x, grid_y):
            # add ink, taking into account there may be ink already
            # in case of negative bearings
            canvas.blit(glyph.pixels, start + x, y)
        # move to next line
        baseline -= font.line_height
    return canvas

def _render_vertical(
        font, glyphs, canvas, margin_x, margin_y, align, adjust_bearings
    ):
    """Render text vertically."""
    # central axis (with leftward bias)
    baseline = font.line_width // 2
    # default is ttb right-to-left
    for glyph_row in glyphs:
        y = 0
        grid_x, grid_y = [], []
        for count, glyph in enumerate(glyph_row):
            # advance origin to next glyph
            if count:
                y -= adjust_bearings
            y -= glyph.advance_height
            grid_y.append(y + glyph.bottom_bearing)
            grid_x.append(
                baseline - glyph.width // 2 - glyph.shift_left
            )
        if align == 'bottom':
            start = margin_y - y
        else:
            start = canvas.height - margin_y
        for glyph, x, y in zip(glyph_row, grid_x, grid_y):
            # add ink, taking into account there may be ink already
            # in case of negative bearings
            canvas.blit(glyph.pixels, margin_x + x, start + y)
        # move to next line
        baseline += font.line_width
    return canvas

def _get_canvas_horizontal(font, glyphs, margin_x, margin_y, adjust_bearings):
    """Get the right size for vertical rendering."""
    # find required width - margins plus max row width
    if not glyphs:
        width = 0
    else:
        width = max(
            adjust_bearings * max(0, len(_row) - 1)
            + sum(_glyph.advance_width for _glyph in _row)
            for _row in glyphs
        )
    # find required height - margins plus line height for each row
    # descent-line of the bottom-most row is at bottom margin
    # ascent-line of top-most row is at top margin
    # if a glyph extends below the descent line or left of the origin,
    # it may draw into the margin
    height = font.pixel_size + font.line_height * (len(glyphs)-1)
    return _get_canvas(width, height, margin_x, margin_y)

def _get_canvas_vertical(font, glyphs, margin_x, margin_y, adjust_bearings):
    """Get the right size for vertical rendering."""
    # find required height - margins plus max column height
    height = 2 * margin_y
    if glyphs:
        height += max(
            adjust_bearings * max(0, len(_col) - 1)
            + sum(_glyph.advance_height + adjust_bearings for _glyph in _col)
            for _col in glyphs
        )
    width = 2 * margin_x + font.line_width * len(glyphs)
    return _get_canvas(width, height, margin_x, margin_y)

def _get_canvas(width, height, margin_x, margin_y):
    """Create canvas."""
    # margin in border colour
    canvas = Canvas.blank(2*margin_x + width, 2*margin_y + height, fill=-1)
    # regular background
    background = Canvas.blank(width, height, 0)
    # blit coordinate is bottom left, but our coordinates work from top left
    canvas.blit(background, margin_x, margin_y+height, operator=max)
    return canvas


def _get_direction(font, text, direction, align):
    """Get direction and alignment."""
    isstr = isinstance(text, str)
    if not direction:
        if isstr:
            direction = 'n'
        else:
            direction = font.direction or 'l'
    direction = direction.lower()
    force = direction.split(' ')[-1].startswith('f')
    if force:
        direction, _, _ = direction.rpartition(' ')
    # get line advance direction if given
    direction, _, line_direction = direction.partition(' ')
    try:
        direction = DIRECTIONS[direction[0]]
    except KeyError:
        raise ValueError(
            'Writing direction must be one of '
            + ', '.join(
                f'`{_k}`==`{_v}`'
                for _k, _v in DIRECTIONS.items()
            )
            + f'; not `{direction}`.'
        )
    if not line_direction or line_direction.startswith('n'):
        if direction == 'top-to-bottom':
            line_direction = 'r'
        else:
            line_direction = 't'
    try:
        line_direction = DIRECTIONS[line_direction[0]]
    except KeyError:
        raise ValueError(
            'Line direction must be one of '
            + ', '.join(
                f'`{_k}`==`{_v}`'
                for _k, _v in DIRECTIONS.items()
            )
            + f'; not `{direction}`.'
        )
    # determine base drection
    if isstr and not force:
        if direction in ('left-to-right', 'right-to-left'):
            # for Unicode text with horizontal directions, always use bidi algo
            # direction parameter is taken as *base direction* only
            base_direction = direction
            direction = 'normal'
        else:
            # use the class of the first directional character encountered
            base_level = get_base_level(text)
            base_direction = ('left-to-right', 'right-to-left')[base_level]
    else:
        if direction == 'normal':
            if isstr:
                raise ValueError(
                    f'Writing direction `{direction}` only supported for Unicode text.'
                )
            else:
                raise ValueError(
                    f'Writing direction `{direction}` not supported with `force`.'
                )
        base_direction = direction
    # determine alignment
    if align:
        align = ALIGNMENTS[align[0].lower()]
    if not align:
        if direction == 'left-to-right':
            align = 'left'
        elif direction == 'right-to-left':
            align = 'right'
        elif direction == 'normal':
            if base_direction == 'left-to-right':
                align = 'left'
            else:
                align = 'right'
        elif direction == 'bottom-to-top':
            align = 'bottom'
        else:
            align = 'top'
    return direction, line_direction, base_direction, align


def _get_text_glyphs(
        font, text,
        direction, line_direction, base_direction,
        missing='raise'
    ):
    """
    Get tuple of tuples of glyphs (by line) from str or bytes/codepoints input.
    Glyphs are reordered so that they can be rendered ltr ttb or ttb ltr
    """
    if isinstance(text, str) and direction not in ('top-to-bottom', 'bottom-to-top'):
        # reshape Arabic glyphs to contextual forms
        try:
            text = reshape(text)
        except ImportError as e:
            # check common Arabic range - is there anything to reshape?
            if any(ord(_c) in range(0x600, 0x700) for _c in text):
                logging.warning(e)
        # put characters in visual order instead of logical
        if direction == 'normal':
            # decide direction based on bidi algorithm
            base_dir = {
                'left-to-right': 'L',
                'right-to-left': 'R'
            }[base_direction]
            text = get_display(text, base_dir=base_dir)
    lines = text.splitlines()
    if direction in ('right-to-left', 'bottom-to-top'):
        # reverse glyph order for rendering
        lines = tuple(_row[::-1] for _row in lines)
    if line_direction in ('right-to-left', 'bottom-to-top'):
        # reverse line order for rendering
        lines = lines[::-1]
    return tuple(
        tuple(_iter_labels(font, _line, missing))
        for _line in lines
    )

def _iter_labels(font, text, missing='raise'):
    """Iterate over labels in text, yielding glyphs. text may be str or bytes."""
    if isinstance(text, str):
        font = font.label()
        labelset = font.get_chars()
        if not labelset:
            raise ValueError(
                'Cannot render string: no character labels in font.'
            )
        # split text into standard grapheme clusters
        text = tuple(grapheme_clusters(text))
        # find the longest *number of standard grapheme clusters* per label
        # this will often be 1, except when the font has defined e.g. Zł or Ft
        # as a char label for a single glyph
        max_length = max(len(tuple(grapheme_clusters(_c))) for _c in labelset)
        # we need to combine multiple elements back into str to match a glyph
        def labeltype(seq):
            return Char(''.join(seq))
    else:
        font = font.label(codepoint_from=font.encoding)
        labelset = font.get_codepoints()
        if not labelset:
            raise ValueError(
                'Cannot render bytes: no codepoint labels in font.'
            )
        labeltype = Codepoint
        max_length = max(len(_c) for _c in labelset)
    remaining = text
    while remaining:
        # try multibyte clusters first
        for try_len in range(max_length, 1, -1):
            try:
                # convert to explicit label type,
                # avoids matching tags as well as chars
                yield font.get_glyph(
                    labeltype(remaining[:try_len]), missing='raise'
                )
            except KeyError:
                pass
            else:
                remaining = remaining[try_len:]
                break
        else:
            yield font.get_glyph(labeltype(remaining[:1]), missing=missing)
            remaining = remaining[1:]
