"""
monobit.image - fonts stored in image files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

try:
    from PIL import Image
except ImportError:
    Image = None
from .binary import ceildiv
from .typeface import Typeface
from .font import Font
from .glyph import Glyph


if Image:
    @Typeface.loads('png', 'bmp', 'gif', 'image', name='Bitmap Image', encoding=None)
    def load(infile, cell=(8, 8), margin=(0, 0), padding=(0, 0), scale=(1, 1)):
        """Import font from image."""
        width, height = cell
        scale_x, scale_y = scale
        padding_x, padding_y = padding
        margin_x, margin_y = margin
        # work out image geometry
        step_x = width * scale_x + padding_x
        step_y = height *scale_y + padding_y
        # maximum number of cells that fits
        img = Image.open(infile)
        ncells_x = (img.width - margin_x) // step_x
        ncells_y = (img.height - margin_y) // step_y
        # extract sub-images
        # assume row-major left-to-right top-to-bottom
        crops = [
            img.crop((
                margin_x + _col*step_x,
                margin_y + _row*step_y,
                margin_x + _col*step_x + width * scale_x,
                margin_y + _row*step_y + height * scale_y,
            ))
            for _row in range(ncells_y)
            for _col in range(ncells_x)
        ]
        # scale
        crops = [_crop.resize(cell) for _crop in crops]
        # get pixels
        crops = [list(_crop.getdata()) for _crop in crops]
        # check that cells are monochrome
        colourset = set.union(*(set(_data) for _data in crops))
        if len(colourset) > 2:
            raise ValueError('Colour, greyscale and antialiased glyphs not supported.')
        # replace colours with characters
        # top-left pixel of first char assumed to be background colour
        bg = crops[0][0]
        crops = tuple(
            [_c != bg for _c in _cell]
            for _cell in crops
        )
        # reshape cells
        glyphs = [
            Glyph(tuple(
                _cell[_offs: _offs+width]
                for _offs in range(0, len(_cell), width)
            ))
            for _cell in crops
        ]
        # set code points
        return Typeface([Font(glyphs)])


    @Typeface.saves('png', 'bmp', 'gif', 'image', encoding=None, multi=False)
    def save(
            font, outfile, format=None,
            columns=32, margin=(0, 0), padding=(0, 0), scale=(1, 1),
            border=(32, 32, 32), back=(0, 0, 0), fore=(255, 255, 255),
        ):
        """Export font to image."""
        img = _to_image(font, columns, margin, padding, scale, border, back, fore)
        img.save(outfile, format)
        return font


def _to_image(
        font,
        columns=32, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=(32, 32, 32), back=(0, 0, 0), fore=(255, 255, 255),
    ):
    """Dump font to image."""
    scale_x, scale_y = scale
    padding_x, padding_y = padding
    margin_x, margin_y = margin
    # work out image geometry
    step_x = font.bounding_box.x * scale_x + padding_x
    step_y = font.bounding_box.y * scale_y + padding_y
    rows = ceildiv(font.max_ordinal, columns)
    # determine image geometry
    width = columns * step_x + 2 * margin_x - padding_x
    height = rows * step_y + 2 * margin_y - padding_y
    img = Image.new('RGB', (width, height), border)
    # output glyphs
    for row in range(rows):
        for col in range(columns):
            ordinal = row * columns + col
            try:
                glyph = font.get_glyph(ordinal)
            except KeyError:
                continue
            if not glyph.width or not glyph.height:
                continue
            charimg = Image.new('RGB', (glyph.width, glyph.height))
            data = glyph.as_tuple(fore, back)
            charimg.putdata(data)
            charimg = charimg.resize((charimg.width * scale_x, charimg.height * scale_y))
            lefttop = (margin_x + col*step_x, margin_y + row*step_y)
            img.paste(charimg, lefttop)
    return img

def show(
        typeface,
        columns=32, margin=(0, 0), padding=(0, 0), scale=(1, 1),
        border=(32, 32, 32), back=(0, 0, 0), fore=(255, 255, 255),
    ):
    """Show font as image."""
    for font in typeface._fonts:
        img = _to_image(font, columns, margin, padding, scale, border, back, fore)
        img.show()
    return typeface
