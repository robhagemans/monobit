"""
monobit.streams - file stream tools

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import logging
from pathlib import Path


class FileFormatError(Exception):
    """Incorrect file format."""


def open_stream(file, mode, *, where=None, overwrite=False):
    """Ensure file is a stream of the right type, open or wrap if necessary."""
    return Stream(file, mode, where=where, overwrite=overwrite)


class StreamBase:
    """Shared base for stream and container."""

    def __init__(self, stream, mode='', name=''):
        self._stream = stream
        self.name = name
        self.mode = mode[:1]
        if self._stream:
            if not self.name:
                self.name = get_name(stream)
            if not self.mode:
                if self._stream.readable():
                    self.mode = 'r'
                else:
                    self.mode = 'w'
        self._refcount = 0
        self.closed = False

    def __enter__(self):
        self._refcount += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensure archive is closed and essential records written."""
        if exc_type == BrokenPipeError:
            return True
        self._refcount -= 1
        logging.debug('Exiting %r with reference count %d.', self, self._refcount)
        if not self._refcount:
            self.close()

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} name='{self.name}' mode='{self.mode}'"
            f"{' [closed]' if self.closed else ''}>"
        )

    def close(self):
        if self._stream and not self._refcount:
            self._stream.close()
        self.closed = True


class StreamWrapper(StreamBase):
    """Wrapper object to emulate a single text stream."""

    def __getattr__(self, attr):
        """Delegate undefined attributes to wrapped stream."""
        return getattr(self._stream, attr)

    def __iter__(self):
        # dunder methods not delegated
        return self._stream.__iter__()


class KeepOpen(StreamWrapper):
    """Wrapper to avoid closing wrapped stream."""

    def close(self):
        """Don't close underlying stream."""
        self._stream.flush()


class Stream(StreamWrapper):
    """Manage file resource."""

    def __init__(self, file, mode, *, name='', where=None, overwrite=False):
        """
        Ensure file is a stream of the right type, open or wrap if necessary.
            file: stream, string or path-like object
            mode: 'r' or 'w'
            where: container to open any new stream on
        """
        if not file:
            raise ValueError('No file name, path or stream provided.')
        mode = mode[:1]
        # if a path is provided, open a (binary) stream
        if isinstance(file, (str, Path)):
            file = self._open_path(file, mode, where, overwrite)
            self._raw = file
        else:
            # don't close externally provided stream
            file = KeepOpen(file)
            self._raw = None
        # initialise wrapper
        super().__init__(file, mode=mode, name=name)
        # check r/w mode is consistent
        self._ensure_rw()
        # placeholder for text wrapper
        self._textstream = None
        # Ensure we have a binary stream
        self._ensure_binary()

    @staticmethod
    def _open_path(file, mode, where, overwrite):
        """Open a raw stream on path and container provided."""
        path = Path(file)
        if not where:
            # open on filesystem
            if not overwrite and mode == 'w' and path.exists():
                raise FileExistsError(f'Will not overwrite existing file `{file}`.')
            logging.debug("Opening file `%s` for mode '%s'.", file, mode)
            file = io.open(path, mode + 'b')
        else:
            # open on container
            if not overwrite and mode == 'w' and file in where:
                raise FileExistsError(
                    f'Will not overwrite existing file `{file}` on `{where.name}`.'
                )
            file = where.open(path, mode)
        return file

    def _ensure_rw(self):
        """Ensure r/w mode is consistent."""
        if self.mode == 'r' and not self._stream.readable():
            raise FileFormatError('Expected readable stream, got writable.')
        if self.mode == 'w' and not self._stream.writable():
            raise FileFormatError('Expected writable stream, got readable.')

    def _ensure_binary(self):
        """Ensure we have a binary stream."""
        # a text format can be read from/written to a binary stream with a wrapper
        if not is_binary(self._stream):
            self._textstream = self._stream
            try:
                self._stream = self._stream.buffer
            except AttributeError as e:
                raise FileFormatError('Unable to access binary stream.') from e
            logging.debug('Getting buffer %r from text stream %r.', self._stream, self._textstream)

    @property
    def text(self):
        """Return underlying text stream or wrap underlying binary stream with utf-8 wrapper."""
        if not self._textstream:
            encoding = 'utf-8-sig' if self.mode == 'r' else 'utf-8'
            self._textstream = io.TextIOWrapper(self._stream, encoding=encoding, errors='ignore')
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
            super().close()
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

def get_name(stream):
    """Get stream name, if available."""
    try:
        return stream.name
    except AttributeError:
        # not all streams have one (e.g. BytesIO)
        return ''


###################################################################################################
# recognise file types

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
        suffix = Path(get_name(file)).suffix
    return normalise_suffix(suffix)

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

    def register(self, *suffixes, magic=()):
        """Decorator to register class that handles file type."""
        def decorator(klass):
            for suffix in suffixes:
                suffix = normalise_suffix(suffix)
                self._suffixes[suffix] = klass
            for sequence in magic:
                self._magic[sequence] = klass
            # use first suffix given as standard
            if suffixes:
                klass.format = normalise_suffix(suffixes[0])
            return klass
        return decorator

    def __contains__(self, suffix):
        """Suffix is covered."""
        return normalise_suffix(suffix) in self._suffixes.keys()

    def __getitem__(self, suffix):
        """Get type by suffix."""
        return self._suffixes.get(suffix, None)

    def identify(self, file, do_open=False):
        """Identify a type from magic sequence on input file."""
        if not file:
            return None
        # can't read magic on write-only file
        if do_open:
            if isinstance(file, (str, Path)):
                # only use context manager if string provided
                # if we got an open stream we should not close it
                with open_stream(file, 'r') as stream:
                    return self.identify(stream, do_open=do_open)
            for magic, klass in self._magic.items():
                if has_magic(file, magic):
                    return klass
        suffix = get_suffix(file)
        return self[suffix]
