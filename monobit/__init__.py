"""
monobit - tools for working with monochrome, monospaced bitmap fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import VERSION as __version__
from .base import Typeface

from . import windows
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
    for _name, _func in Typeface.__dict__.items()
    if hasattr(_func, 'scriptable')
}

# inject operations into main module namespace
globals().update(OPERATIONS)

load = Typeface.load
