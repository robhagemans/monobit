"""
monobit.containers - file containers

(c) 2021--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import os
import sys
import time
import logging
import itertools
from contextlib import contextmanager
import zipfile
import tarfile
import gzip
import lzma
import bz2
from pathlib import Path, PurePath, PurePosixPath

from .streams import (
    MagicRegistry, FileFormatError,
    StreamBase, StreamWrapper, Stream, KeepOpen,
    get_suffix, open_stream, get_name
)


DEFAULT_ROOT = 'fonts'


class ContainerFormatError(FileFormatError):
    """Incorrect container format."""


containers = MagicRegistry()

def open_container(file, mode, overwrite=False):
    """Open container of the appropriate type."""
    if isinstance(file, Container):
        return file
    if not file:
        # no-container, will throw errors when used
        return Container(None)
    container_type = _identify_container(file, mode, overwrite)
    container = container_type(file, mode, overwrite=overwrite)
    logging.debug("Opening %s container `%s` for '%s'.", container_type.__name__, container.name, mode)
    return container

def _identify_container(file, mode, overwrite):
    """Get container of the appropriate type."""
    if not file:
        raise ValueError('No location provided.')
    # if it already is a directory there is no choice
    if isinstance(file, (str, Path)) and Path(file).is_dir():
        container_type = DirContainer
    else:
        container_type = containers.identify(file, do_open=(mode == 'r'))
    if not container_type:
        suffix = get_suffix(file)
        # output to file with no suffix - default to directory
        if mode == 'w' and not suffix and isinstance(file, (str, Path)):
            return DirContainer
        # no container type found
        raise ContainerFormatError('Expected container format, got non-container stream.')
    return container_type


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
            filename = '{}.{}.{}'.format(stem, i, suffix)
            if filename not in self:
                return filename

###################################################################################################
# directory

class DirContainer(Container):
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
            # exist_ok raises FileExistsError only if the *target* already exists, not the parents
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
        file = Stream(self._path / pathname, mode=mode, name=str(pathname), overwrite=True)
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


###################################################################################################
# zip archive

@containers.register('.zip', magic=(b'PK\x03\x04',))
class ZipContainer(Container):
    """Zip-file wrapper."""

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        # reading zipfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            # note file is externally provided so we shouldn't close it
            # but the BytesIO is ours
            stream = io.BytesIO(file.read())
        else:
            stream = open_stream(file, mode, overwrite=overwrite)
        # create the zipfile
        try:
            self._zip = zipfile.ZipFile(stream, mode, compression=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipFile as exc:
            raise ContainerFormatError(exc) from exc
        super().__init__(stream, mode, self._zip.filename)
        # on output, put all files in a directory with the same name as the archive (without suffix)
        if mode == 'w':
            self._root = Path(self.name).stem or DEFAULT_ROOT
        else:
            self._root = ''
        # output files, to be written on close
        self._files = []


    def close(self):
        """Close the zip file, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            for file in self._files:
                logging.debug('Writing out `%s` to zip container `%s`.', file.name, self.name)
                bytearray = file.getvalue()
                file.close()
                self._zip.writestr(file.name, bytearray)
        try:
            self._zip.close()
        except EnvironmentError:
            # e.g. BrokenPipeError
            pass
        super().close()
        self.closed = True

    def __iter__(self):
        """List contents."""
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in self._zip.namelist()
        )

    def open(self, name, mode):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        filename = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on zip container `%s`.', filename, self.name)
        if mode == 'r':
            return Stream(self._zip.open(filename, mode), mode=mode)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = KeepOpen(io.BytesIO(), mode=mode, name=filename)
            if filename in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', filename)
            self._files.append(newfile)
            return newfile



###################################################################################################
# tar archive

@containers.register('.tar')
class TarContainer(Container):
    """Tar-file wrapper."""

    def __init__(self, file, mode='r',*, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        # reading tarfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            # note file is externally provided so we shouldn't close it
            # but the BytesIO is ours
            stream = io.BytesIO(file.read())
        else:
            stream = open_stream(file, mode, overwrite=overwrite)
        # create the tarfile
        try:
            self._tarfile = tarfile.open(fileobj=stream, mode=mode)
        except tarfile.ReadError as exc:
            raise ContainerFormatError(exc) from exc
        super().__init__(stream, mode, self._tarfile.name)
        # on output, put all files in a directory with the same name as the archive (without suffix)
        if mode == 'w':
            self._root = Path(self.name).stem or DEFAULT_ROOT
        else:
            self._root = ''
        # output files, to be written on close
        self._files = []

    def close(self):
        """Close the tar file, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            for file in self._files:
                name = file.name
                logging.debug('Writing out `%s` to tar container `%s`.', name, self.name)
                tinfo = tarfile.TarInfo(name)
                tinfo.mtime = time.time()
                tinfo.size = len(file.getvalue())
                file.seek(0)
                self._tarfile.addfile(tinfo, file)
                file.close()
        try:
            self._tarfile.close()
        except EnvironmentError:
            # e.g. BrokenPipeError
            pass
        super().close()
        self.closed = True

    def __iter__(self):
        """List contents."""
        # list regular files only, skip symlinks and dirs and block devices
        return (_ti.name for _ti in self._tarfile.getmembers() if _ti.isfile())

    def open(self, name, mode):
        """Open a stream in the container."""
        name = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on tar container `%s`.', name, self.name)
        if mode == 'r':
            file = self._tarfile.extractfile(name)
            # .name is not writeable, so we need to wrap
            return Stream(file, mode, name=name)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = KeepOpen(io.BytesIO(), mode=mode, name=name)
            if name in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', name)
            self._files.append(newfile)
            return newfile


###################################################################################################
# single-file compression

class Compressor(Container):
    """Base class for compression helpers."""

    format = ''
    compressor = None

    def __init__(self, infile, mode='r', *, overwrite=False):
        stream = Stream(infile, mode, overwrite=overwrite)
        super().__init__(stream, mode)
        # drop the .gz etc
        last_suffix = get_suffix(self.name)
        if last_suffix == self.format:
            self._content_name = self.name[:-1-len(last_suffix)]
        else:
            self._content_name = self.name

    def __iter__(self):
        return iter((self._content_name,))

    def open(self, name='', mode=''):
        """Open a stream in the container."""
        mode = mode[:1] or self.mode
        wrapped = self.compressor.open(self._stream, mode + 'b')
        wrapped = Stream(wrapped, mode, name=self._content_name)
        logging.debug(
            "Opening %s-compressed stream `%s` on `%s` for mode '%s'",
            self.format, wrapped.name, self.name, mode
        )
        return wrapped


@containers.register('.gz', magic=(b'\x1f\x8b',))
class GzipCompressor(Compressor):
    compressor = gzip

@containers.register('.xz', magic=(b'\xFD7zXZ\x00',))
class LzmaCompressor(Compressor):
    compressor = lzma

@containers.register('.bz2', magic=(b'BZh',))
class Bzip2Compressor(Compressor):
    compressor = bz2
