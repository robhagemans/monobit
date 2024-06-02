"""
monobit.storage.wrappers.wrappers - base class for single-file wrappers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..magic import FileFormatError
from ..holders import StreamHolder
from ..streams import Stream, WrappedWriterStream


class Wrapper(StreamHolder):
    """Base class for single-stream wrappers."""

    def __init__(self, stream, mode='r'):
        if mode not in ('r', 'w'):
            raise ValueError(f"`mode` must be one of 'r' or 'w', not '{mode}'.")
        self.mode = mode
        self.refcount = 0
        self.closed = False
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
        if self.mode == 'r':
            name = Path(self._wrapped_stream.name).stem
            data = self.decode(self._wrapped_stream, **self.decode_kwargs)
            try:
                self._unwrapped_stream = Stream.from_data(data, mode='r', name=name)
            except NotImplementedError:
                raise ValueError(f'Reading from {type(self)} not supported.')
        else:
            outfile = self._wrapped_stream.text
            name = Path(self._wrapped_stream.name).stem
            self._unwrapped_stream = WrappedWriterStream(
                outfile, self.encode, name=name, **self.encode_kwargs
            )
        return self._unwrapped_stream

    def _open_write(self):
        outfile = self._wrapped_stream.text
        name = Path(self._wrapped_stream.name).stem
        return WrappedWriterStream(outfile, self.encode, name=name, **kwargs)

    @staticmethod
    def encode(data, outstream, **kwargs):
        raise NotImplementedError

    @staticmethod
    def decode(instream, **kwargs):
        raise NotImplementedError
