"""
monobit.containers.compressors - single-file compression wrappers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from contextlib import contextmanager
import gzip
import lzma
import bz2

from ..storage import loaders, savers, load_stream, save_stream
from ..storage import open_container, containers
from ..streams import Stream
from ..magic import FileFormatError


class _WrappedContainer:
    """Wrapper for compressed coontainer objects, manages compressed stream."""

    def __init__(self, container, wrapping_stream):
        self._container = container
        self._stream = wrapping_stream

    def close(self):
        """Ensure wrapping stream is closed."""
        self._container.close()
        self._stream.close()

    def __enter__(self):
        return self._container.__enter__()

    def __exit__(self, *args, **kwargs):
        self._container.__exit__(*args, **kwargs)
        self._stream.close()

    def __iter__(self):
        return self._container.__iter__()

    def __contains__(self, *args, **kwargs):
        return self._container.__contains__(*args, **kwargs)

    def __getattr__(self, attr):
        if attr.startswith('_'):
            raise AttributeError(attr)
        return getattr(self._container, attr)


class Compressor:
    """Base class for single-file compression helpers."""

    name = ''
    format = ''
    compressor = None
    # error raised for bad format
    error = Exception
    magic = b''
    suffixes = ()
    must_have_magic = True

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
    def load(cls, instream, payload:str='', **kwargs):
        """
        Load fonts from compressed stream.

        payload: format of compressed font file.
        """
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
        wrapped = cls._get_payload_stream(outstream, 'w')
        with cls._translate_errors():
            with wrapped:
                return save_stream(fonts, wrapped, format=payload, **kwargs)

    @classmethod
    def open(cls, stream, mode, **kwargs):
        """Open container on compressed stream."""
        if mode == 'r':
            cls._check_magic(stream)
        wrapped = cls._get_payload_stream(stream, mode)
        with cls._translate_errors():
            container = open_container(wrapped, mode, **kwargs)
        return _WrappedContainer(container, stream)

    @classmethod
    def register(cls):
        loaders.register(
            *cls.suffixes, name=cls.name, magic=(cls.magic,), wrapper=True
        )(cls.load)
        savers.register(
            *cls.suffixes, name=cls.name, magic=(cls.magic,), wrapper=True
        )(cls.save)
        containers.register(
            *cls.suffixes, name=cls.name, magic=(cls.magic,), wrapper=True
        )(cls.open)


class GzipCompressor(Compressor):
    name  = 'gzip'
    compressor = gzip
    error = gzip.BadGzipFile
    magic = b'\x1f\x8b'
    suffixes = ('gz',)

GzipCompressor.register()


class XZCompressor(Compressor):
    name = 'xz'
    compressor = lzma
    error = lzma.LZMAError
    magic = b'\xFD7zXZ\x00'
    suffixes = ('xz',)

XZCompressor.register()

class LzmaCompressor(Compressor):
    name = 'lzma'
    compressor = lzma
    error = lzma.LZMAError
    # the magic is a 'maybe'
    magic = b'\x5d\0\0'
    must_have_magic = False
    suffixes = ('lzma',)

LzmaCompressor.register()


class Bzip2Compressor(Compressor):
    name = 'bzip2'
    compressor = bz2
    error = OSError
    magic = b'BZh'
    suffixes = ('bz2',)

Bzip2Compressor.register()
