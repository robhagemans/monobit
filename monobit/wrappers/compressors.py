"""
monobit.containers.compressors - single-file compression wrappers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from contextlib import contextmanager
from importlib import import_module

from ..storage import loaders, savers, load_stream, save_stream
from ..streams import Stream
from ..magic import FileFormatError


class Compressor:
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

    @classmethod
    def _check_magic(cls, instream):
        """Check if the magic signature is correct."""
        magic = instream.peek(len(cls.magic))
        if cls.must_have_magic and not magic.startswith(cls.magic):
            raise FileFormatError(
                f'Not a {cls.name}-compressed file'
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

    @classmethod
    @contextmanager
    def _translate_errors(cls):
        """Context wrapper to convert library-specific errors to ours."""
        try:
            yield
        except cls.error as e:
            raise FileFormatError(e)

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
    def load(cls, instream, payload:str='', **kwargs):
        """
        Load fonts from compressed stream.

        payload: format of compressed font file.
        """
        cls._ensure_imports()
        cls._check_magic(instream)
        wrapped = cls._get_payload_stream(instream, 'r')
        with cls._translate_errors():
            with wrapped:
                return load_stream(wrapped, format=payload, **kwargs)

    @classmethod
    def save(cls, fonts, outstream, payload:str='', **kwargs):
        """
        Save fonts to compressed stream.

        payload: format of compressed font file.
        """
        cls._ensure_imports()
        wrapped = cls._get_payload_stream(outstream, 'w')
        with cls._translate_errors():
            with wrapped:
                return save_stream(fonts, wrapped, format=payload, **kwargs)

    @classmethod
    def register(cls):
        loaders.register(
            name=cls.name, magic=(cls.magic,), patterns=cls.patterns, wrapper=True
        )(cls.load)
        savers.register(
            name=cls.name, magic=(cls.magic,), patterns=cls.patterns, wrapper=True
        )(cls.save)


class GzipCompressor(Compressor):
    name  = 'gzip'
    module = 'gzip'
    errorclass = 'BadGzipFile'
    #compressor = gzip
    #error = gzip.BadGzipFile
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
