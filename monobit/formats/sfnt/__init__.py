"""
monobit.formats.sfnt - TrueType/OpenType and related formats

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .sfnt import load_sfnt, load_collection, MAC_ENCODING, mac_style_name, SFNT_MAGIC
from .sfnt_writer import save_sfnt, save_collection
