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

_INDICATOR_RGB = (255, 0, 255, 255)

# see https://github.com/karlb/sfont

if Image:

    @loaders.register(
        name='sfont',
    )
    def load_sfont(instream):
        """Load font from SFont file."""
        image = Image.open(instream)
        glyphs = []
        indicator = tuple(image.crop((0, 0, image.width, 1)).getdata())
        if len(set(indicator)) != 2:
            raise FileFormatError('Not an SFont image: missing indicator bar.')
        for rgb in set(indicator):
            if rgb != _INDICATOR_RGB:
                background = rgb
        spritesheet = image.crop((0, 1, image.width, image.height))
        if len(set(spritesheet.getdata())) > 2:
            logging.warning(
                'Colour and anti-aliasing not supported. '
                'All non-background pixels will be interpreted as inked.'
            )
        groups = tuple(
            (_clr, len(tuple(_g)))
            for _clr, _g in groupby(indicator)
        )
        x = 0
        glyphs = []
        for i, (clr, length) in enumerate(groups):
            if clr == _INDICATOR_RGB:
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
                            codepoint=33 + i,
                            left_bearing=-left,
                            right_bearing=-right,
                        ).invert()
                    )
                    x += left+width+right + length%2
                    left = right
            else:
                width = length
        return Font(glyphs)
