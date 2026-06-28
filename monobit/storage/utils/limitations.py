"""
monobit.storage.utils.limitations - deal with font format limitations

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import Coord
from monobit.core import Glyph, Font
from monobit.base import UnsupportedError


def ensure_single(fonts):
    font, *more = fonts
    if more:
        raise UnsupportedError('This format can only store one font per file.')
    return font


def ensure_charcell(font, cell_size=None):
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise UnsupportedError(
            'This format only supports character-cell fonts. '
            f'It cannot store this font with spacing={font.spacing}.'
        )
    if cell_size:
        cell_size = Coord.create(cell_size)
        if font.cell_size != cell_size:
            raise UnsupportedError(
                f'This format only supports {cell_size} character-cell fonts. '
                f'It cannot store this Font with cell-size={font.cell_size}.'
            )
    # fill out character cell including shifts, bearings and line height
    font = font.equalise_horizontal()
    return font


def make_contiguous(font, *, missing, supported_range=None, full_range=None):
    """Fill out a contiguous range of glyphs."""
    # fill in codepoints where possible
    font = font.label(codepoint_from=font.encoding)
    if not full_range:
        # we need a contiguous range between the min and max codepoints
        min_range = int(min(font.get_codepoints()))
        max_range = int(max(font.get_codepoints()))
        if supported_range:
            min_range = max(min_range, min(supported_range))
            max_range = min(max_range, max(supported_range))
        full_range = range(min_range, max_range+1)
    font = font.resample(codepoints=full_range, missing=missing)
    return font


def ensure_levels(fonts, levels):
    """Check ink levels can be stored."""
    if isinstance(fonts, Font):
        iter_fonts = (fonts,)
    else:
        iter_fonts = fonts
    for font in iter_fonts:
        if font.levels > levels:
            raise UnsupportedError(
                f'This format can save at most {levels} ink levels; '
                f'the font has {font.levels} levels.'
            )
    return fonts


def reencode(font, encoding, fallback=None):
    """Regenerate codepoints according to a different encoding."""
    # create char labels where possible
    font = font.label()
    # remove all old codepoint labels
    font = font.label(codepoint_from=None, overwrite=True)
    # create new codepoint labels
    font = font.label(codepoint_from=encoding)
    font = font.label(codepoint_from=fallback)
    font = font.modify(encoding=encoding)
    return font
