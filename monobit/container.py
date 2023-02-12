"""
monobit.container - directory and base class for archives

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging
import itertools
from pathlib import Path

from .streams import Stream


class Container:
    """Base class for container types."""

    def __init__(self, mode='r', name=''):
        self.mode = mode[:1]
        self.name = name
        self.refcount = 0
        self.closed = False

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        return (
            _item for _item in self
            if _item.name.startswith(prefix)
        )

    def __contains__(self, item):
        return any(str(item) == str(_item) for _item in iter(self))

    def __enter__(self):
        # we don't support nesting the same archive
        assert self.refcount == 0
        self.refcount += 1
        logging.debug('Entering archive %r', self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.refcount -= 1
        if exc_type == BrokenPipeError:
            return True
        logging.debug('Exiting archive %r', self)
        self.close()

    def close(self):
        """Close the archive."""
        self.closed = True

    def open(self, name, mode):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def unused_name(self, stem, suffix):
        """Generate unique name for container file."""
        for i in itertools.count():
            if i:
                filename = '{}.{}.{}'.format(stem, i, suffix)
            else:
                filename = '{}.{}'.format(stem, suffix)
            if filename not in self:
                return filename


###############################################################################

class Directory(Container):
    """Treat directory tree as a container."""

    def __init__(self, path='', mode='r', *, overwrite=False):
        """Create directory wrapper."""
        # if empty path, this refers to the whole filesystem
        if not path:
            self._path = ''
        elif isinstance(path, Directory):
            self._path = path._path
        else:
            self._path = Path(path)
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode == 'w':
            logging.debug('Creating directory `%s`', self._path)
            # exist_ok raises FileExistsError only if the *target* already
            # exists, not the parents
            self._path.mkdir(parents=True, exist_ok=overwrite)
        super().__init__(mode, str(self._path))

    def open(self, name, mode):
        """Open a stream in the container."""
        # mode in 'r', 'w'
        mode = mode[:1]
        pathname = Path(name)
        if mode == 'w':
            path = pathname.parent
            logging.debug('Creating directory `%s`', self._path / path)
            (self._path / path).mkdir(parents=True, exist_ok=True)
        logging.debug("Opening file `%s` for mode '%s'.", name, mode)
        filepath = Path(self._path / pathname)
        # return Directory  object instead of stream if the path is a directory
        if filepath.is_dir():
            return Directory(filepath)
        file = open(filepath, mode + 'b')
        # provide name relative to directory container
        stream = Stream(
            file, mode=mode,
            name=str(pathname), overwrite=True,
            where=self,
        )
        return stream

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
        return Path(self._path / name).exists()

    def __repr__(self):
        return f"{type(self).__name__}('{self._path}')"
