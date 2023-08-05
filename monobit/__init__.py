"""
monobit - tools for working with monochrome bitmap fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys as _sys
assert _sys.version_info >= (3, 9)

from .constants import VERSION as __version__
from .core import Pack
from .core import Font, operations as _operations
from .core import Glyph
from .storage import load, save, loaders, savers
from .storage import FileFormatError
from .encoding import encoder, encodings
from .render import render, chart
from .core import Char, Codepoint, Tag


# inject font operations into main module namespace
globals().update(_operations)

# make dash-versions of operations available through dict
operations = {
    _name.replace('_', '-'): _func
    for _name, _func in _operations.items()
}
