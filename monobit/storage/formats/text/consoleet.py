"""
monobit.storage.formats.text.consoleet - consoleet / vfontas / hxtools format

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from pathlib import Path
import logging

from monobit.storage.base import container_loaders, container_savers
from monobit.storage import FileFormatError
from monobit.core import Font, Glyph
from ..image.image import loop_load


@container_loaders.register(name='consoleet')
def load_clt(location):
    """Load font from consoleet files."""
    # this format consists of separate image files, without a manifest
    glyphs = loop_load(location, _read_clt_glyph)
    return Font(glyphs, source_name=location.path)


def _read_clt_glyph(instream):
    text = instream.text
    name = instream.name
    codepoint = Path(name).stem
    magic = text.readline().strip()
    if magic != 'PCLT':
        return Glyph()
    width, _, height = text.readline().strip().partition(' ')
    glyphtext = text.read().splitlines()
    return Glyph(
        glyphtext, _0='.', _1='#',
        # encoding is not specified by spec or file - can be unicode or codepage
        codepoint=f'0x{codepoint}'
    ).shrink(factor_x=2)
