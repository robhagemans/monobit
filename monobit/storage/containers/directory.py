"""
monobit.storage.containers.directory - directory traversal

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import io
import logging
from pathlib import Path

from ..streams import Stream
from ..holders import Container, find_case_insensitive
from ..base import containers


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
            filepath = self._path / self._match_name(name)
            file = open(filepath, mode + 'b')
        # provide name relative to directory container
        stream = Stream(file, name=str(pathname), mode=mode, where=self)
        return stream

    def is_dir(self, name):
        """Item at `name` is a directory."""
        filepath = self._path / name
        return filepath.is_dir()

    def __iter__(self):
        """List contents."""
        if not self._path:
            raise ValueError('Will not walk over whole filesystem.')
        return self.iter_sub('')

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        return (
            str((Path(_r) / _f).relative_to(self._path))
            for _r, _, _files in os.walk(self._path / prefix)
            for _f in _files
        )

    def __contains__(self, name):
        """File exists in container."""
        if (self._path / name).exists():
            return True
        if not self._ignore_case:
            return False
        segments = Path(name).as_posix().split('/')
        target = self._path
        for segment in segments:
            if not target.is_dir():
                break
            match = find_case_insensitive(target / segment, target.iterdir())
            if match is None:
                return False
            target = match
        else:
            # no break in loop - last segemnt was matched
            return True
        return False

    def __repr__(self):
        return f"{type(self).__name__}('{self._path}')"
