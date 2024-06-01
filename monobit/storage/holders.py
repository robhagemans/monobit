"""
monobit.storage.holders - base class for stream containers and wrappers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from .magic import FileFormatError


class StreamHolder:
    """Container/wrapper base class."""

    # NOTE open() opens a stream, close() closes the container

    def open(self):
        """Get the unwrapped stream. Name, mode are based on wrapper."""
        name = Path(self._wrapped_stream.name).stem
        raise NotImplementedError

    def __enter__(self):
        # we don't support nesting the same archive
        assert self.refcount == 0
        self.refcount += 1
        logging.debug('Entering %r', self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.refcount -= 1
        if exc_type == BrokenPipeError:
            return True
        logging.debug('Exiting %r', self)
        self.close()

    def close(self):
        """Close the archive."""
        self.closed = True


class Wrapper(StreamHolder):
    """Base class for single-stream wrappers."""

    def __init__(self, stream, mode='r'):
        if mode not in ('r', 'w'):
            raise ValueError(f"`mode` must be one of 'r' or 'w', not '{mode}'.")
        self.mode = mode
        self.refcount = 0
        self.closed = False
        # externally provided - don't close this on our side
        self._wrapped_stream = stream
        # opened by us
        self._unwrapped_stream = None

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"stream='{self._wrapped_stream}' mode='{self.mode}'"
            f"{' [closed]' if self.closed else ''}>"
        )


class Container(StreamHolder):
    """Base class for multi-stream containers."""

    def __init__(self, mode='r', name='', ignore_case:bool=False):
        self.mode = mode[:1]
        self.name = name
        self.refcount = 0
        self.closed = False
        # ignore case on read - open any case insensitive match
        # case sensitivity of writing depends on file system
        self._ignore_case = ignore_case

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"mode='{self.mode}' name='{self.name}'"
            f"{' [closed]' if self.closed else ''}>"
        )

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        raise NotImplementedError()

    def contains(self, item):
        """Check if file is in container. Case sensitive if container/fs is."""
        raise NotImplementedError()

    # NOTE open() opens a stream, close() closes the container

    def open(self, name, mode, overwrite=False):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def is_dir(self, name):
        """Item at `name` is a directory."""
        raise NotImplementedError

    def unused_name(self, name):
        """Generate unique name for container file."""
        if not self.contains(name):
            return name
        stem, _, suffix = name.rpartition('.')
        for i in itertools.count():
            filename = '{}.{}'.format(stem, i)
            if suffix:
                filename = '{}.{}'.format(filename, suffix)
            if not self.contains(filename):
                return filename


def match_case_insensitive(filepath, iterator):
    """Find case insensitive match."""
    for name in iterator:
        if str(name).lower() == str(filepath).lower():
            return name
    raise FileNotFoundError(filepath)


class Archive(Container):

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        return (
            str(Path(_name).relative_to(self._root)) for _name in self.list()
            if Path(_name).parent == Path(self._root) / prefix
        )

    def contains(self, item):
        """Check if file is in container. Case sensitive if container/fs is."""
        if self._ignore_case:
            return (
                str(Path(self._root) / item).lower() in
                (str(_item).lower() for _item in self.list())
            )
        else:
            return str(item) in self.list()

    def list(self):
        """List full contents of archive."""
        raise NotImplementedError()
