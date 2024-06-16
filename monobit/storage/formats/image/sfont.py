"""
monobit.storage.formats.sfont - SDL SFont format

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import groupby

try:
    from PIL import Image
except ImportError:
    Image = None

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph
from monobit.render import GlyphMap

# see https://github.com/karlb/sfont


_INDICATOR_RGBA = (255, 0, 255, 255)
_INDICATOR_RGB = (255, 0, 255)
_SFONT_RANGE = range(33, 127)


if Image:

    @loaders.register(
        name='sfont',
    )
    def load_sfont(instream, *, flatten:bool=False):
        """
        Load font from SFont file.

        flatten: interpret all non-background colours as ink. If false (default), more than 2 colours will raise an error.
        """
        image = Image.open(instream).convert('RGB')
        glyphs = []
        indicator = tuple(image.crop((0, 0, image.width, 1)).getdata())
        if len(set(indicator)) != 2:
            raise FileFormatError('Not an SFont image: missing indicator bar.')
        for rgb in set(indicator):
            if not isinstance(rgb, tuple):
                raise FileFormatError('Not an SFont image: must be RGB or RGBA.')
            if rgb != _INDICATOR_RGB and rgb != _INDICATOR_RGBA:
                background = rgb
        spritesheet = image.crop((0, 1, image.width, image.height))
        if len(set(spritesheet.getdata())) > 2:
            msg = (
                'Colour and anti-aliasing not supported. '
                'All non-background pixels will be interpreted as inked.'
            )
            if flatten:
                logging.warning(msg)
            else:
                raise FileFormatError(msg)
        groups = tuple(
            (_clr, len(tuple(_g)))
            for _clr, _g in groupby(indicator)
        )
        x = 0
        glyphs = []
        left = 0
        for i, (clr, length) in enumerate(groups):
            if clr in (_INDICATOR_RGB, _INDICATOR_RGBA):
                if i == 0:
                    left = length
                else:
                    if i == len(groups):
                        right = length
                    else:
                        right = length // 2
                    crop = spritesheet.crop(
                        (x, 0, x + left+width+right, spritesheet.height)
                    )
                    glyphs.append(
                        Glyph.from_vector(
                            tuple(crop.getdata()),
                            stride=crop.width, _1=background,
                            codepoint=min(_SFONT_RANGE) + i,
                            left_bearing=-left,
                            right_bearing=-right,
                        ).invert()
                    )
                    x += left+width+right + length%2
                    left = right
            else:
                width = length
        return Font(glyphs)
