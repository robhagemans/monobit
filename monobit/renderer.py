"""
monobit.renderer - render text to bitmaps using font

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base.text import to_text

try:
    from PIL import Image
except ImportError:
    Image = None


def render(font, text, fore=1, back=0, *, margin=(0, 0), scale=(1, 1), missing='default'):
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
    line_output = [
        [0 for _ in range(width)]
        for _ in range(height)
    ]
    # get to initial origin
    grid_top = margin_y
    for row, kernrow in zip(glyphs, kernings):
        x, y = 0, 0
        for glyph, kerning in zip(row, kernrow):
            matrix = glyph.as_matrix(1, 0)
            # apply pre-offset so that x,y is logical coordinate of grid origin
            x, y = x + font.offset.x, y + font.offset.y
            # grid coordinates of grid origin
            grid_x, grid_y = margin_x + x, grid_top + font.ascent - y
            # add ink, taking into account there may be ink already in case of negative bearings
            for work_y in range(glyph.height):
                y_index = grid_y - work_y - 1
                if 0 <= y_index < height:
                    row = line_output[y_index]
                    for work_x, ink in enumerate(matrix[glyph.height - work_y - 1]):
                        if 0 <= grid_x + work_x < width:
                            row[grid_x + work_x] |= ink
            # advance
            x += glyph.width
            # apply post-offset
            x, y = x + font.tracking + kerning, y - font.offset.y
        grid_top += line_height
    output = []
    output.extend(line_output)
    scale_x, scale_y = scale
    output = tuple(
        tuple((fore if _item else back) for _item in _row for _ in range(scale_x))
        for _row in output for _ in range(scale_y)
    )
    return output


def render_text(font, text, fore='@', back='-', *, margin=(0, 0), scale=(1, 1), missing='default'):
    """Render text string to text bitmap."""
    return to_text(render(font, text, fore, back, margin=margin, scale=scale, missing=missing))


def render_image(
        font, text, *,
        back=(0, 0, 0), fore=(255, 255, 255),
        margin=(0, 0), scale=(1, 1),
        missing='default',
        filename=None,
    ):
    """Render text to image."""
    if not Image:
        raise ImportError('Rendering to image requires PIL module.')
    grid = render(
        font, text, fore, back, margin=margin, scale=scale, missing=missing
    )
    if not grid:
        return
    width, height = len(grid[0]), len(grid)
    img = Image.new('RGB', (width, height), back)
    data = [_c for _row in grid for _c in _row]
    img.putdata(data)
    if filename:
        img.save(filename)
    else:
        img.show()
