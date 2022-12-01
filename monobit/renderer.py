"""
monobit.renderer - render text to bitmaps using font

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

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


# matrix colours
# 0, 1 are background, foreground
# this allows us to use max() to combine the three in blit_matrix
_BORDER = -1


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



class blockstr(str):
    """str that is shown as block text in interactive session."""

    def __repr__(self):
        return f'"""\\\n{self}"""'


###############################################################################
# canvas operations

def create_canvas(width, height, fill=0):
    """Create a matrix in list format."""
    return [
        [fill for _ in range(width)]
        for _ in range(height)
    ]

def scale_canvas(matrix, scale_x, scale_y):
    """Scale a matrix in list format."""
    return [
        [_item  for _item in _row for _ in range(scale_x)]
        for _row in matrix for _ in range(scale_y)
    ]

def rotate_canvas(matrix, quarter_turns=1):
    """Scale a matrix in list format."""
    for turn in range(quarter_turns):
        matrix = mirror_canvas(transpose_canvas(matrix))
    return matrix

def transpose_canvas(matrix):
    """Transpose a matrix."""
    return list(zip(*matrix))

def mirror_canvas(matrix):
    """Mirror a matrix."""
    return [_row[::-1] for _row in matrix]


def blit(matrix, canvas, grid_x, grid_y, operator=max):
    """
    Draw a matrix onto a canvas
    (leaving exising ink in place, depending on operator).
    """
    if not matrix or not canvas:
        return canvas
    matrix_height = len(matrix)
    canvas_height = len(canvas)
    canvas_width = len(canvas[0])
    for work_y in range(matrix_height):
        y_index = grid_y - work_y - 1
        if 0 <= y_index < canvas_height:
            row = canvas[y_index]
            for work_x, ink in enumerate(matrix[matrix_height - work_y - 1]):
                if 0 <= grid_x + work_x < canvas_width:
                    row[grid_x + work_x] = operator(ink, row[grid_x + work_x])
    return canvas


def to_image(matrix, border=(0, 0, 0), paper=(0, 0, 0), ink=(255, 255, 255)):
    """Convert matrix to image."""
    if not Image:
        raise ImportError('Rendering to image requires PIL module.')
    height = len(matrix)
    if height:
        width = len(matrix[0])
    else:
        width = 0
    img = Image.new('RGB', (width, height), border)
    img.putdata([
        {-1: border, 0: paper, 1: ink}[_pix]
        for _row in matrix for _pix in _row
    ])
    return img

def to_text(matrix, *, border='.', paper='.', ink='@', line_break='\n'):
    """Convert matrix to text."""
    colourdict = {-1: border, 0: paper, 1: ink}
    return blockstr(line_break.join(
        ''.join(colourdict[_pix] for _pix in _row)
        for _row in matrix
    ))


###############################################################################
# text rendering

def render(
        font, text, *, margin=(0, 0), scale=(1, 1), rotate=0,
        direction='', align='',
        missing='default'
    ):
    """Render text string to bitmap."""
    direction, line_direction, base_direction, align = _get_direction(
        font, text, direction, align
    )
    # get glyphs for rendering
    font = font._privatise_glyph_metrics()
    glyphs = _get_text_glyphs(
        font, text, direction, line_direction, base_direction, missing
    )
    margin_x, margin_y = margin
    if direction in ('top-to-bottom', 'bottom-to-top'):
        canvas = _get_canvas_vertical(font, glyphs, margin_x, margin_y)
        canvas = _render_vertical(font, glyphs, canvas, margin_x, margin_y, align)
    else:
        canvas = _get_canvas_horizontal(font, glyphs, margin_x, margin_y)
        canvas = _render_horizontal(font, glyphs, canvas, margin_x, margin_y, align)
    scaled = scale_canvas(canvas, *scale)
    rotated = rotate_canvas(scaled, rotate)
    return rotated

def _render_horizontal(font, glyphs, canvas, margin_x, margin_y, align):
    # descent-line of the bottom-most row is at bottom margin
    # if a glyph extends below the descent line or left of the origin,
    # it may draw into the margin
    # raster_size.y moves from canvas origin to raster origin (bottom line)
    baseline = font.ascent
    for glyph_row in glyphs:
        # x, y are relative to the left margin & baseline
        x = 0
        prev = font.get_empty_glyph()
        grid_x, grid_y = [], []
        for glyph in glyph_row:
            # adjust origin for kerning
            x += prev.right_kerning.get_for_glyph(glyph)
            x += glyph.left_kerning.get_for_glyph(prev)
            prev = glyph
            # offset + (x, y) is the coordinate of glyph matrix origin
            # grid_x, grid_y are canvas coordinates relative to top left of canvas
            # canvas y coordinate increases *downwards* from top of line
            grid_x.append(glyph.left_bearing + x)
            grid_y.append(baseline - glyph.shift_up)
            # advance origin to next glyph
            x += glyph.advance_width
        if align == 'right':
            start = len(canvas[0]) - margin_x - x
        else:
            start = margin_x
        for glyph, x, y in zip(glyph_row, grid_x, grid_y):
            # add ink, taking into account there may be ink already
            # in case of negative bearings
            blit(
                glyph.as_matrix(), canvas,
                start + x, margin_y + y
            )
        # move to next line
        baseline += font.line_height
    return canvas

def _render_vertical(font, glyphs, canvas, margin_x, margin_y, align):
    # central axis (with leftward bias)
    baseline = font.line_width // 2
    # default is ttb right-to-left
    for glyph_row in glyphs:
        y = 0
        grid_x, grid_y = [], []
        for glyph in glyph_row:
            # advance origin to next glyph
            y += glyph.advance_height
            grid_y.append(y - glyph.bottom_bearing)
            grid_x.append(
                baseline - glyph.width // 2 - glyph.shift_left
            )
        if align == 'bottom':
            start = len(canvas) - margin_y - y
        else:
            start = margin_y

        for glyph, x, y in zip(glyph_row, grid_x, grid_y):
            # add ink, taking into account there may be ink already
            # in case of negative bearings
            blit(
                glyph.as_matrix(), canvas,
                margin_x + x, start + y
            )
        # move to next line
        baseline += font.line_width
    return canvas

def _get_canvas_horizontal(font, glyphs, margin_x, margin_y):
    """Create canvas of the right size."""
    # find required width - margins plus max row width
    width = 2 * margin_x
    if glyphs:
        width += max(
            sum(_glyph.advance_width for _glyph in _row)
            for _row in glyphs
        )
    # find required height - margins plus line height for each row
    # descent-line of the bottom-most row is at bottom margin
    # ascent-line of top-most row is at top margin
    # if a glyph extends below the descent line or left of the origin,
    # it may draw into the margin
    height = 2 * margin_y + font.pixel_size + font.line_height * (len(glyphs)-1)
    return create_canvas(width, height, _BORDER)

def _get_canvas_vertical(font, glyphs, margin_x, margin_y):
    """Create canvas of the right size."""
    # find required height - margins plus max column height
    height = 2 * margin_y
    if glyphs:
        height += max(
            sum(_glyph.advance_height for _glyph in _col)
            for _col in glyphs
        )
    width = 2 * margin_x + font.line_width * len(glyphs)
    return create_canvas(width, height, _BORDER)


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
        labelset = font.get_chars()
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
        labelset = font.get_codepoints()
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


###############################################################################
# glyph chart

def traverse_chart(columns, rows, order, direction):
    """Traverse a glyph chart in the specified order and directions."""
    dir_x, dir_y = direction
    x_traverse = range(columns)
    if dir_x < 0:
        x_traverse = reversed(x_traverse)
    y_traverse = range(rows)
    if dir_y < 0:
        y_traverse = reversed(y_traverse)
    if order.startswith('r'):
        # row-major left-to-right top-to-bottom
        x_traverse = list(x_traverse)
        return (
            (_row, _col)
            for _row in y_traverse
            for _col in x_traverse
        )
    elif order.startswith('c'):
        # row-major top-to-bottom left-to-right
        y_traverse = list(y_traverse)
        return (
            (_row, _col)
            for _col in x_traverse
            for _row in y_traverse
        )
    else:
        raise ValueError(
            f'order should start with one of `r`, `c`, not `{order}`.'
        )

def chart(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        order='row-major', direction=(1, 1),
    ):
    """Create font chart matrix."""
    scale_x, scale_y = scale
    padding_x, padding_y = padding
    margin_x, margin_y = margin
    # work out image geometry
    step_x = font.raster_size.x * scale_x + padding_x
    step_y = font.raster_size.y * scale_y + padding_y
    rows = ceildiv(len(font.glyphs), columns)
    # determine image geometry
    width = columns * step_x + 2 * margin_x - padding_x
    height = rows * step_y + 2 * margin_y - padding_y
    canvas = create_canvas(width, height, _BORDER)
    # output glyphs
    traverse = traverse_chart(columns, rows, order, direction)
    for glyph, pos in zip(font.glyphs, traverse):
        if not glyph.width or not glyph.height:
            continue
        row, col = pos
        mx = glyph.as_matrix()
        mx = scale_canvas(mx, scale_x, scale_y)
        left = margin_x + col*step_x + glyph.left_bearing
        bottom = margin_y + (row+1)*step_y - padding_y - glyph.shift_up
        blit(mx, canvas, left, bottom)
    return canvas
