"""
monobit.storage.formats.limitations - deal with font format limitations

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base import Coord


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
