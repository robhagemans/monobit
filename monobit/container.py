"""
monobit.container - file containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging
import itertools
from pathlib import Path

from .magic import MagicRegistry, FileFormatError, get_suffix
from .streams import StreamBase, Stream


DEFAULT_ROOT = 'fonts'

containers = MagicRegistry()


class ContainerFormatError(FileFormatError):
    """Incorrect container format."""


def open_container(file, mode, overwrite=False):
    """Open container of the appropriate type."""
    if isinstance(file, Container):
        return file
    if not file:
        # no-container, will throw errors when used
        return Container(None)
    container_types = _identify_container(file, mode, overwrite)
    for container_type in container_types:
        try:
            container = container_type(file, mode, overwrite=overwrite)
            logging.debug(
                "Opening %s container `%s` for '%s'.",
                container_type.__name__, container.name, mode
            )
            return container
        except ContainerFormatError as e:
            logging.debug(e)
    raise ContainerFormatError('No matching container type found.')


def _identify_container(file, mode, overwrite):
    """Get container of the appropriate type."""
    if not file:
        raise ValueError('No location provided.')
    # if it already is a directory there is no choice
    if isinstance(file, (str, Path)) and Path(file).is_dir():
        container_types = (Directory,)
    else:
        container_types = containers.identify(file, do_open=(mode == 'r'))
    if not container_types:
        suffix = get_suffix(file)
        # output to file with no suffix - default to directory
        if mode == 'w' and not suffix and isinstance(file, (str, Path)):
            return (Directory,)
        # no container type found
        #raise ContainerFormatError('Stream is not a known container format.')
    return container_types


class Container(StreamBase):
    """Base class for container types."""

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

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
# directory

class Directory(Container):
    """Treat directory tree as a container."""

    def __init__(self, path, mode='r', *, overwrite=False):
        """Create directory wrapper."""
        # if empty path, this refers to the whole filesystem
        if not path:
            path = ''
        self._path = Path(path)
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode == 'w':
            logging.debug('Creating directory `%s`', self._path)
            # exist_ok raises FileExistsError only if the *target* already
            # exists, not the parents
            self._path.mkdir(parents=True, exist_ok=overwrite)
        super().__init__(None, mode, str(self._path))

    def open(self, name, mode):
        """Open a stream in the container."""
        # mode in 'r', 'w'
        mode = mode[:1]
        pathname = Path(name)
        if mode == 'w':
            path = pathname.parent
            logging.debug('Creating directory `%s`', self._path / path)
            (self._path / path).mkdir(parents=True, exist_ok=True)
        # provide name relative to directory container
        file = Stream(
            self._path / pathname, mode=mode,
            name=str(pathname), overwrite=True
        )
        return file

    def __iter__(self):
        """List contents."""
        # don't walk the whole filesystem - no path is no contents
        if not self._path:
            return ()
        return (
            str((Path(_r) / _f).relative_to(self._path))
            for _r, _, _files in os.walk(self._path)
            for _f in _files
        )

    def __contains__(self, name):
        """File exists in container."""
        return (self._path / name).exists()
