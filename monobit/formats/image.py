"""
monobit.image - fonts stored in image files

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from ..scripting import pair, rgb
from ..base.binary import ceildiv
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..renderer import chart_image


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
        name='Bitmap Image',
    )
    def load_image(
            infile, where=None,
            cell:pair=(8, 8),
            margin:pair=(0, 0),
            padding:pair=(0, 0),
            scale:pair=(1, 1),
            # 0 or negative indicates 'use all chars'
            numchars:int=0,
            background:str='most-common'
        ):
        """
        Extract character-cell font from image.

        cell: size X,Y of character cell
        margin: number of pixels in X,Y direction around glyph chart
        padding: number of pixels in X,Y direction between glyph
        scale: number of pixels in X,Y direction per glyph bit
        numchars: number of glyphs to extract
        background: determine background from "most-common", "least-common", "brightest", "darkest", "top-left" colour
        """
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
        if not crops:
            logging.error('Image too small; no characters found.')
            return Font()
        # scale
        crops = [_crop.resize(cell) for _crop in crops]
        # get pixels
        crops = [list(_crop.getdata()) for _crop in crops]
        # restrict to requested number of characters
        if numchars and numchars > 0:
            crops = crops[:numchars]
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
            ))
            for _cell in crops
        ]
        # set code points
        return Font(glyphs)


    @savers.register(linked=load_image)
    def save_image(
            fonts, outfile, where=None,
            format:str='',
            columns:int=32,
            margin:pair=(0, 0),
            padding:pair=(0, 0),
            scale:pair=(1, 1),
            border:rgb=(32, 32, 32), paper:rgb=(0, 0, 0), ink:rgb=(255, 255, 255),
        ):
        """
        Export character-cell font to image.

        format: image file format
        columns: number of columns in glyph chart
        margin: number of pixels in X,Y direction around glyph chart
        padding: number of pixels in X,Y direction between glyph
        scale: number of pixels in X,Y direction per glyph bit
        border: border colour R,G,B 0--255
        paper: background colour R,G,B 0--255
        ink: foreground colour R,G,B 0--255
        """
        if len(fonts) > 1:
            raise FileFormatError('Can only save one font to image file.')
        img = chart_image(fonts[0], columns, margin, padding, scale, border, paper, ink)
        try:
            img.save(outfile, format=format or Path(outfile).suffix[1:])
        except (KeyError, ValueError, TypeError):
            img.save(outfile, format=DEFAULT_IMAGE_FORMAT)
