"""
monobit.storage.wrappers.compressors - single-file compression wrappers

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import gzip
import lzma
import bz2
from pathlib import Path

from ..streams import Stream
from ..magic import FileFormatError
from ..base import encoders, decoders


###############################################################################
# gzip

@decoders.register(
    name='gzip',
    magic=(b'\x1f\x8b',),
    patterns=('*.gz',),
)
def decode_gzip(instream):
    """Decode a gzip-compressed stream."""
    stream = gzip.open(instream, mode='rb')
    try:
        stream.peek(0)
    except BadGzipFile as e:
        raise FileFormatError(e) from e
    name = Path(instream.name).stem
    return Stream(stream, mode='r', name=name)


@encoders.register(linked=decode_gzip)
def encode_gzip(outstream):
    """Encode to a gzip-compressed stream."""
    stream = gzip.open(outstream, mode='wb')
    name = Path(outstream.name).stem
    return Stream(stream, mode='w', name=name)


###############################################################################
# lzma

@decoders.register(
    name='xz',
    magic=(b'\xFD7zXZ\x00',),
    patterns=('*.xz',),
)
def decode_xz(instream):
    return _decode_lzma_or_xz(instream)


@decoders.register(
    name='lzma',
    # the magic is a 'maybe'
    magic=(b'\x5d\0\0',),
    patterns=('*.lzma',),
)
def decode_lzma(instream):
    return _decode_lzma_or_xz(instream)


def _decode_lzma_or_xz(instream):
    """Decode a lzma or xz-compressed stream."""
    stream = lzma.open(instream, mode='rb')
    try:
        stream.peek(0)
    except LZMAError as e:
        raise FileFormatError(e) from e
    name = Path(instream.name).stem
    return Stream(stream, mode='r', name=name)


@encoders.register(linked=decode_lzma)
def encode_lzma(outstream):
    """Encode to a lzma-compressed stream."""
    stream = lzma.open(outstream, mode='wb', format=lzma.FORMAT_ALONE)
    name = Path(outstream.name).stem
    return Stream(stream, mode='w', name=name)


@encoders.register(linked=decode_xz)
def encode_xz(outstream):
    """Encode to a xz-compressed stream."""
    stream = lzma.open(outstream, mode='wb', format=lzma.FORMAT_XZ)
    name = Path(outstream.name).stem
    return Stream(stream, mode='w', name=name)


###############################################################################
# bzip2

@decoders.register(
    name='bzip2',
    magic=(b'BZh',),
    patterns=('*.bz2',),
)
def decode_bzip2(instream):
    """Decode a bzip2-compressed stream."""
    stream = bz2.open(instream, mode='rb')
    try:
        stream.peek(0)
    except OSError as e:
        raise FileFormatError(e) from e
    name = Path(instream.name).stem
    return Stream(stream, mode='r', name=name)


@encoders.register(linked=decode_bzip2)
def encode_bzip2(outstream):
    """Encode to a bzip2-compressed stream."""
    stream = bz2.open(outstream, mode='wb')
    name = Path(outstream.name).stem
    return Stream(stream, mode='w', name=name)
