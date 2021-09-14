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
from contextlib import contextmanager


def open(path, mode, binary, *, on=None):
    """Open a binary or encoded text stream on a container or the filesystem."""
    # path is a path-like object
    # mode is 'r' or 'w'
    # binary is a boolean; open as binary if true, as text if false
    # on: container / can be anything that provides an open() method with a signature like io.open
    # nameless stream on filesystem -> stdio
    if on is None:
        if not path:
            return stdio_stream(mode, binary)
        on = io
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


@contextmanager
def make_stream(file, mode, binary):
    # if a path is provided, open a stream
    if not file or isinstance(file, (str, bytes, Path)):
        with open(file, mode, binary) as instream:
            yield instream
    # check text/binary
    # a text format can be read from/written to a binary stream with a wrapper
    # but vice versa can't be done
    elif is_binary(file):
        if not binary:
            encoding = 'utf-8-sig' if mode == 'r' else 'utf-8'
            with io.TextIOWrapper(file, encoding=encoding) as text_stream:
                yield text_stream
    elif binary:
        raise ValueError('Encountered text stream while expecting binary stream.')
    elif not file.mode.startswith(mode):
        raise ValueError(
            f"Encountered stream of mode '{file.mode}' while expecting '{mode}'."
        )
    else:
        yield file


def stdio_stream(mode, binary):
    """Get standard stream for given mode and text/binary type."""
    if mode == 'w':
        if binary:
            return sys.stdout.buffer
        return sys.stdout
    if binary:
        return sys.stdin.buffer
    return sys.stdin

def is_binary(instream):
    """Check if readable stream is binary."""
    if instream.mode.startswith('r'):
        # read 0 bytes - the return type will tell us if this is a text or binary stream
        return isinstance(instream.read(0), bytes)
    # write empty bytes - error if text stream
    try:
        instream.write(b'')
    except TypeError:
        return False
    return True

def has_magic(instream, magic):
    """Check if a binary stream matches the given signature."""
    return instream.peek(len(magic)).startswith(magic)
