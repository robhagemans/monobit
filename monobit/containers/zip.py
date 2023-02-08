"""
monobit.containers.zip - zipfile container

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import logging
import zipfile
from pathlib import Path, PurePosixPath

from ..container import DEFAULT_ROOT, Container
from ..streams import KeepOpen, Stream
from ..storage import loaders, savers, containers, load_all, save_all
from ..magic import FileFormatError


@loaders.register('zip', magic=(b'PK\x03\x04',), name='zip')
def load_zip(instream):
    with ZipContainer(instream) as container:
        return load_all(container)

@savers.register(linked=load_zip)
def save_zip(fonts, outstream):
    with ZipContainer(outstream, 'w') as container:
        return save_all(fonts, container)

@containers.register(linked=load_zip)
def open_zip(instream):
    return ZipContainer(instream)


class ZipContainer(Container):
    """Zip-file wrapper."""

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        super().__init__(mode, file.name)
        # reading zipfile needs a seekable stream, drain to buffer if needed
        stream = Stream(file, mode, overwrite=overwrite)
        # create the zipfile
        try:
            self._zip = zipfile.ZipFile(
                stream, mode,
                compression=zipfile.ZIP_DEFLATED
            )
        except zipfile.BadZipFile as exc:
            raise FileFormatError(exc) from exc
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

    def __iter__(self):
        """List contents."""
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in self._zip.namelist()
            # exclude directories
            if not _name.endswith('/')
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
            return Stream(self._zip.open(filename, mode), mode=mode, where=self)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = Stream(KeepOpen(io.BytesIO()), mode=mode, name=filename, where=self)
            if filename in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', filename)
            self._files.append(newfile)
            return newfile
