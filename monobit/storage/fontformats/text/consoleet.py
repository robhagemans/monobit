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

from ..image.image import loop_load, loop_save
from monobit.storage.utils.limitations import ensure_single


@container_loaders.register(name='consoleet')
def load_clt(location):
    """Load font from consoleet files."""
    # this format consists of separate image files, without a manifest
    glyphs = loop_load(location, _read_clt_glyph)
    return Font(glyphs, source_name=location.path)


@container_savers.register(linked=load_clt)
def save_clt(fonts, location):
    """
    Save font to consoleet files.
    """
    loop_save(
        fonts, location,
        prefix='', suffix='txt', save_func=_write_clt_glyph,
    )


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


def _write_clt_glyph(glyph, outstream):
    text = outstream.text
    text.write('PCLT\n')
    text.write(f'{glyph.width} {glyph.height}\n')
    text.write(glyph.as_text(paper='..', ink='##', end='\n'))
