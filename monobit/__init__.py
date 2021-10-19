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
from .font import Font, operations as _operations
from .glyph import Glyph
from .formats import loaders, savers, converters, open_location, load, save
from .encoding import charmaps
from .renderer import render, render_image, render_text


# inject font operations into main module namespace
globals().update(_operations)

# make dash-versions of operations available through dict
operations = {
    _name.replace('_', '-'): _func
    for _name, _func in _operations.items()
}
