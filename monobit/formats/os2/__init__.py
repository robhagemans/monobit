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
from ...font import Font

from .lx import read_os2_font
from .gpifont import parse_os2_font_resource, convert_os2_glyphs


@loaders.register(
    #'fon',
    name='os2',
)
def load_os2(
        instream, where=None,
    ):
    """Load an OS/2 font file."""
    resources = read_os2_font(instream)
    parsed = (
        parse_os2_font_resource(_data)
        for _data in resources
    )
    # TODO: convert font metrics
    fonts = tuple(
        Font(convert_os2_glyphs(_pfont))
        for _pfont in parsed
    )
    return fonts
