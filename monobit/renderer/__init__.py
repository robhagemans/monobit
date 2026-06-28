"""
monobit.renderer - render to bitmaps

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .renderer import render, render_text
from .createchart import (
    chart, create_chart, grid_map, grid_traverser, write_imagefile,
)
from .glyphmap import GlyphMap, glyph_to_image
from .rgb import RGBTable, create_image_colours, create_gradient
from .image import write_imagefile, IMAGE_PATTERNS, IMAGE_MAGIC

from . import pdf
