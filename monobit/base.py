"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import os
import sys
import logging
from contextlib import contextmanager
from zipfile import ZipFile


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

def zip_streams(outfile, sequence, ext='', encoding=None):
    """Generate streams that write to zip container."""
    if isinstance(outfile, str):
        if outfile:
            name = os.path.basename(outfile)
            outfile += '.zip'
        else:
            name = ''
    else:
        name = os.path.basename(outfile.name)
    if '.' in name:
        ext = name.split('.')[-1]
    if not ext:
        ext = 'fontdata'
    with ensure_stream(outfile, 'w', encoding=None) as outstream:
        names_used = []
        with ZipFile(outstream, 'w') as zipfile:
            for i, item in enumerate(sequence):
                if encoding is None:
                    singlestream = io.BytesIO()
                else:
                    singlestream = io.StringIO()
                filename = '{}.{}'.format(item.name.replace(' ', '_'), ext)
                if filename in names_used:
                    filename = '{}.{}.{}'.format(item.name.replace(' ', '_'), i, ext)
                names_used.append(filename)
                singlestream.name = filename
                yield item, singlestream
                if encoding is None:
                    data = singlestream.getvalue()
                else:
                    data = singlestream.getvalue().encode(encoding)
                if data:
                    zipfile.writestr(filename, data)

def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn
