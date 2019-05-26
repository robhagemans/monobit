"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
from contextlib import contextmanager


DEFAULT_FORMAT = 'text'
VERSION = '0.8'


@contextmanager
def ensure_stream(infile, mode, encoding=None):
    """
    If argument is a string, open as file.
    Mode should be 'w' or 'r'. For binary, use encoding=None
    """
    if not infile:
        if mode.startswith('w'):
            instream = sys.stdout.buffer
        else:
            instream = sys.stdin.buffer
        # we take encoding == None to mean binary
        if encoding:
            instream = io.TextIOWrapper(instream, encoding=encoding)
    elif isinstance(infile, (str, bytes)):
        if encoding:
            instream = open(infile, mode, encoding=encoding)
        else:
            instream = open(infile, mode + 'b')
    else:
        instream = infile
    try:
        with instream:
            yield instream
    except BrokenPipeError:
        # ignore broken pipes
        pass

def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn
