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


def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn


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


class ZipContainer:
    """Zip-file wrapper"""

    def __init__(self, stream, mode='r'):
        """Create wrapper."""
        self._mode = mode
        self._zip = ZipFile(stream, mode)

    def __enter__(self):
        return self

    def __exit__(self, one, two, three):
        self._zip.close()

    def open(self, name, mode):
        """Open a stream in the container."""
        if mode.endswith('b'):
            return self._zip.open(name, mode[:-1])
        else:
            stream = self._zip.open(name, mode)
            if mode == 'r':
                encoding = 'utf-8-sig'
            else:
                encoding = 'utf-8'
            return io.TextIOWrapper(stream, encoding)

    def namelist(self):
        """List contents."""
        return self._zip.namelist()


class DirContainer:
    """Treat directory tree as a container."""

    def __init__(self, path, mode='r'):
        """Create wrapper."""
        self._path = path
        if mode == 'w':
            try:
                os.makedirs(path)
            except EnvironmentError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, one, two, three):
        pass

    def open(self, name, mode):
        """Open a stream in the container."""
        if mode.startswith('w'):
            path = os.path.dirname(name)
            try:
                os.makedirs(os.path.join(self._path, path))
            except EnvironmentError:
                pass
        return open(os.path.join(self._path, name), mode)

    def namelist(self):
        """List contents."""
        return [
            os.path.join(_r, _f)[len(self._path):]
            for _r, _, _files in os.walk(self._path)
            for _f in _files
        ]
