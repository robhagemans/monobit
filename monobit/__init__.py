"""
monobit - tools for working with monochrome bitmap fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# we need at least Python 3.7
import sys as _sys
assert _sys.version_info >= (3, 7)

from .constants import VERSION as __version__
from .pack import Pack, operations as _pack_operations
from .font import Font, operations as _operations
from .glyph import Glyph
from . import formats
from .storage import open_location, load, save, loaders, savers
from .encoding import charmaps, encoder
from .taggers import tagmaps
from .renderer import render
from .labels import Char, Codepoint, Tag


_operations.update(_pack_operations)
# inject font operations into main module namespace
globals().update(_operations)

# make dash-versions of operations available through dict
operations = {
    _name.replace('_', '-'): _func
    for _name, _func in _operations.items()
}
