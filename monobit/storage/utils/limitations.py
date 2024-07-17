"""
monobit.storage.utils.limitations - deal with font format limitations

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import Coord
from monobit.core import Glyph
from monobit.base import FileFormatError


def ensure_single(fonts):
    font, *more = fonts
    if more:
        raise FileFormatError('This format can only store one font per file.')
    return font


def ensure_charcell(font, cell_size=None):
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    if cell_size and font.cell_size != cell_size:
        raise FileFormatError(
            f'This format only supports {Coord(cell_size)} character-cell fonts.'
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
