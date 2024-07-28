"""
monobit.storage.formats.fon.os2 - read OS/2 GPI bitmap fonts and LX containers

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT

this implementation leans heavily on Alexander Taylor's os2font
- http://www.altsan.org/programming/os2font_src.zip
- https://github.com/altsan/os2-gpi-font-tools
"""

import logging

from monobit.storage import loaders, savers
from monobit.storage import Magic
from monobit.core import Font

from .gpifont import convert_os2_font_resource, GPI_MAGIC, OS2FNT_SIGNATURE


@loaders.register(
    name='gpi',
    magic=(GPI_MAGIC + Magic.offset(4) + OS2FNT_SIGNATURE.encode('ascii'),),
    patterns=('*.fnt',),
)
def load_os2(instream):
    """Load a bare OS/2 GPI font resource."""
    resource = instream.read()
    return convert_os2_font_resource(resource)
