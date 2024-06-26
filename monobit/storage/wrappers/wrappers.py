"""
monobit.storage.wrappers.wrappers - base class for single-file wrappers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging
from pathlib import Path

from ..magic import FileFormatError
from ..holders import StreamHolder
from ..streams import Stream


class Wrapper(StreamHolder):
    """Base class for single-stream wrappers."""

    def __init__(self, stream, mode='r', encode_kwargs=None, decode_kwargs=None):
        if mode not in ('r', 'w'):
            raise ValueError(f"`mode` must be one of 'r' or 'w', not '{mode}'.")
        self.mode = mode
        self.refcount = 0
        self.closed = False
        self.encode_kwargs = encode_kwargs or {}
        self.decode_kwargs = decode_kwargs or {}
        # externally provided - don't close this on our side
        self._wrapped_stream = stream
        # opened by us
        self._unwrapped_stream = None

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"stream='{self._wrapped_stream}' mode='{self.mode}'"
            f"{' [closed]' if self.closed else ''}>"
        )


class FilterWrapper(Wrapper):
    """Simple i/o filter wrapper."""

    decode_kwargs = {}
    encode_kwargs = {}

    def open(self):
        name = Path(self._wrapped_stream.name).stem
        if self.mode == 'r':
            if type(self).decode == FilterWrapper.decode:
                raise ValueError(f'Reading from {type(self)} not supported.')
            data = self.decode(self._wrapped_stream, **self.decode_kwargs)
            self._unwrapped_stream = Stream.from_data(data, mode='r', name=name)
        else:
            if type(self).encode == FilterWrapper.encode:
                raise ValueError(f'Writing to {type(self)} not supported.')
            self._unwrapped_stream = _WrappedWriterStream(
                self._wrapped_stream,
                self.encode, name=name, **self.encode_kwargs
            )
        return self._unwrapped_stream

    @staticmethod
    def encode(data, outstream, **kwargs):
        raise NotImplementedError

    @staticmethod
    def decode(instream, **kwargs):
        raise NotImplementedError


class _WrappedWriterStream(Stream):

    def __init__(self, outfile, write_out, name='', **kwargs):
        self._outfile = outfile
        self._write_out = write_out
        self._write_out_kwargs = kwargs
        stream = io.BytesIO()
        super().__init__(stream, name=name, mode='w')

    def close(self):
        if not self.closed:
            try:
                # write out text buffers
                self.flush()
                data = self._stream.getvalue()
                self._write_out(data, self._outfile, **self._write_out_kwargs)
            except Exception as exc:
                logging.warning(
                    f"Could not write to '{self._outfile.name}': {exc}"
                )
        super().close()
