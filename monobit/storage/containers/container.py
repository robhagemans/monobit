"""
monobit.storage.containers.container - base class for containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools
from pathlib import Path

from ..magic import MagicRegistry

CONTAINERS = MagicRegistry('__unused__')


class Container:
    """Base class for container types."""

    def __init__(self, mode='r', name='', ignore_case=True):
        self.mode = mode[:1]
        self.name = name
        self.refcount = 0
        self.closed = False
        # ignore case on read - open any case insensitive match
        # case sensitivity of writing depends on file system
        self._ignore_case = ignore_case

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        return (
            _item for _item in self
            if _item.startswith(str(prefix))
        )

    def __contains__(self, item):
        """Check if file is in container. Case sensitive if container/fs is."""
        if self._ignore_case:
            return (
                str(item).lower() in
                (str(_item).lower() for _item in iter(self))
            )
        else:
            return str(item) in iter(self)

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

    def open(self, name, mode, overwrite=False):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def is_dir(self, name):
        """Item at `name` is a directory."""
        raise NotImplementedError

    def __iter__(self):
        """List contents."""
        return self.iter_sub(prefix='')

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        raise NotImplementedError

    def _match_name(self, filepath):
        """Find case insensitive match, if the case sensitive match doesn't."""
        if self._ignore_case:
            match = find_case_insensitive(filepath, iter(self))
            if match is not None:
                return match
        raise FileNotFoundError(filepath)

    def unused_name(self, name):
        """Generate unique name for container file."""
        if name not in self:
            return name
        stem, _, suffix = name.rpartition('.')
        for i in itertools.count():
            filename = '{}.{}'.format(stem, i)
            if suffix:
                filename = '{}.{}'.format(filename, suffix)
            if filename not in self:
                return filename

def find_case_insensitive(filepath, iterator):
    """Find case insensitive match."""
    for name in iterator:
        if str(name).lower() == str(filepath).lower():
            return name
    return None
