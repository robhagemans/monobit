"""
monobit.storage.fontformats.sfont - SDL SFont format

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import groupby

from monobit.base import safe_import
Image = safe_import('PIL.Image')

from monobit.storage import loaders, savers
from monobit.base import FileFormatError, UnsupportedError
from monobit.core import Font, Glyph
from monobit.renderer import GlyphMap
from monobit.core.palette import Palette

from monobit.storage.utils.limitations import ensure_single
from .image import sort_inklevels

# see https://github.com/karlb/sfont


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
        image = Image.open(instream).convert('RGBA')
        glyphs = []
        indicator = tuple(image.crop((0, 0, image.width, 1)).getdata())
        if len(set(indicator)) != 2:
            raise FileFormatError('Not an SFont image: missing indicator bar.')
        # background colour is what's in the indicator bar when it's not the indicator colour
        non_indicator = tuple(
            _rgba for _rgba in set(indicator) if _rgba[:3] != _INDICATOR_RGB
        )
        if not non_indicator:
            raise FileFormatError('No gaps in top indicator bar')
        background = non_indicator[0]
        if len(non_indicator) > 1:
            logging.warning(
                'Multiple background colours found: %s. Picking %s',
                non_indicator, background
            )
        spritesheet = image.crop((0, 1, image.width, image.height))
        # get palette
        inklevels = sort_inklevels(spritesheet.getdata(), background)
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
            if clr[:3] == _INDICATOR_RGB:
                if i == 0:
                    left = length
                else:
                    if i == len(groups) - 1:
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
                            # i is always even for indicators
                            # first codepoint is writen at second indicator
                            codepoint=min(_SFONT_RANGE) + i//2 - 1,
                            left_bearing=-left,
                            right_bearing=-right,
                        )
                    )
                    x += left+width+right + length%2
                    left = right
            else:
                width = length
        font = Font(glyphs, palette=inklevels)
        return font


    @savers.register(linked=load_sfont)
    def save_sfont(fonts, outstream, *, image_format:str='png'):
        """
        Save font to SFont file.

        image_format: format of the image file. Default: `png`
        """
        font = ensure_single(fonts)
        font = font.equalise_horizontal()
        font = font.resample(codepoints=_SFONT_RANGE)
        glyphmap = GlyphMap(levels=font.levels, palette=font.palette)
        glyphmap.append_glyph(Glyph(), 0, 0)
        indicator = []
        right = 0
        x = 0
        for cp in _SFONT_RANGE:
            glyph = font.get_glyph(codepoint=cp)
            left = max(0, -glyph.left_bearing)
            if cp == min(_SFONT_RANGE):
                indicator_length = left
            else:
                indicator_length = 2 * max(left, right)
            indicator_length = max(1, indicator_length)
            x += indicator_length
            glyphmap.append_glyph(glyph, x, 0)
            width = max(1, glyph.advance_width)
            x += width
            indicator.extend((_INDICATOR_RGB,) * indicator_length)
            indicator.extend(((0, 0, 0),) * width)
            right = max(0, -glyph.right_bearing)
        if right:
            indicator.append(_INDICATOR_RGB * right)
        glyphmap.append_glyph(Glyph(), x, 0)
        glyph_image = glyphmap.as_image(border=(0, 0, 0))
        image = Image.new(
            glyph_image.mode, (glyph_image.width, glyph_image.height+1)
        )
        image.paste(glyph_image, (0, 1))
        image.putdata(indicator)
        image.save(outstream, format=image_format)
