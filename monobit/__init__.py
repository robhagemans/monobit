"""
monobit - tools for working with monochrome bitmap fonts

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# we need at least Python 3.6
import sys as _sys
assert _sys.version_info >= (3, 6)

from .base import VERSION as __version__
from .pack import Pack
from .font import Font, operations
from .glyph import Glyph
from .formats import loaders, savers, open_location, converters
from .encoding import charmaps
from .renderer import render, render_image, render_text

# inject font operations into main module namespace
globals().update(operations)

save = savers.save
load = loaders.load
