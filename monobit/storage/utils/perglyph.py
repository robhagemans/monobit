"""
monobit.storage.utils.perglyph - utilities for one-glyph-per-file formats

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage.utils.limitations import ensure_single


def loop_save(fonts, location, prefix, suffix, save_func):
    """Loop over per-glyph files in container."""
    font = ensure_single(fonts)
    font = font.label(codepoint_from=font.encoding)
    font = font.equalise_horizontal()
    width = len(f'{int(max(font.get_codepoints())):x}')
    for glyph in font.glyphs:
        if not glyph.codepoint:
            logging.warning('Cannot store glyph without codepoint label.')
            continue
        cp = f'{int(glyph.codepoint):x}'.zfill(width)
        name = f'{prefix}{cp}.{suffix}'
        with location.open(name, 'w') as imgfile:
            save_func(glyph, imgfile)


def loop_load(location, load_func):
    """Loop over per-glyph files in container."""
    glyphs = []
    for name in sorted(location.iter_sub('')):
        with location.open(name, mode='r') as stream:
            glyphs.append(load_func(stream))
    return glyphs
