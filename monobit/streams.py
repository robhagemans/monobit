"""
monobit.streams - file stream tools

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import logging
from pathlib import Path



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
                raise FileExistsError(
                    f'Use option `-overwrite` to replace existing file `{file}`.'
                )
            logging.debug("Opening file `%s` for mode '%s'.", file, mode)
            file = io.open(path, mode + 'b')
        else:
            # open on container
            if not overwrite and mode == 'w' and file in where:
                raise FileExistsError(
                    f'Use option `-overwrite` to replace existing file `{file}` on `{where.name}`.'
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
            self._textstream = io.TextIOWrapper(
                self._stream, encoding=encoding,
                # on the one hand, this avoids breaks on slightly damaged files
                # on the other hand, we are less likely to break
                # on files that are clearly not text
                errors='ignore'
            )
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
