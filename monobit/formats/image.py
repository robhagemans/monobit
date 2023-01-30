"""
monobit.formats.image - fonts stored in image files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from ..basetypes import Coord, RGB
from ..binary import ceildiv
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..chart import chart, traverse_chart


DEFAULT_IMAGE_FORMAT = 'png'


# available background policies
# -----------------------------
#
# most-common       use colour most commonly found in payload cells
# least-common      use colour least commonly found in payload cells
# brightest         use brightest colour, by sum of RGB values
# darkest           use darkest colour, by sum of RGB values
# top-left          use colour of top-left pixel in first cell


if Image:
    @loaders.register(
        'png', 'bmp', 'gif', 'tif', 'tiff',
        'ppm', 'pgm', 'pbm', 'pnm', 'webp',
        'pcx', 'tga', 'jpg', 'jpeg',
        magic=(
            # PNG
            b'\x89PNG\r\n\x1a\n',
            # BMP
            #b'BM',   # -- clash with bmfont b'BMF'
            # GIF
            b'GIF87a', b'GIF89a',
            # TIFF
            b'\x4D\x4D\x00\x2A', b'\x49\x49\x2A\x00'
            # PNM
            b'P1', b'P2', b'P3',
            # WebP
            b'RIFF',
            # PCX
            b'\n\x00', b'\n\x02', b'\n\x03', b'\n\x04', b'\n\x05',
            # JPEG
            b'\xFF\xD8\xFF',
        ),
        name='image',
    )
    def load_image(
            infile, where=None,
            cell:Coord=(8, 8),
            margin:Coord=(0, 0),
            padding:Coord=(0, 0),
            scale:Coord=(1, 1),
            table_size:Coord=(0,0),
            count:int=0,
            background:str='most-common',
            first_codepoint:int=0,
            order:str='row-major',
            direction:Coord=(1, -1),
        ):
        """
        Extract character-cell font from image.

        cell: size X,Y of character cell
        margin: number of pixels in X,Y direction around glyph chart
        padding: number of pixels in X,Y direction between glyph
        scale: number of pixels in X,Y direction per glyph bit
        table_size: number of glyphs in X, Y direction. 0 or negative means as much as fits on the axis.
        count: maximum number of glyphs to extract (within constraints of table_size). 0 or negative means extract all.
        background: determine background from "most-common", "least-common", "brightest", "darkest", "top-left" colour
        first_codepoint: codepoint value assigned to first glyph
        order: start with "r" for row-major order, "c" for column-major order
        direction: X, Y direction where +1, -1 (default) means left-to-right, top-to-bottom
        """
        width, height = cell
        scale_x, scale_y = scale
        padding_x, padding_y = padding
        margin_x, margin_y = margin
        # work out image geometry
        step_x = width * scale_x + padding_x
        step_y = height * scale_y + padding_y
        # maximum number of cells that fits
        img = Image.open(infile)
        img = img.convert('RGB')
        ncells_x, ncells_y = table_size
        if ncells_x <= 0:
            ncells_x = (img.width - margin_x) // step_x
        if ncells_y <= 0:
            ncells_y = (img.height - margin_y) // step_y
        traverse = traverse_chart(ncells_x, ncells_y, order, direction)
        # extract sub-images
        crops = [
            img.crop((
                margin_x + _col*step_x,
                img.height - (margin_y + _row*step_y + height * scale_y),
                margin_x + _col*step_x + width * scale_x,
                img.height - (margin_y + _row*step_y),
            ))
            for _row, _col in traverse
        ]
        if not crops:
            logging.error('Image too small; no characters found.')
            return Font()
        if count > 0:
            crops = crops[:count]
        # scale
        crops = [_crop.resize(cell) for _crop in crops]
        # get pixels
        crops = [list(_crop.getdata()) for _crop in crops]
        # check that cells are monochrome
        colourset = set.union(*(set(_data) for _data in crops))
        if len(colourset) > 2:
            logging.warning('Colour, greyscale and antialiased glyphs are not supported. ')
            logging.warning(
                f'More than two colours ({len(colourset)}) found in payload. '
                'All non-background colours will be converted to foreground.'
            )
        colourfreq = Counter(_c for _data in crops for _c in _data)
        brightness = sorted((sum(_v for _v in _c), _c) for _c in colourset)
        if background == 'most-common':
            # most common colour in image assumed to be background colour
            bg, _ = colourfreq.most_common(1)[0]
        elif background == 'least-common':
            # least common colour in image assumed to be background colour
            bg, _ = colourfreq.most_common()[-1]
        elif background == 'brightest':
            # brightest colour assumed to be background
            _, bg = brightness[-1]
        elif background == 'darkest':
            # darkest colour assumed to be background
            _, bg = brightness[0]
        elif background == 'top-left':
            # top-left pixel of first char assumed to be background colour
            bg = crops[0][0]
        # replace colours with characters
        crops = tuple(
            [_c != bg for _c in _cell]
            for _cell in crops
        )
        # reshape cells
        glyphs = [
            Glyph(tuple(
                _cell[_offs: _offs+width]
                for _offs in range(0, len(_cell), width)
            ), codepoint=_index)
            for _index, _cell in enumerate(crops, first_codepoint)
        ]
        # set code points
        return Font(glyphs)


    @savers.register(linked=load_image)
    def save_image(
            fonts, outfile, where=None, *,
            image_format:str='',
            columns:int=32,
            margin:Coord=(0, 0),
            padding:Coord=(0, 0),
            scale:Coord=(1, 1),
            order:str='row-major',
            direction:Coord=(1, -1),
            border:RGB=(32, 32, 32), paper:RGB=(0, 0, 0), ink:RGB=(255, 255, 255),
        ):
        """
        Export character-cell font to image.

        image_format: image file format
        columns: number of columns in glyph chart
        margin: number of pixels in X,Y direction around glyph chart
        padding: number of pixels in X,Y direction between glyph
        scale: number of pixels in X,Y direction per glyph bit
        border: border colour R,G,B 0--255
        order: start with "r" for row-major order, "c" for column-major order
        direction: X, Y direction where +1, -1 means left-to-right, top-to-bottom
        paper: background colour R,G,B 0--255
        ink: foreground colour R,G,B 0--255
        """
        if len(fonts) > 1:
            raise FileFormatError('Can only save one font to image file.')
        img = (
            chart(fonts[0], columns, margin, padding, scale, order, direction)
            .as_image(border=border, paper=paper, ink=ink)
        )
        try:
            img.save(outfile, format=image_format or Path(outfile).suffix[1:])
        except (KeyError, ValueError, TypeError):
            img.save(outfile, format=DEFAULT_IMAGE_FORMAT)
