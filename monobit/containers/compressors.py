"""
monobit.containers.compressors - single-file compression wrappers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
import gzip
import lzma
import bz2

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
    must_have_magic = True

    @classmethod
    def load(cls, instream, **kwargs):
        """Load fonts from compressed stream."""
        magic = instream.peek(len(cls.magic))
        if cls.must_have_magic and not magic.startswith(cls.magic):
            raise FileFormatError(
                f'Not a {cls.name}-compressed file'
            )
        name = Path(instream.name).stem
        wrapped = Stream(
            cls.compressor.open(instream, mode='rb'),
            mode='r', name=name
        )
        try:
            with wrapped:
                return load_stream(wrapped, **kwargs)
        except cls.error as e:
            raise FileFormatError(e)


    @classmethod
    def save(cls, fonts, outstream, **kwargs):
        """Load fonts from compressed stream."""
        name = Path(outstream.name).stem
        wrapped = Stream(
            cls.compressor.open(outstream, mode='wb'),
            mode='w', name=name
        )
        try:
            with wrapped:
                return save_stream(fonts, wrapped, **kwargs)
        except cls.error as e:
            raise FileFormatError(e)

    @classmethod
    def register(cls):
        loaders.register(
            *cls.suffixes, name=cls.name, magic=(cls.magic,)
        )(cls.load)
        savers.register(
            *cls.suffixes, name=cls.name, magic=(cls.magic,)
        )(cls.save)



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
