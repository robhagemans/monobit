"""
monobit.renderer - render text to bitmaps using font

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base.text import to_text
from .base.binary import ceildiv
from .base.image import to_image


# matrix colours
# 0, 1 are background, foreground
# this allows us to use max() to combine the three in blit_matrix
_BORDER = -1


###################################################################################################
# text rendering

def render_text(font, text, ink='@', paper='-', *, margin=(0, 0), scale=(1, 1), missing='default'):
    """Render text string to text bitmap."""
    return to_text(
        render(font, text, margin=margin, scale=scale, missing=missing),
        ink=ink, paper=paper
    )

def render_image(
        font, text, *,
        paper=(0, 0, 0), ink=(255, 255, 255),
        margin=(0, 0), scale=(1, 1),
        missing='default',
    ):
    """Render text to image."""
    return to_image(
        render(font, text, margin=margin, scale=scale, missing=missing),
        ink=ink, paper=paper
    )

def render(font, text, *, margin=(0, 0), scale=(1, 1), missing='default'):
    """Render text string to bitmap."""
    glyphs = font.get_glyphs(text, missing=missing)
    kernings = font.get_kernings(glyphs)
    margin_x, margin_y = margin
    canvas = _get_canvas(font, glyphs, margin_x, margin_y)
    # top of first line starts at the margin
    top_line = margin_y
    for glyph_row, kerning_row in zip(glyphs, kernings):
        # get to initial glyph origin
        x, y = 0, 0
        for glyph, kerning in zip(glyph_row, kerning_row):
            matrix = glyph.as_matrix()
            # apply pre-offset so that x,y is logical coordinate of raster origin
            x, y = x + font.offset.x, y + font.offset.y
            # canvas coordinates of raster origin
            grid_x = margin_x + x
            # canvas y coordinate increases *downwards* from top of line
            grid_y = top_line + font.ascent - y
            # add ink, taking into account there may be ink already in case of negative bearings
            _blit_matrix(matrix, canvas, grid_x, grid_y)
            # advance
            x += glyph.width + font.tracking + kerning
            # apply post-offset
            y -= font.offset.y
        # move to next line
        top_line += font.line_height
    scaled = _scale_matrix(canvas, *scale)
    return scaled

def _get_canvas(font, glyphs, margin_x, margin_y):
    """Create canvas of the right size."""
    # find required width - margins plus max row width
    width = 2 * margin_x
    if glyphs:
        width += max(
            (
                sum(_glyph.width for _glyph in _row)
                + (font.offset.x + font.tracking) * len(_row)
            )
            for _row in glyphs
        )
    # find required height - margins plus line height for each row
    height = 2 * margin_y + font.line_height * len(glyphs)
    return _create_matrix(width, height)


###################################################################################################
# matrix operations

def _create_matrix(width, height, fill=0):
    """Create a matrix in list format."""
    return [
        [fill for _ in range(width)]
        for _ in range(height)
    ]

def _scale_matrix(matrix, scale_x, scale_y):
    """Scale a matrix in list format."""
    return [
        [_item  for _item in _row for _ in range(scale_x)]
        for _row in matrix for _ in range(scale_y)
    ]

def _blit_matrix(matrix, canvas, grid_x, grid_y, operator=max):
    """Draw a matrix onto a canvas (leaving exising ink in place, depending on operator)."""
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


###################################################################################################
# glyph chart

def chart_image(
        font,
        columns=32, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=(32, 32, 32), paper=(0, 0, 0), ink=(255, 255, 255),
    ):
    """Dump font to image."""
    canvas = chart(font, columns, margin, padding, scale)
    return to_image(canvas, border=border, paper=paper, ink=ink)

def chart_text(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=' ', paper='-', ink='@',
    ):
    """Dump font to image."""
    canvas = chart(font, columns, margin, padding, scale)
    return to_text(canvas, border=border, paper=paper, ink=ink)


def chart(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
    ):
    """Dump font to image."""
    scale_x, scale_y = scale
    padding_x, padding_y = padding
    margin_x, margin_y = margin
    # work out image geometry
    step_x = font.max_raster_size.x * scale_x + padding_x
    step_y = font.max_raster_size.y * scale_y + padding_y
    rows = ceildiv(len(font.glyphs), columns)
    # determine image geometry
    width = columns * step_x + 2 * margin_x - padding_x
    height = rows * step_y + 2 * margin_y - padding_y
    canvas = _create_matrix(width, height, _BORDER)
    # output glyphs
    for ordinal, glyph in enumerate(font.glyphs):
        if not glyph.width or not glyph.height:
            continue
        row, col = divmod(ordinal, columns)
        matrix = glyph.as_matrix()
        matrix = _scale_matrix(matrix, scale_x, scale_y)
        left, bottom = margin_x + col*step_x, margin_y + (row+1)*step_y - padding_y
        _blit_matrix(matrix, canvas, left, bottom)
    return canvas
