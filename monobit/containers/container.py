"""
monobit.containers.container - base class for containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools


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

    def open(self, name, mode, overwrite=False):
        """Open a binary stream in the container."""
        raise NotImplementedError

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
