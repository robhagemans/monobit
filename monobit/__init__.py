"""
monobit - tools for working with monochrome bitmap fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# we need at least Python 3.6
import sys as _sys
assert _sys.version_info >= (3, 6)

from .base import VERSION as __version__
from .typeface import Typeface
from .formats import Loaders, Savers
from .text import to_text as _to_text

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

from .image import show, render


# get font operations
OPERATIONS = {
    _name: _func
    for _name, _func in Typeface.__dict__.items()
    if hasattr(_func, 'scriptable')
}

# inject operations into main module namespace
globals().update(OPERATIONS)

save = Savers().save
load = Loaders().load


def banner(
        font, text, fore='@', back='.',
        margin=(0, 0), scale=(1, 1), missing='default', stream=_sys.stdout
    ):
    """Print a banner."""
    stream.write(_to_text(font.render(
        text, fore, back, margin=margin, scale=scale, missing=missing
    )) + '\n')
