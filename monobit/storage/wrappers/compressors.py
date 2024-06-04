"""
monobit.storage.wrappers.compressors - single-file compression wrappers

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from contextlib import contextmanager
from importlib import import_module

from ..streams import Stream
from ..magic import FileFormatError
from ..base import wrappers
from .wrappers import Wrapper


class Compressor(Wrapper):
    """Base class for single-file compression helpers."""

    compressor = None
    # error raised for bad format
    error = Exception
    # late import machinery
    module = ''
    errorclass = ''

    def __init__(self, stream, mode='r'):
        self._ensure_imports()
        super().__init__(stream, mode)

    def __exit__(self, exc_type, exc_value, traceback):
        # convert library-specific errors to ours
        if exc_type == self.error:
            raise FileFormatEror(exc_value)
        super().__exit__(exc_type, exc_value, traceback)

    def open(self):
        """Get the uncompressed stream."""
        name = Path(self._wrapped_stream.name).stem
        stream = self.compressor.open(self._wrapped_stream, mode=self.mode+'b')
        self._unwrapped_stream = Stream(stream, mode=self.mode, name=name)
        return self._unwrapped_stream

    @classmethod
    def _ensure_imports(cls):
        """Late import of compressor library."""
        if cls.module:
            cls.compressor = import_module(cls.module)
            cls.module = ''
        if cls.errorclass:
            cls.error = getattr(cls.compressor, cls.errorclass)
            cls.errorclass = ''


@wrappers.register(
    name='gzip',
    magic=(b'\x1f\x8b',),
    patterns=('*.gz',),
)
class GzipCompressor(Compressor):
    module = 'gzip'
    errorclass = 'BadGzipFile'


@wrappers.register(
    name='xz',
    magic=(b'\xFD7zXZ\x00',),
    patterns=('*.xz',),
)
class XZCompressor(Compressor):
    module = 'lzma'
    errorclass = 'LZMAError'


@wrappers.register(
    name='lzma',
    # the magic is a 'maybe'
    magic=(b'\x5d\0\0',),
    patterns=('*.lzma',),
)
class LzmaCompressor(Compressor):
    module = 'lzma'
    errorclass = 'LZMAError'


@wrappers.register(
    name='bzip2',
    magic=(b'BZh',),
    patterns=('*.bz2',),
)
class Bzip2Compressor(Compressor):
    module = 'bz2'
    error = OSError
