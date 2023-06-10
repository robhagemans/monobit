"""
monobit.formats.sfnt - TrueType/OpenType and related formats

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .sfnt import load_sfnt, load_collection
from .sfnt_writer import save_sfnt, save_collection, to_postscript_name

from .sfnt import MAC_ENCODING, mac_style_name, SFNT_MAGIC, STYLE_MAP
