"""
monobit.containers.zip - zipfile container

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging
import zipfile
from pathlib import Path, PurePosixPath

from .container import Container
from ..streams import KeepOpen, Stream
from ..magic import FileFormatError


class ZipContainer(Container):
    """Zip-file wrapper."""

    def __init__(self, file, mode='r', ignore_case=True):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        super().__init__(mode, file.name, ignore_case=ignore_case)
        # reading zipfile needs a seekable stream, drain to buffer if needed
        self._stream = Stream(file, mode)
        # create the zipfile
        try:
            self._zip = zipfile.ZipFile(
                self._stream, mode,
                compression=zipfile.ZIP_DEFLATED
            )
        except zipfile.BadZipFile as exc:
            raise FileFormatError(exc) from exc
        # on output, put all files in a directory with the same name as the archive (without suffix)
        stem = Path(self.name).stem
        if mode == 'w':
            self._root = stem
        else:
            # on read, only set root if it is a common parent
            self._root = ''
            if all(Path(_item).is_relative_to(stem) for _item in iter(self)):
                self._root = stem
        # output files, to be written on close
        self._files = []

    def close(self):
        """Close the zip file, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            for file in self._files:
                logging.debug('Writing out `%s` to zip container `%s`.', file.name, self.name)
                bytearray = file.getvalue()
                file.close()
                self._zip.writestr(
                    str(PurePosixPath(self._root) / file.name), bytearray
                )
        try:
            self._zip.close()
        except EnvironmentError as e:
            # e.g. BrokenPipeError
            logging.debug(e)
        self._stream.close()
        super().close()

    def __iter__(self):
        """List contents."""
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in self._zip.namelist()
            # exclude directories
            if not _name.endswith('/')
        )

    def open(self, name, mode, overwrite=False):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        filename = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on zip container `%s`.', filename, self.name)
        if mode == 'r':
            try:
                file = self._zip.open(filename, mode)
            except KeyError:
                file = self._zip.open(self._match_name(filename), mode)
            return Stream(file, mode=mode, where=self, name=name)
        else:
            if filename in self and not overwrite:
                raise ValueError(
                    f'Overwriting existing file {str(filename)}'
                    ' requires -overwrite to be set'
                )
            # stop BytesIO from being closed until we want it to be
            newfile = Stream(KeepOpen(io.BytesIO()), mode=mode, name=name, where=self)
            if filename in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', filename)
            self._files.append(newfile)
            return newfile


ZipContainer.register(
    name='zip',
    magic=(b'PK\x03\x04',),
    patterns=('*.zip',),
)
