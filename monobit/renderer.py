"""
monobit.renderer - render text to bitmaps using font

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .binary import ceildiv
from . import matrix

# matrix colours
# 0, 1 are background, foreground
# this allows us to use max() to combine the three in blit_matrix
_BORDER = -1


###################################################################################################
# text rendering

def render_text(
        font, text, ink='@', paper='-', *,
        margin=(0, 0), scale=(1, 1), rotate=0,
        missing='default'
    ):
    """Render text string to text bitmap."""
    return matrix.to_text(
        render(font, text, margin=margin, scale=scale, rotate=rotate, missing=missing),
        ink=ink, paper=paper
    )

def render_image(
        font, text, *,
        paper=(0, 0, 0), ink=(255, 255, 255),
        margin=(0, 0), scale=(1, 1), rotate=0,
        missing='default',
    ):
    """Render text to image."""
    return matrix.to_image(
        render(font, text, margin=margin, scale=scale, rotate=rotate, missing=missing),
        ink=ink, paper=paper
    )

def render(font, text, *, margin=(0, 0), scale=(1, 1), rotate=0, missing='default'):
    """Render text string to bitmap."""
    glyphs = font.get_glyphs(text, missing=missing)
    kernings = font.get_kernings(glyphs)
    margin_x, margin_y = margin
    canvas = _get_canvas(font, glyphs, margin_x, margin_y)
    # descent-line of the bottom-most row is at bottom margin
    # if a glyph extends below the descent line or left of the orgin, it may draw into the margin
    # raster_size.y moves from canvas origin to raster origin (bottom line)
    baseline = margin_y + font.ascent
    for glyph_row, kerning_row in zip(glyphs, kernings):
        # x, y are relative to the left margin & baseline
        x, y = 0, 0
        for glyph, kerning in zip(glyph_row, kerning_row):
            mx = glyph.as_matrix()
            if glyph.offset is not None:
                offset = glyph.offset
            else:
                offset = font.offset
            # apply pre-offset so that x, y is now the coordinate of glyph matrix origin
            x, y = x + offset.x, y + offset.y
            # grid_x, grid_y are canvas coordinates relative to top left of canvas
            # canvas y coordinate increases *downwards* from top of line
            grid_x = margin_x + x
            grid_y = baseline - y
            # add ink, taking into account there may be ink already in case of negative bearings
            matrix.blit(mx, canvas, grid_x, grid_y)
            # advance
            if glyph.advance is not None and glyph.offset is not None:
                advance = glyph.advance - glyph.offset.x
            else:
                advance = glyph.width + font.tracking
            x += advance + kerning
            # apply post-offset
            y -= offset.y
        # move to next line
        baseline += font.line_height
    scaled = matrix.scale(canvas, *scale)
    rotated = matrix.rotate(scaled, rotate)
    return rotated

def _get_canvas(font, glyphs, margin_x, margin_y):
    """Create canvas of the right size."""
    # find required width - margins plus max row width
    width = 2 * margin_x
    if glyphs:
        width += max(
            sum(
                (_glyph.offset.x if _glyph.offset is not None else font.offset.x)
                + (
                    _glyph.advance - _glyph.offset.x
                    if _glyph.advance is not None
                    else _glyph.width + font.tracking
                )
                for _glyph in _row
            )
            for _row in glyphs
        )
    # find required height - margins plus line height for each row
    # descent-line of the bottom-most row is at bottom margin
    # ascent-line of top-most row is at top margin
    # if a glyph extends below the descent line or left of the orgin, it may draw into the margin
    height = 2 * margin_y + font.pixel_size + font.line_height * (len(glyphs)-1)
    return matrix.create(width, height)



###################################################################################################
# glyph chart

def chart_image(
        font,
        columns=32, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=(32, 32, 32), paper=(0, 0, 0), ink=(255, 255, 255),
    ):
    """Dump font to image."""
    canvas = chart(font, columns, margin, padding, scale)
    return matrix.to_image(canvas, border=border, paper=paper, ink=ink)

def chart_text(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=' ', paper='-', ink='@',
    ):
    """Dump font to image."""
    canvas = chart(font, columns, margin, padding, scale)
    return matrix.to_text(canvas, border=border, paper=paper, ink=ink)


def chart(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
    ):
    """Dump font to image."""
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
    canvas = matrix.create(width, height, _BORDER)
    # output glyphs
    for ordinal, glyph in enumerate(font.glyphs):
        if not glyph.width or not glyph.height:
            continue
        row, col = divmod(ordinal, columns)
        mx = glyph.as_matrix()
        mx = matrix.scale(mx, scale_x, scale_y)
        left, bottom = margin_x + col*step_x, margin_y + (row+1)*step_y - padding_y
        matrix.blit(mx, canvas, left, bottom)
    return canvas
