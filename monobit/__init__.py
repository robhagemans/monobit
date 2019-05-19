"""
monobit - tools for working with monochrome, monospaced bitmap fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# we need at least Python 3.6
import sys as _sys
assert _sys.version_info >= (3, 6)

from .base import VERSION as __version__
from .base import Typeface

from . import winfon
from . import winfnt
from . import amiga
from . import image
from . import text
from . import raw
from . import bdf
from . import psf
from . import hex
from . import cpi
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
