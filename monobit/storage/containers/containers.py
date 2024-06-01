"""
monobit.storage.containers.containers - base classes for containers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..magic import FileFormatError
from ..streams import Stream
from ..holders import StreamHolder


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
    """Base class for multi-file archives."""

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



class MacFork(Archive):
    """Base class for Macintosh forks (2-stream containers)."""

    forknames = ('rsrc', 'data')

    def __init__(self, file, mode='r', name=''):
        if mode != 'r':
            raise ValueError('Writing onto Mac forks is not supported.')
        super().__init__(mode, name)
        with Stream(file, mode) as stream:
            self.name, *forks = self._parse(stream)
        self.forks = dict(zip(self.forknames, forks))

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        self._check_name(prefix)
        if Path(prefix) != Path('.'):
            raise NotADirectoryError(f"'{prefix}' is not a directory.")
        return iter(self.forknames)

    def open(self, name, mode, overwrite=False):
        """Open a binary stream in the container."""
        if mode != 'r':
            raise ValueError('Writing onto Mac forks is not supported.')
        if self.is_dir(name):
            raise IsADirectoryError(f"'name' is a directory.")
        fork = self.forks[str(name)]
        return Stream.from_data(fork, mode='r', name=f'{self.name/name}')

    def is_dir(self, name):
        """Item at `name` is a directory."""
        self._check_name(name)
        return Path(name) == Path('.')

    def list(self):
        """List full contents of archive."""
        return self.forknames

    def _check_name(self, name):
        if Path(name) != Path('.') and str(name) not in self.forks:
            raise FileNotFoundError(
                f"Mac container only contains {self.forknames}, not '{name}'."
            )

    def _parse(self, instream):
        """Resource and data fork loader."""
        raise NotImplementedError()
