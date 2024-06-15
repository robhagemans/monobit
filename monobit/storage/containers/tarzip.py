"""
monobit.storage.containers.tarzip - tar and zip containers

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging
import zipfile
import tarfile
import time
from pathlib import Path, PurePosixPath
from itertools import chain

from .containers import Archive
from ..base import containers
from ..streams import KeepOpen, Stream
from ..magic import FileFormatError, Magic


class ZipTarBase(Archive):

    def __init__(self, file, mode='r'):
        """Create wrapper."""
        # reading zipfile needs a seekable stream, drain to buffer if needed
        self._stream = Stream(file, mode)
        # create the zipfile
        self._archive = self._create_archive(self._stream, mode)
        # output files, to be written on close
        self._files = []
        super().__init__(file, mode)

    def close(self):
        """Close the archive, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            for file in self._files:
                logging.debug("Writing out '%s' to archive %s.", file.name, self)
                self._write_out(file)
                file.close()
        try:
            self._archive.close()
        except EnvironmentError as e:
            # e.g. BrokenPipeError
            logging.debug(e)
        self._stream.close()
        super().close()

    def open(self, name, mode):
        """Open a stream in the container."""
        filename = str(PurePosixPath(self.root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug("Opening file '%s' on container %s.", name, self)
        if mode == 'r':
            try:
                file = self._open_read(filename)
            except KeyError:
                raise FileNotFoundError(f"'{filename}' not found on {self}")
            # .name is not writeable, so we need to wrap
            return Stream(file, mode, name=name)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = Stream(KeepOpen(io.BytesIO()), mode=mode, name=name)
            if name in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', name)
            self._files.append(newfile)
            return newfile


###############################################################################

@containers.register(
    name='zip',
    magic=(b'PK\x03\x04',),
    patterns=('*.zip',),
)
class ZipContainer(ZipTarBase):
    """Zip-file wrapper."""

    def __init__(self, file, mode='r', *, password:bytes=None):
        """
        Access Zip archive.

        password: password for encrypted archive entries. Individual per-file passwords not supported.
        """
        super().__init__(file, mode)
        self._pwd = password

    @staticmethod
    def _create_archive(stream, mode):
        try:
            return zipfile.ZipFile(
                stream, mode,
                compression=zipfile.ZIP_DEFLATED
            )
        except zipfile.BadZipFile as exc:
            raise FileFormatError(exc) from exc

    def _write_out(self, file):
        bytearray = file.getvalue()
        self._archive.writestr(
            str(PurePosixPath(self.root) / file.name), bytearray
        )

    def list(self):
        """List full contents of archive."""
        # construct directory entries even if they are missing from the zip
        ziplist = tuple(set(chain(*(
            (_name, *(f'{_path}/' for _path in Path(_name).parents[:-1]))
            for _name in self._archive.namelist()
        ))))
        return ziplist

    def _open_read(self, filename):
        filename = filename.removesuffix('/')
        try:
            return self._archive.open(filename, 'r', pwd=self._pwd)
        except KeyError:
            # return None for open() on directories (like tarfile does)
            if filename + '/' in self.list():
                return None
            raise


###############################################################################

@containers.register(
    name='tar',
    # maybe
    magic=(
        Magic.offset(257) + b'ustar',
    ),
    patterns=('*.tar',),
)
class TarContainer(ZipTarBase):
    """Tar-file wrapper."""

    def __init__(self, file, mode='r'):
        """Access Tar archive."""
        super().__init__(file, mode)

    @staticmethod
    def _create_archive(stream, mode):
        try:
            return tarfile.open(fileobj=stream, mode=mode)
        except tarfile.ReadError as exc:
            raise FileFormatError(exc) from exc

    def _write_out(self, file):
        name = file.name
        tinfo = tarfile.TarInfo(str(PurePosixPath(self.root) / name))
        tinfo.mtime = time.time()
        tinfo.size = len(file.getvalue())
        file.seek(0)
        self._archive.addfile(tinfo, file)

    def list(self):
        """List full contents of archive."""
        return tuple(
            f'{_name}/' if self._is_dir(_name) else _name
            for _name in self._archive.getnames()
        )

    def _open_read(self, filename):
        return self._archive.extractfile(filename)

    def _is_dir(self, filename):
        tarinfo = self._archive.getmember(filename)
        return tarinfo.isdir()
