"""
monobit - tools for working with monochrome, monospaced bitmap fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import VERSION as __version__
from .base import Font

from . import operations
from . import amiga
from . import image
from . import text
from . import raw
from . import bdf
from . import c

from .image import show


# inject per-glyph operations

def _modifier(func):
    """Return modified version of font."""
    def _modify(font, *args, **kwargs):
        return font.modified(func, *args, **kwargs)
    return _modify

globals().update({
    _name: _modifier(_func)
    for _name, _func in operations.__dict__.items()
})


# other operations

load = Font.load
renumber = Font.renumbered
subset = Font.subset
