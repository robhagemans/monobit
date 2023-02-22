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

from ..container import Container
from ..streams import Stream, KeepOpen
from ..storage import (
    loaders, savers, load_all, save_all,
    open_stream_or_container, load_stream, save_stream
)
from ..magic import FileFormatError, Magic


@loaders.register(
    name='tar',
    # maybe
    magic=(
        Magic.offset(257) + b'ustar',
    ),
    patterns=('*.tar',),
)
def load_tar(instream, subpath:str='', payload:str='', **kwargs):
    with TarContainer(instream) as container:
        if not subpath:
            return load_all(container, format=payload, **kwargs)
        with open_stream_or_container(container, subpath, mode='r', overwrite=False) as (stream, subpath):
            return load_stream(stream, format=payload, subpath=subpath, **kwargs)


@savers.register(linked=load_tar)
def save_tar(fonts, outstream, subpath:str='', payload:str='', **kwargs):
    with TarContainer(outstream, 'w') as container:
        if not subpath:
            return save_all(fonts, container, format=payload, **kwargs)
        with open_stream_or_container(container, subpath, mode='w', overwrite=False) as (stream, subpath):
            return save_stream(fonts, stream, format=payload, subpath=subpath, **kwargs)



class TarContainer(Container):
    """Tar-file wrapper."""

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        super().__init__(mode, file.name)
        # reading tarfile needs a seekable stream, drain to buffer if needed
        self._stream = Stream(file, mode, overwrite=overwrite)
        # create the tarfile
        try:
            self._tarfile = tarfile.open(fileobj=self._stream, mode=mode)
        except tarfile.ReadError as exc:
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
        except EnvironmentError as e:
            # e.g. BrokenPipeError
            logging.debug(e)
        self._stream.close()
        super().close()
        self.closed = True

    def __iter__(self):
        """List contents."""
        # list regular files only, skip symlinks and dirs and block devices
        namelist = (
            _ti.name
            for _ti in self._tarfile.getmembers()
            if _ti.isfile()
        )
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in namelist
            # exclude directories
            if not _name.endswith('/')
        )

    def open(self, name, mode, overwrite=False):
        """Open a stream in the container."""
        name = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on tar container `%s`.', name, self.name)
        if mode == 'r':
            try:
                file = self._tarfile.extractfile(name)
            except KeyError as e:
                raise FileNotFoundError(e) from e
            # .name is not writeable, so we need to wrap
            return Stream(file, mode, name=name, where=self)
        else:
            if name in self and not overwrite:
                raise ValueError(
                    f'Overwriting existing file {str(name)}'
                    ' requires -overwrite to be set'
                )
            # stop BytesIO from being closed until we want it to be
            newfile = Stream(KeepOpen(io.BytesIO()), mode=mode, name=name, where=self)
            if name in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', name)
            self._files.append(newfile)
            return newfile
