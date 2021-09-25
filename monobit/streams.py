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



class FileFormatError(Exception):
    """Incorrect file format."""


def open_stream(file, mode, *, where=None, overwrite=False):
    """Ensure file is a stream of the right type, open or wrap if necessary."""
    return Stream(file, mode, where=where, overwrite=overwrite)


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


class KeepOpen(StreamWrapper):
    """Wrapper to avoid closing wrapped stream."""

    def close(self):
        """Do nothing."""


class Stream(StreamWrapper):
    """Manage file resource."""

    def __init__(self, file, mode, *, where=None, overwrite=False):
        """Ensure file is a stream of the right type, open or wrap if necessary."""
        if not file:
            raise ValueError('No file name, path or stream provided.')
        # file is a stream, string or path-like object
        # mode is 'r' or 'w'
        # binary is a boolean; open as binary if true, as text if false
        # where: container to open any new stream on
        mode = mode[:1]
        self.mode = mode
        # if a path is provided, open a (binary) stream
        if isinstance(file, (str, Path)):
            if not where:
                if not overwrite and mode == 'w' and Path(file).exists():
                    raise FileExistsError(f'Will not overwrite existing file `{file}`.')
                logging.debug("Opening file `%s` for mode '%s'.", file, mode)
                file = io.open(file, mode + 'b')
            else:
                if not overwrite and mode == 'w' and file in where:
                    raise FileExistsError(
                        f'Will not overwrite existing file `{file}` on `{where.name}`.'
                    )
                file = where.open_binary(file, mode)
            self._raw = file
        else:
            # don't close externally provided stream
            file = KeepOpen(file)
            self._raw = None
        # wrap compression/decompression if needed
        file = open_compressed_stream(file)
        # check r/w mode is consistent
        if mode == 'r' and not file.readable():
            raise FileFormatError('Expected readable stream, got writable.')
        if mode == 'w' and not file.writable():
            raise FileFormatError('Expected writable stream, got readable.')
        # check text/binary
        # a text format can be read from/written to a binary stream with a wrapper
        if not is_binary(file):
            self._textstream = file
            try:
                file = file.buffer
            except AttributeError as e:
                raise FileFormatError('Unable to access binary stream.') from e
        else:
            self._textstream = None
        self.name = get_stream_name(file)
        super().__init__(file)

    @property
    def text(self):
        """Return underlying text stream or wrap underlying binary stream with utf-8 wrapper."""
        if not self._textstream:
            encoding = 'utf-8-sig' if self.mode == 'r' else 'utf-8'
            self._textstream = io.TextIOWrapper(self._stream, encoding=encoding)
        return self._textstream

    def __getattr__(self, attr):
        """Delegate undefined attributes to wrapped stream."""
        return getattr(self._stream, attr)

    def close(self):
        """Close stream, absorb errors."""
        # always close at wrapper level
        self.closed = True
        if self._textstream:
            try:
                self._textstream.close()
            except EnvironmentError:
                pass
        try:
            self._stream.close()
        except EnvironmentError:
            pass
        if self._raw:
            try:
                self._raw.close()
            except EnvironmentError:
                pass


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

def normalise_suffix(suffix):
    """Bring suffix to lowercase without dot."""
    if suffix.startswith('.'):
        suffix = suffix[1:]
    return suffix.lower()

def get_suffix(file):
    """Get normalised suffix for file or path."""
    if isinstance(file, (str, Path)):
        suffix = Path(file).suffix
    else:
        suffix = Path(get_stream_name(file)).suffix
    return normalise_suffix(suffix)


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
                suffix = normalise_suffix(suffix)
                self._suffixes[suffix] = klass
            if magic:
                self._magic[magic] = klass
            return klass
        return decorator

    def __contains__(self, suffix):
        """Suffix is covered."""
        return normalise_suffix(suffix) in self._suffixes.keys()

    def identify(self, file, mode):
        """Identify a type from magic sequence on input file."""
        if not file:
            return None
        # can't read magic on write-only file
        if mode == 'r':
            if isinstance(file, (str, Path)):
                # only use context manager if string provided
                # if we got an open stream we should not close it
                with open_stream(file, 'r') as stream:
                    for magic, klass in self._magic.items():
                        if has_magic(stream, magic):
                            return klass
        suffix = get_suffix(file)
        return self._suffixes.get(suffix, None)


###################################################################################################
# compression helpers

compressors = MagicRegistry()
compressors.register('.gz', magic=b'\x1f\x8b')(gzip)
compressors.register('.xz', magic=b'\xFD7zXZ\x00')(lzma)
compressors.register('.bz2', magic=b'BZh')(bz2)

def open_compressed_stream(file):
    """Identify and wrap compressed streams."""
    mode = 'r' if file.readable() else 'w'
    compressor = compressors.identify(file, mode)
    if not compressor:
        return file
    if file.readable():
        mode = 'r'
    else:
        mode = 'w'
    logging.debug("Opening %s-compressed stream for mode '%s'", compressor.__name__, mode)
    wrapped = compressor.open(file, mode + 'b')
    # set name of uncompressed stream
    wrapped.name = get_stream_name(file)
    # drop the .gz etc
    try:
        last_suffix = Path(wrapped.name).suffixes[-1]
    except IndexError:
        pass
    else:
        if last_suffix in compressors:
            wrapped.name = wrapped.name[:-len(last_suffix)]
    return wrapped
