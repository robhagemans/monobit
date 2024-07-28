"""
monobit.storage.wrappers.offset - binary files at offset in binary files

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from ..base import decoders
from ..streams import Stream


@decoders.register(
    name='offset',
)
def decode_offset(stream, *, offset:int=0):
    """
    Binary file at an offset in another binary file.

    offset: offset to use, in bytes.
    """
    stream.read(offset)
    # Stream wrapper will drop a seek() anchor
    return Stream(stream, mode=stream.mode, name=stream.name)
