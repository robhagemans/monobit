"""
monobit.storage.wrappers.wraper - single-file wrapper base class

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from contextlib import contextmanager
from importlib import import_module

from ..streams import Stream
from ..magic import FileFormatError
from ..base import wrappers



class Wrapper:
    """Container/wrapper base class."""

    def __init__(self, stream, mode='r'):
        self.mode = mode
        if mode not in ('r', 'w'):
            raise ValueError(f"`mode` must be one of 'r' or 'w', not '{mode}'.")
        self.refcount = 0
        self.closed = False
        # externally provided - don't close this on our side
        self._wrapped_stream = stream
        # opened by us
        self._unwrapped_stream = None

    # NOTE open() opens a stream, close() closes the container

    def open(self):
        """Get the unwrapped stream. Name, mode are based on wrapper."""
        name = Path(self._wrapped_stream.name).stem
        raise NotImplementedError

    def __enter__(self):
        # we don't support nesting the same archive
        assert self.refcount == 0
        self.refcount += 1
        logging.debug('Entering archive %r', self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.refcount -= 1
        if exc_type == BrokenPipeError:
            return True
        logging.debug('Exiting archive %r', self)
        self.close()

    def close(self):
        """Close the archive."""
        self.closed = True
