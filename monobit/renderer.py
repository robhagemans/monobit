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
    glyphs = _get_text_glyphs(font, text, missing=missing)
    margin_x, margin_y = margin
    canvas = _get_canvas(font, glyphs, margin_x, margin_y)
    # descent-line of the bottom-most row is at bottom margin
    # if a glyph extends below the descent line or left of the orgin, it may draw into the margin
    # raster_size.y moves from canvas origin to raster origin (bottom line)
    baseline = margin_y + font.ascent
    for glyph_row in glyphs:
        # x, y are relative to the left margin & baseline
        x, y = 0, 0
        prev = font.get_empty_glyph()
        for glyph in glyph_row:
            # adjust origin for kerning
            x += prev.kern_to.get_for_glyph(glyph)
            prev = glyph
            # offset + (x, y) is the coordinate of glyph matrix origin
            # grid_x, grid_y are canvas coordinates relative to top left of canvas
            # canvas y coordinate increases *downwards* from top of line
            offset = font.offset + glyph.offset
            grid_x = margin_x + (offset.x + x)
            grid_y = baseline - (offset.y + y)
            # add ink, taking into account there may be ink already in case of negative bearings
            matrix.blit(glyph.as_matrix(), canvas, grid_x, grid_y)
            # advance origin to next glyph
            x += font.offset.x + glyph.advance + font.tracking
        # move to next line
        baseline += font.line_spacing
    scaled = matrix.scale(canvas, *scale)
    rotated = matrix.rotate(scaled, rotate)
    return rotated

def _get_canvas(font, glyphs, margin_x, margin_y):
    """Create canvas of the right size."""
    # find required width - margins plus max row width
    width = 2 * margin_x
    if glyphs:
        width += max(
            sum(font.offset.x + _glyph.advance + font.tracking for _glyph in _row)
            for _row in glyphs
        )
    # find required height - margins plus line height for each row
    # descent-line of the bottom-most row is at bottom margin
    # ascent-line of top-most row is at top margin
    # if a glyph extends below the descent line or left of the origin, it may draw into the margin
    height = 2 * margin_y + font.pixel_size + font.line_spacing * (len(glyphs)-1)
    return matrix.create(width, height)

def _get_text_glyphs(font, text, missing='raise'):
    """Get tuple of tuples of glyphs (by line) from str or bytes/codepoints input."""
    if isinstance(text, str):
        max_length = max(len(_c) for _c in font.get_chars())
        type_conv = str
    else:
        max_length = max(len(_cp) for _cp in font.get_codepoints())
        type_conv = tuple
    return tuple(
        tuple(_iter_labels(font, type_conv(_line), max_length, missing))
        for _line in text.splitlines()
    )

def _iter_labels(font, labels, max_length, missing='raise'):
    """Iterate over labels, yielding glyphs."""
    remaining = labels
    while remaining:
        # try multibyte clusters first
        for try_len in range(max_length, 1, -1):
            try:
                yield font.get_glyph(key=remaining[:try_len], missing='raise')
            except KeyError:
                pass
            else:
                remaining = remaining[try_len:]
                break
        else:
            yield font.get_glyph(key=remaining[:1], missing=missing)
            remaining = remaining[1:]



###################################################################################################
# glyph chart

def chart_image(
        font,
        columns=32, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=(32, 32, 32), paper=(0, 0, 0), ink=(255, 255, 255),
    ):
    """Create font chart as image."""
    canvas = chart(font, columns, margin, padding, scale)
    return matrix.to_image(canvas, border=border, paper=paper, ink=ink)

def chart_text(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=' ', paper='-', ink='@',
    ):
    """Create font chart as text."""
    canvas = chart(font, columns, margin, padding, scale)
    return matrix.to_text(canvas, border=border, paper=paper, ink=ink)


def chart(
        font,
        columns=16, margin=(0, 0), padding=(0, 0), scale=(1, 1),
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
    canvas = matrix.create(width, height, _BORDER)
    # output glyphs
    for ordinal, glyph in enumerate(font.glyphs):
        if not glyph.width or not glyph.height:
            continue
        row, col = divmod(ordinal, columns)
        mx = glyph.as_matrix()
        mx = matrix.scale(mx, scale_x, scale_y)
        left = margin_x + col*step_x + glyph.offset.x
        bottom = margin_y + (row+1)*step_y - padding_y - glyph.offset.y
        matrix.blit(mx, canvas, left, bottom)
    return canvas
