"""
monobit.formats.os2 - read OS/2 GPI bitmap fonts and LX containers

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT

this implementation leans heavily on Alexander Taylor's os2font
- http://www.altsan.org/programming/os2font_src.zip
- https://github.com/altsan/os2-gpi-font-tools
"""

import logging

from ...storage import loaders, savers
from ...streams import FileFormatError
from ...font import Font

from .gpifont import convert_os2_font_resource, GPI_MAGIC


@loaders.register(
    #'fnt',
    name='gpi',
    magic=(GPI_MAGIC,)
)
def load_os2(instream, where=None,):
    """Load a bare OS/2 GPI font resource."""
    resource = instream.read()
    return convert_os2_font_resource(resource)
