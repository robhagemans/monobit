"""
monobit.streams - file stream tools

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import os
import sys
import logging
from pathlib import Path


def get_bytesio(bytestring):
    """Workaround as our streams objects require a buffer."""
    return io.BufferedReader(io.BytesIO(bytestring))

def get_stringio(string):
    """Workaround as our streams objects require a buffer."""
    return io.TextIOWrapper(get_bytesio(string.encode()))


class StreamBase:
    """Base class for streams."""

    def __init__(self, stream, mode='', name='', where=None):
        self._stream = stream
        self.name = name
        self.mode = mode[:1]
        if self._stream:
            if not self.name:
                self.name = get_name(stream)
            if not self.mode:
                try:
                    self.mode = self._stream.mode[:1]
                except AttributeError:
                    if self._stream.readable():
                        self.mode = 'r'
                    else:
                        self.mode = 'w'
        self._refcount = 0
        # embedding container
        self.where = where
        self.closed = False

    def __enter__(self):
        self._refcount += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensure stream is closed."""
        if exc_type == BrokenPipeError:
            return True
        self._refcount -= 1
        logging.debug(
            'Exiting %r with reference count %d. '
            '[Underlying stream %r]', self, self._refcount, self._stream)
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
            logging.debug('Closing %r', self)
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

    def __init__(self, file, mode, *, name='', where=None):
        """
        Ensure file is a stream of the right type, open or wrap if necessary.

        file: stream or file-like object
        mode: 'r' or 'w'
        where: embedding container
        """
        if not file:
            raise ValueError('No stream provided.')
        mode = mode[:1]
        if isinstance(file, (str, Path)):
            raise ValueError('Argument `file` must be a Python file or stream-like object.')
        # initialise wrapper
        super().__init__(file, mode=mode, name=name, where=where)
        # check r/w mode is consistent
        self._ensure_rw()
        # Ensure we have a binary stream
        self._ensure_binary()
        if mode == 'r' and not self._stream.seekable():
            # we need streams to be seekable - drain to buffer
            # note you can only do this once on the input stream!
            self._stream = get_bytesio(self._stream.read())
            self._ensure_binary()
        if mode == 'r':
            self._anchor = self._stream.tell()
        else:
            self._anchor = 0

    @classmethod
    def from_data(cls, data, **kwargs):
        """BytesIO stream on bytes data."""
        # Stream requires a buffer so we wrap
        return cls(get_bytesio(data), **kwargs)

    @classmethod
    def from_string(cls, text, **kwargs):
        """StringIO stream on string data."""
        return cls.from_data(text.encode(), **kwargs)

    def _ensure_rw(self):
        """Ensure r/w mode is consistent."""
        if self.mode == 'r' and not self._stream.readable():
            raise ValueError('Expected readable stream, got writable.')
        if self.mode == 'w' and not self._stream.writable():
            raise ValueError('Expected writable stream, got readable.')

    def _ensure_binary(self):
        """Ensure we have a binary stream."""
        # a text format can be read from/written to a binary stream with a wrapper
        if not is_binary(self._stream):
            self._textstream = self._stream
            try:
                self._stream = self._stream.buffer
            except AttributeError as e:
                raise ValueError('Unable to access binary stream.') from e
            logging.debug('Getting buffer %r from text stream %r.', self._stream, self._textstream)
        else:
            # placeholder for text wrapper
            self._textstream = None

    @property
    def text(self):
        """Return underlying text stream or wrap underlying binary stream with utf-8 wrapper."""
        if not self._textstream:
            encoding = 'utf-8-sig' if self.mode == 'r' else 'utf-8'
            self._textstream = io.TextIOWrapper(
                self._stream, encoding=encoding,
                # on the one hand, this avoids breaks on slightly damaged files
                # on the other hand, we are less likely to break
                # on files that are clearly not text
                errors='ignore'
            )
        return self._textstream

    def seek(self, loc, whence=0, /):
        """Seek relative to anchor."""
        if whence == 0:
            loc += self._anchor
        self._stream.seek(loc, whence)

    def tell(self):
        """Location relative to anchor."""
        return self._stream.tell() - self._anchor

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


class DirectoryStream(Stream):
    """Fake stream to represent directory."""

    def __init__(self, file, mode, *, name='', where=None):
        name = name or str(file)
        mode = mode[:1]
        if isinstance(file, DirectoryStream):
            file = file.name
        if not isinstance(file, (str, Path)):
            raise TypeError(
                'DirectoryStream initialiser must be DirectoryStream, Path or str.'
            )
        # path is what should be used to open the actual directory
        self.path = Path(file)
        dummystream = open(os.devnull, mode + 'b')
        # initialise wrapper
        super().__init__(dummystream, mode=mode, name=name, where=where)


###############################################################################

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
