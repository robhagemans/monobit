"""
monobit.storage.wrappers.unixcompress - compress (.Z) encoding

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO
from pathlib import Path

try:
    import ncompress
except ImportError:
    ncompress = None

from ..streams import Stream
from ..magic import FileFormatError
from ..base import wrappers
from .wrappers import FilterWrapper


if ncompress:

    @wrappers.register(
        name='compress',
        patterns=('*.Z',),
        magic=(b'\x1f\x9d',),
    )
    class CompressWrapper(FilterWrapper):
        """Compresss .Z format wrapper."""

        @staticmethod
        def decode(instream):
            return ncompress.decompress(instream)

        @staticmethod
        def encode(data, outstream):
            ncompress.compress(data, outstream)
