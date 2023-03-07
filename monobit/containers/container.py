"""
monobit.containers.container - base class for containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools
from pathlib import Path

from ..storage import (
    loaders, savers, load_all, save_all, load_stream, save_stream
)


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

    def _match_name(self, filepath):
        """Find case insensitive match, if the case sensitive match doesn't."""
        if self._ignore_case:
            for name in self:
                logging.debug('trying %s', name)
                if name.lower() == str(filepath).lower():
                    return name
        raise FileNotFoundError(filepath)

    def _open_stream_at(self, path, mode, overwrite):
        """Open stream recursively an container(s) given path."""
        head, tail = find_next_node(self, path, mode)
        if str(head) == '.':
            # no next node found, path is leaf
            # this'll raise a FileNotFoundError if we're reading
            stream = self.open(tail, mode, overwrite)
            tail = ''
        else:
            stream = self.open(head, mode, overwrite)
        return stream, tail

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

    @classmethod
    def load(cls, instream, *, subpath='', **kwargs):
        """Load fonts from container."""
        with cls(instream) as container:
            if not subpath:
                return load_all(container, **kwargs)
            stream, subsubpath = container._open_stream_at(
                subpath, mode='r', overwrite=False
            )
            with stream:
                return load_stream(stream, subpath=subsubpath, **kwargs)

    @classmethod
    def save(
            cls, fonts, outstream, *,
            subpath='', overwrite=False,
            template:str='',
            **kwargs
        ):
        """
        Save fonts to container (directory or archive).

        template: naming template for files in container
        """
        with cls(outstream, 'w') as container:
            if not subpath:
                return save_all(
                    fonts, container,
                    template=template, overwrite=overwrite,
                    **kwargs
                )
            stream, subsubpath = container._open_stream_at(
                subpath, mode='w', overwrite=overwrite
            )
            with stream:
                if template:
                    kwargs['template'] = template
                return save_stream(
                    fonts, stream,
                    subpath=subsubpath, overwrite=overwrite,
                    **kwargs
                )

    @classmethod
    def register(cls, name, magic=(), patterns=()):
        loaders.register(name, magic, patterns, wrapper=True)(cls.load)
        savers.register(name, magic, patterns, wrapper=True)(cls.save)


def find_next_node(container, path, mode):
    """Find the next node (container or file) in the path."""
    head, tail = _split_path(container, path)
    if mode == 'w' and not head.suffixes:
        head2, tail = _split_path_suffix(tail)
        head /= head2
    return head, tail

def _split_path(container, path):
    """Pare back path until an existing ancestor is found."""
    path = Path(path)
    for head in (path, *path.parents):
        if head in container:
            tail = path.relative_to(head)
            return head, tail
    # nothing exists
    return Path('.'), path

def _split_path_suffix(path):
    """Pare forward path until a suffix is found."""
    for head in reversed((path, *path.parents)):
        if head.suffixes:
            tail = path.relative_to(head)
            return head, tail
    # no suffix
    return path, Path('.')
