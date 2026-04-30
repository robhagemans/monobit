"""
monobit.storage.containerformats.directory - filesystem operations

(c) 2021--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import io
import logging
from pathlib import Path
from collections import deque

from ..streams import Stream
from ..base import containers
from ..containers import Container


class Directory(Container):
    """Treat directory tree as a container."""

    def __init__(self, path='', mode='r'):
        """Create directory wrapper."""
        # if empty path, this refers to the whole filesystem
        if not path:
            self._path = Path('/')
        elif isinstance(path, Directory):
            self._path = Path(path._path)
        else:
            self._path = Path(path)
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode == 'w':
            logging.debug('Creating directory `%s`', self._path)
            # exist_ok raises FileExistsError only if the *target* already
            # exists, not the parents
            self._path.mkdir(parents=True, exist_ok=True)
        self._created = set()
        super().__init__(mode, str(self._path))

    def __str__(self):
        """Base directory representation in files."""
        return self.name

    def decode(self, name):
        return self.open(name, mode='r')

    def encode(self, name):
        return self.open(name, mode='w')

    def open(self, name, mode):
        """Open a stream in the directory."""
        # mode in 'r', 'w'
        mode = mode[:1]
        pathname = Path(name)
        if mode == 'w':
            # track which directories we created in case we need to remove them
            paths_to_create = reversed(pathname.parents)
            for path in paths_to_create:
                if (self._path / path).is_dir():
                    continue
                logging.debug("Creating directory '%s'", self._path / path)
                (self._path / path).mkdir()
                self._created.add(path)
        logging.debug("Opening file '%s' for mode '%s'.", name, mode)
        filepath = self._path / pathname
        file = open(filepath, mode + 'b')
        # provide name relative to directory container
        stream = Stream(file, name=str(pathname), mode=mode)
        self._created.add(pathname)
        return stream

    def remove(self, name):
        """Remove a previously created file from the directory."""
        if not name:
            return
        if Path(name) not in self._created:
            return
        filepath = self._path / name
        if not filepath.is_dir():
            filepath.unlink()
        # remove empty dirs leading to removed file
        for path in Path(name).parents:
            if path in self._created:
                try:
                    (self._path / path).rmdir()
                except EnvironmentError:
                    pass

    def is_dir(self, name):
        """Item at `name` is a directory."""
        filepath = self._path / name
        return filepath.is_dir()

    def iter_sub(self, prefix):
        """Iterate over contents of a subpath."""
        return (
            _path.relative_to(self._path)
            for _path in (self._path / prefix).iterdir()
        )
