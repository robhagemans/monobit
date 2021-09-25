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
from pathlib import Path, PurePath, PurePosixPath

from . import streams
from .streams import MagicRegistry, StreamWrapper, FileFormatError, get_suffix, open_stream


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
        # this will deal with compressed output, e.g. tar.gz or .tar.xz
        # this parallels what happens in open_stream, but we don't want to create a file here yet
        if mode == 'w' and isinstance(file, (str, Path)) and streams.compressors.identify(file, 'w'):
            # remove compressor suffix
            file = Path(file).with_suffix('')
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


class Container:
    """Base class for container types."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

    def __contains__(self, name):
        """File exists in container."""
        raise NotImplementedError

    def open_binary(self, name, mode):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def open(self, name, mode, *, encoding=None):
        """Open a stream on the container."""
        stream = self.open_binary(name, mode[:1])
        if mode.endswith('b'):
            return stream
        return streams.make_textstream(stream, encoding=encoding)


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
        self.name = str(self._path)
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode == 'w':
            logging.debug('Creating directory `%s`', self._path)
            # exist_ok raises FileExistsError only if the *target* already exists, not the parents
            self._path.mkdir(parents=True, exist_ok=overwrite)

    def open_binary(self, name, mode):
        """Open a stream in the container."""
        # mode in 'rb', 'rt', 'wb', 'wt'
        mode = mode[:1]
        pathname = Path(name)
        if mode == 'w':
            path = pathname.parent
            logging.debug('Creating directory `%s`', self._path / path)
            (self._path / path).mkdir(parents=True, exist_ok=True)
        file = open_stream(self._path / pathname, mode, binary=True)
        # provide name relative to directory container
        file.name = str(pathname)
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

@containers.register('.zip', magic=b'PK\x03\x04')
class ZipContainer(Container):
    """Zip-file wrapper."""

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # append .zip to zip filename, but leave out of root dir name
        root = ''
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if isinstance(file, (str, Path)):
            file = open_stream(file, mode, binary=True, overwrite=overwrite)
        else:
            root = streams.get_stream_name(file)
            # if name ends up empty, replace; clip off any dir path and suffix
            root = PurePath(file.name).stem or 'fonts'
        # reading zipfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            file = io.BytesIO(file.read())
        if mode == 'w':
            # if creating a new container, put everything in a directory inside it
            self._root = root
        else:
            self._root = ''
        self._mode = mode
        # create the zipfile
        try:
            self._zip = zipfile.ZipFile(file, mode, compression=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipFile as exc:
            raise ContainerFormatError(exc) from exc
        self.name = self._zip.filename
        # output files, to be written on close
        self._files = []
        self.closed = False

    def _close(self):
        """Close the zip file, ignoring errors."""
        if self._mode == 'w' and not self.closed:
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

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensure archive is closed and essential records written."""
        if exc_type == BrokenPipeError:
            return True
        self._close()

    def __iter__(self):
        """List contents."""
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in self._zip.namelist()
        )

    def __contains__(self, name):
        """File exists in container."""
        return name in list(self)

    def open_binary(self, name, mode):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        filename = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on zip container `%s`.', filename, self.name)
        if mode == 'r':
            return self._zip.open(filename, mode)
        else:
            newfile = io.BytesIO()
            newfile.name = filename
            # stop BytesIO from being closed until we want it to be
            newfile.close = lambda: None
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
            file = open_stream(file, mode, binary=True, overwrite=overwrite)
        # create the tarfile
        try:
            self._tarfile = tarfile.open(fileobj=file, mode=mode)
        except tarfile.ReadError as exc:
            raise ContainerFormatError(exc) from exc
        self._mode = mode
        self.name = self._tarfile.name
        if mode == 'w':
            self._root = Path(self.name).stem or fonts
        else:
            self._root = ''
        # output files, to be written on close
        self._files = []
        self.closed = False

    def _close(self):
        """Close the tar file, ignoring errors."""
        if self._mode == 'w' and not self.closed:
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

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type == BrokenPipeError:
            return True
        self._close()

    def __del__(self):
        """Ensure archive is closed and essential records written."""
        try:
            self._close()
        except AttributeError:
            # _tarfile may already have been destroyed
            pass

    def __iter__(self):
        """List contents."""
        return iter(self._tarfile.getnames())

    def __contains__(self, name):
        """File exists in container."""
        return name in list(self)

    def open_binary(self, name, mode):
        """Open a stream in the container."""
        name = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on tar container `%s`.', name, self.name)
        if mode == 'r':
            file = self._tarfile.extractfile(name)
            # .name is not writeable, so we need to wrap
            return TarStream(file, name)
        else:
            newfile = io.BytesIO()
            newfile.name = name
            # stop BytesIO from being closed until we want it to be
            newfile.close = lambda: None
            if name in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', name)
            self._files.append(newfile)
            return newfile


class TarStream(StreamWrapper):
    """Wrapper for stream open on tar file."""

    def __init__(self, stream, name):
        """Override name with member name."""
        self.name = name
        super().__init__(stream)


###################################################################################################
# yaml-style '---'-separated text stream

@containers.register('.txt', '.yaffs', magic=b'---')
class TextContainer(Container):
    """Container of mime-/yaml-style concatenated text files with boundary marker."""

    # boundary marker
    separator = b'---'

    def __init__(self, infile, mode='r', *, overwrite=False):
        """Open stream or create wrapper."""
        # all containers expect binary stream, including TextContainer
        self._stream_context = streams.open_stream(infile, mode, binary=True, overwrite=overwrite)
        self._stream = self._stream_context.__enter__()
        self._mode = mode[:1]
        if self._mode == 'r':
            if self._stream.readline().strip() != self.separator:
                raise ContainerFormatError('Not a text container.')
        else:
            self._stream.write(b'%s\n' % (self.separator,))
        self._substream = None
        self.name = self._stream.name

    def __exit__(self, exc_type, exc_value, traceback):
        if self._substream:
            self._substream.close()
        return self._stream_context.__exit__(exc_type, exc_value, traceback)

    def __iter__(self):
        """Dummy content lister."""
        for i in itertools.count():
            if self._stream.closed:
                return
            yield str(i)

    def __contains__(self, name):
        return False

    def open_binary(self, name, mode):
        """Open a single stream. Name argument is a dummy."""
        if not mode.startswith(self._mode):
            raise FileFormatError(f"Cannot open file for '{mode}' on container open for '{self._mode}'")
        if self._substream and not self._substream.closed:
            raise EnvironmentError('Text container can only support one open file at a time.')
        self._substream = _Substream(self._stream, self._mode, self.separator)
        return self._substream


class _Substream(StreamWrapper):
    """Stream on TextContainer."""

    def __init__(self, parent_stream, mode, separator):
        """Open a substream."""
        self.closed = False
        self._separator = separator
        self._mode = mode
        self.name = ''
        self._linebuffer = b''
        self._eof = False
        super().__init__(parent_stream)

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
        if not self.closed and not self._stream.closed:
            try:
                self._stream.flush()
                if self._mode == 'w' and not self.closed:
                    self._stream.write(b'\n%s\n' % (self._separator, ))
            except BrokenPipeError:
                pass
        self.closed = True
