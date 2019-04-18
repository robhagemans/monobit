"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from contextlib import contextmanager


@contextmanager
def ensure_stream(infile, mode):
    """If argument is a string, open as file."""
    if isinstance(infile, str) or isinstance(infile, bytes):
        instream = open(infile, mode)
    else:
        instream = infile
    with instream:
        yield instream
