"""
monobit.storage.wrappers.offset - binary files at offset in binary files

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from ..base import wrappers
from .wrappers import Wrapper
from ..streams import Stream


@wrappers.register(
    name='offset',
)
class OffsetWrapper(Wrapper):
    """Binary offset wrapper."""

    def __init__(
            self, stream, mode='r',
            *,
            offset:int=0,
        ):
        """
        Binary file at an offset in another binary file.

        offset: offset to use, in bytes.
        """
        super().__init__(stream, mode)
        self._wrapped_stream.read(offset)
        # Stream wrapper will drop a seek() anchor
        self._unwrapped_stream = Stream(self._wrapped_stream, mode)

    def open(self):
        return self._unwrapped_stream
