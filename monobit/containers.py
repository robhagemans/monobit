"""
monobit.containers - file containers

(c) 2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import os
import sys
import logging
import itertools
from contextlib import contextmanager
from zipfile import ZipFile
from pathlib import Path, PurePath, PurePosixPath

from . import streams
from .streams import MagicRegistry


_containers = MagicRegistry()


def open_container(file, mode, binary=True):
    """Open container of the appropriate type."""
    if mode == 'r':
        # handle directories separately - no magic
        if file and isinstance(file, (str, bytes, Path)) and Path(file).is_dir():
            container_type = DirContainer
        else:
            container_type = _containers.identify(file)
        if not container_type:
            raise TypeError('Expected container format, got non-container stream')
    else:
        if file and isinstance(file, (str, bytes, Path)):
            container_type = DirContainer
        elif binary:
            container_type = ZipContainer
        else:
            container_type = TextContainer
    return container_type(file, mode)


def unique_name(container, name, ext):
    """Generate unique name for container file."""
    filename = '{}.{}'.format(name, ext)
    i = 0
    while filename in container:
        i += 1
        filename = '{}.{}.{}'.format(name, i, ext)
    return filename


class Container:
    """Base class for container types."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

    def __contains__(self, name):
        """File exists in container."""
        raise NotImplementedError

    def open_binary(self, name, mode):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def open(self, name, mode, *, encoding=None):
        """Open a stream on the container."""
        stream = self.open_binary(name, mode[:1])
        if mode.endswith('b'):
            return stream
        return streams.make_textstream(stream, encoding=encoding)


class DirContainer(Container):
    """Treat directory tree as a container."""

    def __init__(self, path, mode='r'):
        """Create wrapper."""
        self._path = Path(path)
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode == 'w' and path:
            self._path.mkdir(parents=True, exist_ok=True)

    def open_binary(self, name, mode):
        """Open a stream in the container."""
        # mode in 'rb', 'rt', 'wb', 'wt'
        mode = mode[:1]
        name = Path(name)
        if mode == 'w':
            path = name.parent
            (self._path / path).mkdir(parents=True, exist_ok=True)
        return io.open(self._path / name, mode + 'b')

    def __iter__(self):
        """List contents."""
        return (
            str((Path(_r) / _f).relative_to(self._path))
            for _r, _, _files in os.walk(self._path)
            for _f in _files
        )

    def __contains__(self, name):
        """File exists in container."""
        return (self._path / name).exists()


@_containers.set_magic(b'PK\x03\x04')
class ZipContainer(Container):
    """Zip-file wrapper"""

    def __init__(self, stream_or_name, mode='r'):
        """Create wrapper."""
        # append .zip to zip filename, but leave out of root dir name
        root = ''
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        # use standard streams if none provided
        if not stream_or_name:
            stream_or_name = streams.stdio_stream(mode, binary=True)
        if isinstance(stream_or_name, bytes):
            stream_or_name = stream_or_name.decode('ascii')
        if isinstance(stream_or_name, (str, Path)):
            stream_or_name = root = str(stream_or_name)
            if mode == 'w' and not stream_or_name.endswith('.zip'):
                stream_or_name += '.zip'
        else:
            # try to get stream name. Not all streams have one (e.g. BytesIO)
            try:
                root = stream_or_name.name
            except AttributeError:
                pass
        # if name ends up empty, replace; clip off any dir path and suffix
        root = PurePath(root).stem or 'fontdata'
        # create the zipfile
        self._zip = ZipFile(stream_or_name, mode)
        if mode == 'w':
            # if creating a new container, put everything in a directory inside it
            self._root = root
        else:
            self._root = ''
        self._mode = mode

    def __enter__(self):
        return self

    def _close(self):
        """Close the zip file, ignoring errors."""
        try:
            self._zip.close()
        except EnvironmentError:
            # e.g. BrokenPipeError
            pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type == BrokenPipeError:
            return True
        self._close()

    def __del__(self):
        """Ensure archive is closed and essential records written."""
        try:
            self._close()
        except AttributeError:
            # _zip may already have been destroyed
            pass

    def __iter__(self):
        """List contents."""
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in self._zip.namelist()
        )

    def __contains__(self, name):
        """File exists in container."""
        return name in list(self)

    def open_binary(self, name, mode):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        filename = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        return self._zip.open(filename, mode)


@_containers.set_magic(b'---')
class TextContainer(Container):
    """Container of concatenated text files."""

    separator = b'---'

    def __init__(self, infile, mode='r'):
        """Open stream or create wrapper."""
        # all containers expect binary stream, including TextContainer
        self._stream = streams.open_stream(infile, mode, binary=True)
        self._mode = mode[:1]
        if self._mode == 'r':
            if self._stream.readline().strip() != self.separator:
                raise ValueError('Not a text container.')
        else:
            self._stream.write(b'%s\n' % (self.separator,))

    def __iter__(self):
        """Dummy content lister."""
        for i in itertools.count():
            if self._stream.closed:
                return
            yield str(i)

    def __contains__(self, name):
        return False

    def open_binary(self, name, mode):
        """Open a single stream. Name argument is a dummy."""
        if not mode.startswith(self._mode):
            raise ValueError(f"Cannot open file for '{mode}' on container open for '{self._mode}'")

        parent = self

        class _SubStream:
            """Wrapper object to emulate a single text stream."""

            def __init__(self, stream):
                self._stream = stream
                self.closed = False

            def __iter__(self):
                """Iterate over lines until next separator."""
                for line in self._stream:
                    if line.strip() == parent.separator:
                        return
                    yield line[:-1]
                self._stream.close()

            def __getattr__(self, attr):
                """Delegate undefined attributes to wrapped stream."""
                return getattr(self._stream, attr)

            def close(self):
                self._stream.flush()
                if parent._mode == 'w' and not self.closed:
                    self._stream.write(b'\n%s\n' % (parent.separator, ))
                self.closed = True

            def __del__(self):
                self.close()

        return _SubStream(self._stream)
