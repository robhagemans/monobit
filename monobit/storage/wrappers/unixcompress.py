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
from ..base import encoders, decoders
from .wrappers import _WrappedWriterStream


if ncompress:

    @decoders.register(
        name='compress',
        patterns=('*.Z',),
        magic=(b'\x1f\x9d',),
    )
    def decode_compress(instream):
        data = ncompress.decompress(instream)
        name = Path(instream.name).stem
        return Stream.from_data(data, mode='r', name=name)


    @encoders.register(linked=decode_compress)
    def encode_compress(outstream):
        encode_func = ncompress.compress
        name = Path(outstream.name).stem
        return _WrappedWriterStream(outstream, encode_func, name)
