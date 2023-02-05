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
from .pack import Pack


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
    container_types = _identify_container(file, mode, overwrite)  #, where=
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
    return Container(None)

def _identify_container(file, mode, overwrite, where=None):
    """Get container of the appropriate type."""
    if not file:
        raise ValueError('No location provided.')
    if isinstance(file, str):
        file = Path(file)
    # if it already is a directory there is no choice
    if isinstance(file, Path) and file.is_dir():
        container_types = (Directory,)
    else:
        if isinstance(file, Path) and mode == 'r' and where:
            file = where.open(file)
        container_types = containers.identify(file)
    if not container_types:
        suffix = get_suffix(file)
        # output to file with no suffix - default to directory
        if mode == 'w' and not suffix and isinstance(file, Path):
            return (Directory,)
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

    def load(self, **kwargs):
        return _load_all(self, **kwargs)

    def save(self, fonts, **kwargs):
        return _save_all(fonts, where=self, **kwargs)


def _load_all(container, **kwargs):
    """Open container and load all fonts found in it into one pack."""
    format = ''
    logging.info('Reading all from `%s`.', container.name)
    packs = Pack()
    # try opening a container on input file for read, will raise error if not container format
    for name in container:
        logging.debug('Trying `%s` on `%s`.', name, container.name)
        with Stream(name, 'r', where=container) as stream:
            try:
                pack = _load_from_location(stream, where=container, format=format, **kwargs)
            except Exception as exc:
                # if one font fails for any reason, try the next
                # loaders raise ValueError if unable to parse
                logging.debug('Could not load `%s`: %s', name, exc)
            else:
                packs += Pack(pack)
    return packs

def _save_all(pack, where, **kwargs):
    """Save fonts to a container."""
    format = ''
    logging.info('Writing all to `%s`.', where.name)
    for font in pack:
        # generate unique filename
        name = font.name.replace(' ', '_')
        filename = where.unused_name(name, format)
        try:
            with Stream(filename, 'w', where=where) as stream:
                _save_to_file(Pack(font), stream, where, format, **kwargs)
        except BrokenPipeError:
            pass
        except Exception as e:
            logging.error('Could not save `%s`: %s', filename, e)
            #raise


class Directory(Container):
    """Treat directory tree as a container."""

    def __init__(self, path, mode='r', *, overwrite=False):
        """Create directory wrapper."""
        # if empty path, this refers to the whole filesystem
        if not path:
            path = ''
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
        logging.debug("Opening file `%s` for mode '%s'.", name, mode)
        file = open(self._path / pathname, mode + 'b')
        # provide name relative to directory container
        stream = Stream(
            file, mode=mode,
            name=str(pathname), overwrite=True,
            where=self,
        )
        return stream

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
