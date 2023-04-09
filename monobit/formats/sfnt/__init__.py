"""
monobit.formats.sfnt - TrueType/OpenType and related formats

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

try:
    from .sfnt import load_sfnt, load_collection
    from .sfnt_writer import save_sfnt, save_collection
except ImportError:
    from .sfnt import _no_fonttools
    # load_sfnt must be importable by mac, win modules
    def load_sfnt(*args, **kwargs):
        _no_fonttools()

from .sfnt import MAC_ENCODING, mac_style_name, SFNT_MAGIC
