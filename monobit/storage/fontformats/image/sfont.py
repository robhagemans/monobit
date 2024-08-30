"""
monobit.storage.fontformats.sfont - SDL SFont format

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import groupby

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.storage import loaders, savers
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Font, Glyph
from monobit.render import GlyphMap

from monobit.storage.utils.limitations import ensure_single
from .image import identify_inklevels

# see https://github.com/karlb/sfont


# _INDICATOR_RGBA = (255, 0, 255, 255)
_INDICATOR_RGB = (255, 0, 255)
_SFONT_RANGE = range(33, 127)


if Image:

    @loaders.register(
        name='sfont',
    )
    def load_sfont(instream):
        """
        Load font from SFont file.
        """
        image = Image.open(instream).convert('RGB')
        glyphs = []
        indicator = tuple(image.crop((0, 0, image.width, 1)).getdata())
        if len(set(indicator)) != 2:
            raise FileFormatError('Not an SFont image: missing indicator bar.')
        # we converted to RGB so we don't need to consider RGBA
        for rgb in set(indicator):
            if rgb != _INDICATOR_RGB:
                background = rgb
                break
        spritesheet = image.crop((0, 1, image.width, image.height))
        colours = spritesheet.getdata()
        # identify colour mode
        inklevels = identify_inklevels(colours, background)
        # find indicator lengths
        groups = tuple(
            (_clr, len(tuple(_g)))
            for _clr, _g in groupby(indicator)
        )
        # extract glyphs
        x = 0
        glyphs = []
        left = 0
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
                            stride=crop.width,
                            inklevels=inklevels,
                            codepoint=min(_SFONT_RANGE) + i//2,
                            left_bearing=-left,
                            right_bearing=-right,
                        )
                    )
                    x += left+width+right + length%2
                    left = right
            else:
                width = length
        return Font(glyphs)


    @savers.register(linked=load_sfont)
    def save_sfont(fonts, outstream, *, image_format:str='png'):
        """
        Save font to SFont file.

        image_format: format of the image file. Default: `png`
        """
        font = ensure_single(fonts)
        font = font.equalise_horizontal()
        font = font.resample(codepoints=_SFONT_RANGE)
        glyphmap = GlyphMap()
        glyphmap.append_glyph(Glyph(), 0, 0)
        indicator = []
        right = 0
        x = 0
        for cp in _SFONT_RANGE:
            glyph = font.get_glyph(codepoint=cp)
            left = -glyph.left_bearing
            indicator_length = left
            if cp > min(_SFONT_RANGE):
                indicator_length += right + (right+left)%2 + 1
            x += indicator_length
            glyphmap.append_glyph(glyph, x, 0)
            width = glyph.advance_width
            x += width
            indicator.extend((_INDICATOR_RGB,) * indicator_length)
            indicator.extend(((0, 0, 0),) * width)
            right = -glyph.right_bearing
        if right:
            indicator.append(_INDICATOR_RGB * right)
        glyphmap.append_glyph(Glyph(), x, 0)
        glyph_image = glyphmap.as_image(
            ink=(255, 255, 255), paper=(0, 0, 0), border=(0, 0, 0)
        )
        image = Image.new(
            glyph_image.mode, (glyph_image.width, glyph_image.height+1)
        )
        image.paste(glyph_image, (0, 1))
        image.putdata(indicator)
        image.save(outstream, format=image_format)
