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
from .wrapper import Wrapper


class Compressor(Wrapper):
    """Base class for single-file compression helpers."""

    name = ''
    format = ''
    compressor = None
    # error raised for bad format
    error = Exception
    magic = b''
    suffixes = ()
    patterns = ()
    must_have_magic = True
    # late import machinery
    module = ''
    errorclass = ''

    def __init__(self, stream, mode='r'):
        if mode == 'r':
            self._check_magic(stream)
        self._ensure_imports()
        super().__init__(stream, mode)

    # leave magic checks to MagicRegistry?
    # but we need to be able to raise FileFormatError
    # i.e. would need to implement 'must have magic' on MagicRegistry
    @classmethod
    def _check_magic(cls, instream):
        """Check if the magic signature is correct."""
        magic = instream.peek(len(cls.magic))
        if cls.must_have_magic and not magic.startswith(cls.magic):
            raise FileFormatError(
                f"Stream '{instream.name}' is not a `{cls.name}`-compressed file."
            )

    @classmethod
    def _get_payload_stream(cls, stream, mode):
        """Get the uncompressed stream."""
        name = Path(stream.name).stem
        wrapped = Stream(
            cls.compressor.open(stream, mode=mode + 'b'),
            mode=mode, name=name
        )
        return wrapped

    def open(self):
        """Get the uncompressed stream."""
        self._unwrapped_stream = self._get_payload_stream(
            self._wrapped_stream, self.mode
        )
        return self._unwrapped_stream

    #FIXME reintroduce
    # @classmethod
    # @contextmanager
    # def _translate_errors(cls):
    #     """Context wrapper to convert library-specific errors to ours."""
    #     try:
    #         yield
    #     except cls.error as e:
    #         raise FileFormatError(e)

    @classmethod
    def _ensure_imports(cls):
        """Late import compressor library."""
        if cls.module:
            cls.compressor = import_module(cls.module)
            cls.module = ''
        if cls.errorclass:
            cls.error = getattr(cls.compressor, cls.errorclass)
            cls.errorclass = ''

    @classmethod
    def register(cls):
        wrappers.register(
            name=cls.name, magic=(cls.magic,), patterns=cls.patterns
        )(cls)


class GzipCompressor(Compressor):
    name  = 'gzip'
    module = 'gzip'
    errorclass = 'BadGzipFile'
    magic = b'\x1f\x8b'
    patterns = ('*.gz',)

GzipCompressor.register()


class XZCompressor(Compressor):
    name = 'xz'
    module = 'lzma'
    errorclass = 'LZMAError'
    magic = b'\xFD7zXZ\x00'
    patterns = ('*.xz',)

XZCompressor.register()

class LzmaCompressor(Compressor):
    name = 'lzma'
    module = 'lzma'
    errorclass = 'LZMAError'
    # the magic is a 'maybe'
    magic = b'\x5d\0\0'
    must_have_magic = False
    patterns = ('*.lzma',)

LzmaCompressor.register()


class Bzip2Compressor(Compressor):
    name = 'bzip2'
    module = 'bz2'
    error = OSError
    magic = b'BZh'
    patterns = ('*.bz2',)

Bzip2Compressor.register()
