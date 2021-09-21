"""
monobit.formats - loader and saver plugin registry

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import logging
from pathlib import Path
import gzip
import lzma
import bz2


def open_stream(file, mode, binary, *, on=None):
    """Ensure file is a stream of the right type, open or wrap if necessary."""
    return Stream(file, mode, binary, on=on)


class StreamWrapper:
    """Wrapper object to emulate a single text stream."""

    def __init__(self, stream):
        self._stream = stream

    def __getattr__(self, attr):
        """Delegate undefined attributes to wrapped stream."""
        return getattr(self._stream, attr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __iter__(self):
        # dunder methods not delegated?
        return self._stream.__iter__()


class Stream(StreamWrapper):
    """Manage file resource."""

    def __init__(self, file, mode, binary, *, on=None):
        """Ensure file is a stream of the right type, open or wrap if necessary."""
        if not file:
            raise ValueError('No file name, path or stream provided.')
        # file is a stream, string or path-like object
        # mode is 'r' or 'w'
        # binary is a boolean; open as binary if true, as text if false
        # on: container to open any new stream on
        mode = mode[:1]
        # don't close externally provided stream
        self._keep_open = not isinstance(file, (str, Path))
        # if a path is provided, open a (binary) stream
        if isinstance(file, (str, Path)):
            if not on:
                file = io.open(file, mode + 'b')
            else:
                file = on.open_binary(file, mode)
        # wrap compression/decompression if needed
        file = open_compressed_stream(file)
        # override gzip's mode values which are numeric
        if mode == 'r' and not file.readable():
            raise ValueError('Expected readable stream, got writable.')
        if mode == 'w' and not file.writable():
            raise ValueError('Expected writable stream, got readable.')
        # check text/binary
        # a text format can be read from/written to a binary stream with a wrapper
        # but vice versa can't be done
        if not is_binary(file) and binary:
            raise ValueError('Expected binary stream, got text stream.')
        if is_binary(file) and not binary:
            file = make_textstream(file)
        self.binary = binary
        self.name = get_stream_name(file)
        super().__init__(file)

    def __getattr__(self, attr):
        """Delegate undefined attributes to wrapped stream."""
        return getattr(self._stream, attr)

    def close(self):
        """Close stream, absorb errors."""
        if not self._keep_open:
            try:
                self._stream.close()
            except EnvironmentError:
                pass


def make_textstream(file, *, encoding=None):
    """Wrap binary stream to create text stream."""
    if not encoding:
        encoding = 'utf-8-sig' if file.readable() else 'utf-8'
    return io.TextIOWrapper(file, encoding=encoding)

def is_binary(stream):
    """Check if stream is binary."""
    if stream.readable():
        # read 0 bytes - the return type will tell us if this is a text or binary stream
        return isinstance(stream.read(0), bytes)
    # write empty bytes - error if text stream
    try:
        stream.write(b'')
    except TypeError:
        return False
    return True

def get_stream_name(stream):
    """Get stream name, if available."""
    try:
        return stream.name
    except AttributeError:
        # not all streams have one (e.g. BytesIO)
        return ''


###################################################################################################
# magic byte sequences

def has_magic(instream, magic):
    """Check if a binary stream matches the given signature."""
    try:
        return instream.peek(len(magic)).startswith(magic)
    except EnvironmentError:
        # e.g. write-only stream
        return False


class MagicRegistry:
    """Registry of file types and their magic sequences."""

    def __init__(self):
        """Set up registry."""
        self._magic = {}
        self._suffixes = {}

    def register(self, *suffixes, magic=b''):
        """Decorator to register class that handles file type."""
        def decorator(klass):
            for suffix in suffixes:
                suffix = self._normalise_suffix(suffix)
                self._suffixes[suffix] = klass
            if magic:
                self._magic[magic] = klass
            return klass
        return decorator

    def _normalise_suffix(self, suffix):
        """Bring suffix to lowercase without dot."""
        if suffix.startswith('.'):
            suffix = suffix[1:]
        return suffix.lower()

    def has_suffix(self, suffix):
        """Suffix is covered."""
        return self._normalise_suffix(suffix) in self._suffixes.keys()

    def identify(self, file):
        """Identify a type from magic sequence on input file."""
        if not file:
            return None
        if isinstance(file, (str, Path)):
            # only use context manager if string provided
            # if we got an open stream we should not close it
            with open_stream(file, 'r', binary=True) as stream:
                return self.identify(stream)
        # can't read magic on write-only file
        if file.readable():
            for magic, klass in self._magic.items():
                if has_magic(file, magic):
                    return klass
        # not readable or no magic, try suffix
        suffix = Path(get_stream_name(file)).suffix
        suffix = self._normalise_suffix(suffix)
        return self._suffixes.get(suffix, None)


###################################################################################################
# compression helpers

compressors = MagicRegistry()
compressors.register('.gz', magic=b'\x1f\x8b')(gzip)
compressors.register('.xz', magic=b'\xFD7zXZ\x00')(lzma)
compressors.register('.bz2', magic=b'BZh')(bz2)

def open_compressed_stream(file):
    """Identify and wrap compressed streams."""
    compressor = compressors.identify(file)
    if not compressor:
        return file
    if file.readable():
        mode = 'r'
    else:
        mode = 'w'
    wrapped = compressor.open(file, mode + 'b')
    # set name of uncompressed stream
    wrapped.name = get_stream_name(file)
    # drop the .gz etc
    try:
        last_suffix = Path(wrapped.name).suffixes[-1]
    except IndexError:
        pass
    else:
        if last_suffix and compressors.has_suffix(last_suffix):
            wrapped.name = wrapped.name[:-len(last_suffix)]
    return wrapped
