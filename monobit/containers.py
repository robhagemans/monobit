"""
monobit.containers - file containers

(c) 2021 Rob Hagemans
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
    if not file or file == io:
        # io module is not a context manager
        return DirContainer('')
    container_type = identify_container(file, mode, overwrite)
    return container_type(file, mode, overwrite=overwrite)

def identify_container(file, mode, overwrite):
    """Get container of the appropriate type."""
    # no file provided means filesystem
    if not file or file == io:
        # io module is not a context manager
        return DirContainer
    # handle directories separately - no magic
    if isinstance(file, (str, Path)) and Path(file).is_dir():
        container_type = DirContainer
    else:
        container_type = containers.identify(file, mode)
    suffix = get_suffix(file)
    if not container_type:
        # output to file with no suffix - default to text container
        if mode == 'w' and not suffix:
            return TextContainer
        # no container type found
        raise ContainerFormatError('Expected container format, got non-container stream.')
    return container_type


def unique_name(container, name, ext):
    """Generate unique name for container file."""
    filename = '{}.{}'.format(name, ext)
    i = 0
    while filename in container:
        i += 1
        filename = '{}.{}.{}'.format(name, i, ext)
    return filename


class Container(StreamBase):
    """Base class for container types."""

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

    def open(self, name, mode):
        """Open a binary stream in the container."""
        raise NotImplementedError


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
        file = Stream(self._path / pathname, mode=mode, name=str(pathname))
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
        # append .zip to zip filename, but leave out of root dir name
        root = ''
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if isinstance(file, (str, Path)):
            file = open_stream(file, mode, overwrite=overwrite)
        else:
            root = get_name(file)
            # if name ends up empty, replace; clip off any dir path and suffix
            root = PurePath(file.name).stem or DEFAULT_ROOT
        # reading zipfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            file = io.BytesIO(file.read())
        if mode == 'w':
            # if creating a new container, put everything in a directory inside it
            self._root = root
        else:
            self._root = ''
        # create the zipfile
        try:
            self._zip = zipfile.ZipFile(file, mode, compression=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipFile as exc:
            raise ContainerFormatError(exc) from exc
        # output files, to be written on close
        self._files = []
        super().__init__(None, mode, self._zip.filename)

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
        # reading zipfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            file = io.BytesIO(file.read())
        else:
            file = open_stream(file, mode, overwrite=overwrite)
        # create the tarfile
        try:
            self._tarfile = tarfile.open(fileobj=file, mode=mode)
        except tarfile.ReadError as exc:
            raise ContainerFormatError(exc) from exc
        super().__init__(None, mode, self._tarfile.name)
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
# yaml-style '---'-separated text stream

@containers.register('.txt', '.yaffs', magic=(b'---',))
class TextContainer(Container):
    """Container of mime-/yaml-style concatenated text files with boundary marker."""

    # boundary marker
    separator = b'---'

    def __init__(self, infile, mode='r', *, overwrite=False):
        """Open stream or create wrapper."""
        # all containers expect binary stream, including TextContainer
        stream = Stream(infile, mode, overwrite=overwrite)
        super().__init__(stream, mode)
        if self.mode == 'r':
            if self._stream.readline().strip() != self.separator:
                raise ContainerFormatError('Not a text container.')
        else:
            self._stream.write(b'%s\n' % (self.separator,))
        self._substream = None

    def __exit__(self, exc_type, exc_value, traceback):
        if self._substream:
            self._substream.close()
        return self._stream.__exit__(exc_type, exc_value, traceback)

    def __iter__(self):
        """Dummy content lister."""
        for i in itertools.count():
            if self._stream.closed:
                return
            yield str(i)

    def __contains__(self, name):
        return False

    def open(self, name, mode):
        """Open a single stream. Name argument is a dummy."""
        if not mode.startswith(self.mode):
            raise FileFormatError(f"Cannot open file for '{mode}' on container open for '{self.mode}'")
        if self._substream and not self._substream.closed:
            raise EnvironmentError('Text container can only support one open file at a time.')
        self._substream = _Substream(self._stream, self.mode, self.separator, name=name)
        return self._substream


class _Substream(StreamWrapper):
    """Stream on TextContainer."""

    def __init__(self, parent_stream, mode, separator, name=''):
        """Open a substream."""
        self._separator = separator
        self._linebuffer = b''
        self._eof = False
        super().__init__(parent_stream, mode, name=name)

    def __iter__(self):
        """Iterate over lines until next separator."""
        while not self._eof:
            yield self.readline()

    def _check_line(self):
        """Fill the line buffer, stop at separator."""
        if self._eof:
            line = b''
        else:
            line = self._stream.readline()
            if not line:
                # parent stream has ended, signal eof on substream too
                self._eof = True
                # close parent stream
                # this signals to parent not to open further substreams
                self._stream.close()
            elif line.strip() == self._separator:
                # encountered separator, don't read any further
                self._eof = True
            else:
                self._linebuffer += line
        return self._linebuffer

    def read(self, n=-1):
        """Read n bytes."""
        while n < 0 or len(self._linebuffer) < n:
            self._check_line()
            if self._eof:
                break
        value, self._linebuffer = self._linebuffer[:n], self._linebuffer[n:]
        return value

    read1 = read

    def readline(self):
        """Read line until \n."""
        self._check_line()
        value, _, self._linebuffer = self._linebuffer.partition(b'\n')
        return value

    readline1 = readline

    def close(self):
        """Close the substream."""
        try:
            if not self.closed and not self._stream.closed:
                try:
                    self._stream.flush()
                    if self.mode == 'w' and not self.closed:
                        self._stream.write(b'\n%s\n' % (self._separator, ))
                except BrokenPipeError:
                    pass
        finally:
            self.closed = True


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
        logging.debug('%r %r %r', last_suffix, self.format, self._content_name)

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
