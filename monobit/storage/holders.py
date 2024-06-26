"""
monobit.storage.holders - base class for stream containers and wrappers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path


class StreamHolder:
    """Container/wrapper base class."""

    # NOTE open() opens a stream, close() closes the container

    def open(self):
        """Get the unwrapped stream. Name, mode are based on wrapper."""
        name = Path(self._wrapped_stream.name).stem
        raise NotImplementedError

    def __enter__(self):
        # we don't support nesting the same archive
        assert self.refcount == 0
        self.refcount += 1
        logging.debug('Entering %r', self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.refcount -= 1
        if exc_type == BrokenPipeError:
            return True
        logging.debug('Exiting %r', self)
        self.close()

    def close(self):
        """Close the archive."""
        self.closed = True
