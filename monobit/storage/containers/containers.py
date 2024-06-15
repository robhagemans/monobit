"""
monobit.storage.containers.containers - base classes for containers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools
from io import BytesIO
from pathlib import Path

from ..magic import FileFormatError
from ..streams import Stream, KeepOpen
from ..holders import StreamHolder


class Container(StreamHolder):
    """Base class for multi-stream containers."""

    def __init__(self, mode='r', name=''):
        self.mode = mode[:1]
        self.name = name
        self.refcount = 0
        self.closed = False

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"mode='{self.mode}' name='{self.name}'"
            f"{' [closed]' if self.closed else ''}>"
        )

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        raise NotImplementedError()

    # NOTE open() opens a stream, close() closes the container

    def open(self, name, mode):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def is_dir(self, name):
        """Item at `name` is a directory."""
        raise NotImplementedError


class Archive(Container):
    """Base class for multi-file archives."""

    def __init__(self, file, mode='r'):
        """Create archive object."""
        super().__init__(mode, file.name)

    @property
    def root(self):
        """Root directory for archive - elided on read, auto-added on write."""
        if not hasattr(self, '_root'):
            # on output, put all files in a directory with the same name as the archive (without suffix)
            stem = Path(self.name).stem
            if self.mode == 'w':
                self._root = stem
            else:
                # on read, only set root if it is a common parent
                self._root = ''
                if all(Path(_item).is_relative_to(stem) for _item in self.list()):
                    self._root = stem
        return self._root

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        subs = list(
            str(Path(_name).relative_to(self.root)) for _name in self.list()
            if Path(_name).parent == Path(self.root) / prefix
        )
        return subs

    def is_dir(self, name):
        """Item at 'name' is a directory."""
        name = Path(self.root) / name
        if Path(name) == Path(self.root):
            return True
        ziplist = self.list()
        # str(Path) does not end in /
        if f'{name}/' in ziplist:
            return True
        if f'{name}' in ziplist:
            return False
        raise FileNotFoundError(
            f"File '{name}' not found in archive {self}."
        )

    def list(self):
        """List full contents of archive."""
        raise NotImplementedError()


class FlatFilterContainer(Archive):
    """Archive implementation based on filter logic."""

    def __init__(self, stream, mode='r', encode_kwargs=None, decode_kwargs=None):
        self.encode_kwargs = encode_kwargs or {}
        self.decode_kwargs = decode_kwargs or {}
        # private fields
        self._wrapped_stream = stream
        self._data = {}
        self._files = []
        super().__init__(stream, mode)
        self._get_data()

    def close(self):
        """Close the archive, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            data = {
                str(_file.name): _file.getvalue()
                for _file in self._files
            }
            self.encode_all(
                data, self._wrapped_stream,
                **self.encode_kwargs
            )
        self._wrapped_stream.close()
        super().close()

    def list(self):
        """List full contents of archive."""
        return tuple(self._data.keys())

    def open(self, name, mode):
        """Open a binary stream in the container."""
        name = Path(self.root) / name
        if mode == 'r':
            return self._open_read(name)
        else:
            return self._open_write(name)

    def _open_read(self, name):
        """Open input stream on source wrapper."""
        name = str(name)
        try:
            data = self._data[name]
        except KeyError:
            if f'{name}/' in self._data:
                raise IsADirectoryError(f"'{name}' is a directory")
            raise FileNotFoundError(
                f"No file with name '{name}' found in archive."
            )
        return Stream.from_data(data, mode='r', name=name)

    def _open_write(self, name):
        """Open output stream on source wrapper."""
        if name in self._files:
            raise FileExistsError(
                f"Cannot create multiple files of the same name '{name}'"
            )
        newfile = Stream(KeepOpen(BytesIO()), mode='w', name=name)
        self._files.append(newfile)
        return newfile

    def _get_data(self):
        """Read contents of archive into memory."""
        if self.mode == 'w':
            return
        if self._data:
            return
        self._data = self.decode_all(self._wrapped_stream, **self.decode_kwargs)
        # create directory items, if not present
        for name in list(self._data.keys()):
            if '/' in name:
                for parent in Path(name).parents:
                    if parent != Path('.'):
                        self._data[f'{parent}/'] = b''


    @classmethod
    def decode_all(cls, instream):
        """Generator to decode all files in readable archive."""
        raise NotImplementedError

    @classmethod
    def encode_all(cls, data, outstream):
        """Generator to encode all files in writable archive."""
        raise NotImplementedError
