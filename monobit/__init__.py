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
from .font import Font
from .glyph import Glyph
from .encoding import Codepage
from .formats import loaders, savers, open_location

from . import bmfont
from . import winfon
from . import winfnt
from . import amiga
from . import image
from . import yaff
from . import raw
from . import mac
from . import bdf
from . import psf
from . import hex
from . import cpi
from . import fzx
from . import pdf
from . import c

from .image import create_image, render


# get font operations
OPERATIONS = {
    _name: _func
    for _name, _func in Pack.__dict__.items()
    if hasattr(_func, 'scriptable')
}

# inject operations into main module namespace
globals().update(OPERATIONS)

save = savers.save
load = loaders.load
