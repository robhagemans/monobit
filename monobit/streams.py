"""
monobit.formats - loader and saver plugin registry

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import gzip
import io
import sys
import logging
from pathlib import Path


def open(on, path, mode, binary):
    """Open a binary or encoded text stream on a container or the filesystem."""
    # on: container / can be anything that provides an open() method with a signature like io.open
    # path is a path-like object
    # mode is 'r' or 'w'
    # binary is a boolean; open as binary if true, as text if false
    path = Path(path)
    if path.suffix == '.gz':
        # open the compressed stream on any container
        # gzip.open accepts an open stream in its path argument
        path = on.open(path, mode + 'b')
        on = gzip
    if not binary:
        encoding = 'utf-8-sig' if mode == 'r' else 'utf-8'
        # 'r' is text for io but binary for gzip - 'rt' is always text
        return on.open(path, mode + 't', encoding=encoding)
    else:
        return on.open(path, mode + 'b')

def is_binary(instream):
    """Check if stream is binary."""
    # read 0 bytes - the return type will tell us if this is a text or binary stream
    return isinstance(instream.read(0), bytes)

def has_magic(instream, magic):
    """Check if a binary stream matches the given signature."""
    return instream.peek(len(magic)).startswith(magic)
