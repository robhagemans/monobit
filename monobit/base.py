"""
monobit.base - shared utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import os
import sys
import logging
import posixpath
from contextlib import contextmanager
from zipfile import ZipFile


DEFAULT_FORMAT = 'text'
VERSION = '0.8'


def scriptable(fn):
    """Decorator to register operation for scripting."""
    fn.scriptable = True
    fn.script_args = fn.__annotations__
    return fn


class ZipContainer:
    """Zip-file wrapper"""

    def __init__(self, stream_or_name, mode='r'):
        """Create wrapper."""
        # append .zip to zip filename, but leave out of root dir name
        name = ''
        if isinstance(stream_or_name, (str, bytes)):
            name = stream_or_name
            if not stream_or_name.endswith('.zip'):
                stream_or_name += '.zip'
        else:
            # try to get stream name. Not all streams have one (e.g. BytesIO)
            try:
                name = stream_or_name.name
            except AttributeError:
                pass
        # if name ends up empty, replace
        name = os.path.basename(name or 'fontdata')
        if name.endswith('.zip'):
            name = name[:-4]
        # create the zipfile
        self._zip = ZipFile(stream_or_name, mode)
        if mode == 'w':
            # if creating a new container, put everything in a directory inside it
            self._root = name
        else:
            self._root = ''
        self._mode = mode

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type == BrokenPipeError:
            return True
        try:
            self._zip.close()
        except EnvironmentError:
            pass

    def open(self, name, mode, encoding=None):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        filename = posixpath.join(self._root, name)
        if mode.endswith('b'):
            return self._zip.open(filename, mode[:-1])
        else:
            stream = self._zip.open(filename, mode)
            if mode == 'r':
                encoding = encoding or 'utf-8-sig'
            else:
                encoding = encoding or 'utf-8'
            return io.TextIOWrapper(stream, encoding)

    def __iter__(self):
        """List contents."""
        return (
            posixpath.relpath(_name, self._root)
            for _name in self._zip.namelist()
        )

    def __contains__(self, name):
        """File exists in container."""
        return name in list(self)


class DirContainer:
    """Treat directory tree as a container."""

    def __init__(self, path, mode='r'):
        """Create wrapper."""
        self._path = path
        if mode == 'w' and path:
            try:
                os.makedirs(path)
            except EnvironmentError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, one, two, three):
        pass

    def open(self, name, mode, encoding=None):
        """Open a stream in the container."""
        if mode.startswith('w'):
            path = os.path.dirname(name)
            try:
                os.makedirs(os.path.join(self._path, path))
            except EnvironmentError:
                pass
        return open(os.path.join(self._path, name), mode, encoding=encoding)

    def __iter__(self):
        """List contents."""
        return (
            os.path.relpath(os.path.join(_r, _f), self._path)
            for _r, _, _files in os.walk(self._path)
            for _f in _files
        )

    def __contains__(self, name):
        """File exists in container."""
        return os.path.exists(os.path.join(self._path, name))
