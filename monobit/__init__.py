"""
monobit - tools for working with monochrome, monospaced bitmap fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from functools import partial

from .base import VERSION as __version__
from .base import Font

from . import glyph as operations
from . import amiga
from . import image
from . import text
from . import raw
from . import bdf
from . import c

from .image import show


# get font operations
OPERATIONS = {
    _name: _func
    for _name, _func in Font.__dict__.items()
    if not _name.startswith('_')
}
# doesn't work for classmethod
OPERATIONS['load'] = Font.load

# inject operations into main module namespace
globals().update(OPERATIONS)
