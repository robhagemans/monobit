"""
monobit.storage.wrappers.wrappers - base class for single-file wrappers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..magic import FileFormatError
from ..holders import StreamHolder


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
