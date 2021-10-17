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

def render_text(font, text, fore='@', back='-', *, margin=(0, 0), scale=(1, 1), missing='default'):
    """Render text string to text bitmap."""
    return to_text(
        render(font, text, margin=margin, scale=scale, missing=missing),
        fore=fore, back=back
    )

def render_image(
        font, text, *,
        back=(0, 0, 0), fore=(255, 255, 255),
        margin=(0, 0), scale=(1, 1),
        missing='default',
    ):
    """Render text to image."""
    return to_image(
        render(font, text, margin=margin, scale=scale, missing=missing),
        fore=fore, back=back
    )

def render(font, text, *, margin=(0, 0), scale=(1, 1), missing='default'):
    """Render text string to bitmap."""
    if isinstance(text, str):
        chars = [
            list(font._iter_string(_line))
            for _line in text.splitlines()
        ]
        glyphs = [
            [font.get_glyph(_c, missing=missing) for _c in _line]
            for _line in chars
        ]
    else:
        glyphs = [
            list(font._iter_codepoints(_line, missing=missing))
            for _line in text.splitlines()
        ]
        chars = [[_g.char for _g in _line] for _line in glyphs]
    # kerning currently only works for str
    if font.kerning:
        kerning = {
            (font.get_glyph(_key[0]).char, font.get_glyph(_key[1]).char): _value
            for _key, _value in font.kerning.items()
        }
        kernings = [
            [
                kerning.get((_char, _next), 0)
                for _char, _next in zip(_line[:-1], _line[1:])
            ] + [0]
            for _line in chars
        ]
    else:
        kernings = [[0] * len(_line) for _line in glyphs]
    # determine dimensions
    margin_x, margin_y = margin
    if not glyphs:
        width = 2 * margin_x
    else:
        width = 2 * margin_x + max(
            (
                sum(_glyph.width for _glyph in _row)
                + (font.offset.x + font.tracking) * len(_row)
            )
            for _row in glyphs
        )
    line_height = font.max_raster_size.y + font.leading
    height = 2 * margin_y + line_height * len(glyphs)
    canvas = _create_matrix(width, height)
    # get to initial origin
    grid_top = margin_y
    for row, kernrow in zip(glyphs, kernings):
        x, y = 0, 0
        for glyph, kerning in zip(row, kernrow):
            matrix = glyph.as_matrix()
            # apply pre-offset so that x,y is logical coordinate of grid origin
            x, y = x + font.offset.x, y + font.offset.y
            # grid coordinates of grid origin
            grid_x, grid_y = margin_x + x, grid_top + font.ascent - y
            # add ink, taking into account there may be ink already in case of negative bearings
            _blit_matrix(matrix, canvas, grid_x, grid_y)
            # advance
            x += glyph.width
            # apply post-offset
            x, y = x + font.tracking + kerning, y - font.offset.y
        grid_top += line_height
    scaled = _scale_matrix(canvas, *scale)
    return scaled


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
        border=(32, 32, 32), back=(0, 0, 0), fore=(255, 255, 255),
    ):
    """Dump font to image."""
    canvas = chart(font, columns, margin, padding, scale)
    return to_image(canvas, border, back, fore)

def chart_text(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=' ', back='-', fore='@',
    ):
    """Dump font to image."""
    canvas = chart(font, columns, margin, padding, scale)
    return to_text(canvas, border=border, back=back, fore=fore)


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
