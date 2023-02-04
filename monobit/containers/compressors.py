"""
monobit.containers.compressors - single-file compression wrappers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import gzip
import lzma
import bz2

from ..magic import get_suffix
from ..container import containers, ContainerFormatError, Container
from ..streams import Stream


###################################################################################################
# single-file compression

class Compressor(Container):
    """Base class for compression helpers."""

    format = ''
    compressor = None
    # error raised for bad format
    error = Exception
    magic = b''

    def __init__(self, infile, mode='r', *, overwrite=False):
        """Set up a compressor wrapper."""
        stream = Stream(infile, mode, overwrite=overwrite)
        super().__init__(stream, mode)
        # drop the .gz etc
        last_suffix = get_suffix(self.name)
        if last_suffix == self.format:
            self._content_name = self.name[:-1-len(last_suffix)]
        else:
            self._content_name = self.name
        if self.mode == 'r':
            magic = stream.peek(len(self.magic))[:len(self.magic)]
            if self.magic and magic != self.magic:
                raise ContainerFormatError(
                    f'Not a {self.format} container: magic bytes {magic};'
                    f' expected {self.magic}'
                )

    def __iter__(self):
        """Iterate over content (single file)."""
        return iter((self._content_name,))

    def open(self, name='', mode=''):
        """Open a stream in the container."""
        mode = mode[:1] or self.mode
        wrapped = self.compressor.open(self._stream, mode + 'b')
        wrapped = Stream(wrapped, mode, name=self._content_name)
        logging.debug(
            "Opening %s-compressed stream `%s` on `%s` for mode '%s'",
            self.format, wrapped.name, self.name, mode
        )
        return wrapped


_GZ_MAGIC = b'\x1f\x8b'

@containers.register('.gz', magic=(_GZ_MAGIC,))
class GzipCompressor(Compressor):
    compressor = gzip
    error = gzip.BadGzipFile
    magic = _GZ_MAGIC


_XZ_MAGIC = b'\xFD7zXZ\x00'

@containers.register('.xz', magic=(_XZ_MAGIC,))
class XZCompressor(Compressor):
    compressor = lzma
    error = lzma.LZMAError
    magic = _XZ_MAGIC


# the magic is a 'maybe'
@containers.register('.lzma', magic=(b'\x5d\0\0',))
class LzmaCompressor(Compressor):
    compressor = lzma
    error = lzma.LZMAError


_BZ2_MAGIC = b'BZh'

@containers.register('.bz2', magic=(_BZ2_MAGIC,))
class Bzip2Compressor(Compressor):
    compressor = bz2
    error = OSError
    magic = _BZ2_MAGIC
