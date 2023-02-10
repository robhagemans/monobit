"""
monobit.containers.tar - tarfile container

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import time
import tarfile
import logging
from pathlib import Path, PurePosixPath

from ..container import DEFAULT_ROOT, Container
from ..streams import Stream, KeepOpen
from ..storage import loaders, savers, containers, load_all, save_all
from ..magic import FileFormatError


@loaders.register('tar', name='tar')
def load_tar(instream):
    with TarContainer(instream) as container:
        return load_all(container)

@savers.register(linked=load_tar)
def save_tar(fonts, outstream):
    with TarContainer(outstream, 'w') as container:
        return save_all(fonts, container)

@containers.register(linked=load_tar)
def open_tar(instream, mode='r', *, overwrite=False):
    return TarContainer(instream, mode, overwrite=overwrite)


class TarContainer(Container):
    """Tar-file wrapper."""

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        super().__init__(mode, file.name)
        # reading tarfile needs a seekable stream, drain to buffer if needed
        stream = Stream(file, mode, overwrite=overwrite)
        # create the tarfile
        try:
            self._tarfile = tarfile.open(fileobj=stream, mode=mode)
        except tarfile.ReadError as exc:
            raise FileFormatError(exc) from exc
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
            return Stream(file, mode, name=name, where=self)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = Stream(KeepOpen(io.BytesIO()), mode=mode, name=name, where=self)
            if name in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', name)
            self._files.append(newfile)
            return newfile
