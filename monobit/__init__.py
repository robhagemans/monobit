"""
monobit - tools for working with monochrome bitmap fonts

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys as _sys
assert _sys.version_info >= (3, 9)

from .constants import VERSION as __version__
from .core import Pack, Font, Glyph, Char, Codepoint, Tag
from .storage import FileFormatError, load, save, loaders, savers
from .plumbing import scriptables as _operations
from .encoding import encoder, encodings
from .render import render, chart


# inject font operations into main module namespace
globals().update(_operations)

# make dash-versions of operations available through dict
operations = {
    _name.replace('_', '-'): _func
    for _name, _func in _operations.items()
}
