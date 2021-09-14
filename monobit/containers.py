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
import itertools
from contextlib import contextmanager
from zipfile import ZipFile
from pathlib import Path

from . import streams


def unique_name(container, name, ext):
    """Generate unique name for container file."""
    filename = '{}.{}'.format(name, ext)
    i = 0
    while filename in container:
        i += 1
        filename = '{}.{}.{}'.format(name, i, ext)
    return filename


def identify_container(infile):
    """Recognise container type and return container object."""
    if isinstance(infile, (str, bytes, Path)):
        # string provided
        if Path(infile).is_dir():
            return DirContainer
        else:
            with streams.open(io, infile, 'r', binary=True) as instream:
                return identify_container(instream)
    # stream provided
    if streams.has_magic(infile, ZipContainer.magic):
        return ZipContainer
    elif streams.has_magic(infile, TextMultiStream.magic):
        return TextMultiStream
    return None


class ZipContainer:
    """Zip-file wrapper"""

    magic = b'PK\x03\x04'

    def __init__(self, stream_or_name, mode='r'):
        """Create wrapper."""
        # append .zip to zip filename, but leave out of root dir name
        name = ''
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if isinstance(stream_or_name, (str, bytes)):
            name = stream_or_name
            if mode == 'w' and not stream_or_name.endswith('.zip'):
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
        binary = mode.endswith('b')
        mode = mode[:1]
        stream = self._zip.open(filename, mode)
        if binary:
            return stream
        else:
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
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
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
        # mode in 'rb', 'rt', 'wb', 'wt'
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


class TextMultiStream:
    """Container of concatenated text files. This is a bit hacky."""

    separator = b'---'
    magic = separator

    def __init__(self, infile, mode='r'):
        """Open stream or create wrapper."""
        if isinstance(infile, (str, bytes, Path)):
            # all containers expect binary stream, including TextMultiStream
            self._stream = open(io, infile, 'rb')
        else:
            self._stream = infile
        self.closed = False
        self._mode = mode[:1]
        if self._mode == 'r':
            if self._stream.readline().strip() != self.separator:
                raise ValueError('Not a text multistream.')
        else:
            self._stream.write(b'%s\n' % (self.separator,))

    def __iter__(self):
        """Dummy content lister."""
        for i in itertools.count():
            if self.closed or self._stream.closed:
                return
            yield str(i)

    def __contains__(self, name):
        return False

    def __enter__(self):
        return self

    def __exit__(self, one, two, three):
        pass

    @contextmanager
    def open(self, name, mode, encoding=None):
        """Open a single stream. Name argument is a dummy."""
        if not mode.startswith(self._mode):
            raise ValueError('File and container read/write mode must match.')
        if mode.endswith('b'):
            raise('Cannot open binary file on text container.')

        class _TextStream:
            """Wrapper object to emulate a single text stream."""

            def __init__(self, parent, stream):
                self._stream = stream
                self._stream.close = lambda: None
                self._parent = parent

            def __iter__(self):
                """Iterate over lines until next separator."""
                for line in self._stream:
                    if line.strip() == self._parent.separator.decode('ascii'):
                        return
                    yield line[:-1]
                self._parent.closed = True

            def write(self, s):
                """Write to stream."""
                self._stream.write(s)

        encoding = encoding or 'utf-8'
        textstream = io.TextIOWrapper(self._stream, encoding=encoding)
        yield _TextStream(self, textstream)
        textstream.flush()
        if self._mode == 'w':
            self._stream.write(b'\n%s\n' % (self.separator, ))
