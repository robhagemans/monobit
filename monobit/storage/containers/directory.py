"""
monobit.storage.containers.directory - directory traversal

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import io
import logging
from pathlib import Path
from collections import deque

from ..streams import Stream
from ..base import containers
from .containers import Container


@containers.register(name='dir')
class Directory(Container):
    """Treat directory tree as a container."""

    def __init__(self, path='', mode='r', ignore_case:bool=True):
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
        super().__init__(mode, str(self._path), ignore_case=ignore_case)

    def __repr__(self):
        return f"{type(self).__name__}('{self._path}')"

    def open(self, name, mode, overwrite=False):
        """Open a stream in the directory."""
        # mode in 'r', 'w'
        mode = mode[:1]
        pathname = Path(name)
        if mode == 'w':
            path = pathname.parent
            logging.debug('Creating directory `%s`', self._path / path)
            (self._path / path).mkdir(parents=True, exist_ok=True)
        logging.debug("Opening file `%s` for mode '%s'.", name, mode)
        filepath = self._path / pathname
        if mode == 'w' and not overwrite and filepath.exists():
            raise ValueError(
                f'Overwriting existing file {str(filepath)}'
                ' requires -overwrite to be set'
            )
        if filepath.is_dir():
            raise IsADirectoryError(
                f"Cannot open stream on '{filepath}': is a directory."
            )
        try:
            file = open(filepath, mode + 'b')
        except FileNotFoundError:
            # match_name will raise FileNotFoundError if no match
            if not self._ignore_case:
                raise
            filepath = self._match_case_insensitive(filepath)
            file = open(filepath, mode + 'b')
        # provide name relative to directory container
        stream = Stream(file, name=str(pathname), mode=mode)
        return stream

    def is_dir(self, name):
        """Item at `name` is a directory."""
        filepath = self._path / name
        return filepath.is_dir()

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        return (
            _path.relative_to(self._path)
            for _path in (self._path / prefix).iterdir()
        )

    def _match_case_insensitive(self, path):
        """Stepwise match per path element."""
        segments = Path(path).as_posix().split('/')
        segments = deque(segments)
        matched_path = Path('.')
        while True:
            target = segments.popleft()
            for name in self.iter_sub(matched_path):
                if str(target).lower() == name.name.lower():
                    matched_path /= name.name
                    if not segments:
                        return matched_path
                    if self.is_dir(matched_path):
                        break
            else:
                raise FileNotFoundError(f"'{path}' not found on {self}.")

    def contains(self, name):
        """File exists in container."""
        if (self._path / name).exists():
            return True
        if not self._ignore_case:
            return False
        try:
            self._match_case_insensitive(name)
        except FileNotFoundError:
            return False
        return True
