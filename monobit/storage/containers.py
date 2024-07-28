"""
monobit.storage.containers - base classes for containers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools
from io import BytesIO
from pathlib import Path

from .magic import FileFormatError
from .streams import Stream, KeepOpen


class Container:
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

    def __enter__(self):
        # we don't support nesting the same archive
        assert self.refcount == 0
        self.refcount += 1
        logging.debug('Entering %r', self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.refcount -= 1
        if exc_type == BrokenPipeError:
            return True
        logging.debug('Exiting %r', self)
        self.close()

    def close(self):
        """Close the archive."""
        self.closed = True

    def decode(self, name, **kwargs):
        """Open a binary stream to read from the container."""
        raise NotImplementedError

    def encode(self, name, **kwargs):
        """Open a binary stream to write to the container."""
        raise NotImplementedError

    def is_dir(self, name):
        """Item at `name` is a directory."""
        raise NotImplementedError

    def iter_sub(self, prefix):
        """List contents of a subpath."""
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

    def __init__(self, stream, mode='r'):
        # private fields
        self._wrapped_stream = stream
        self._data = {}
        self._files = {}
        super().__init__(stream, mode)
        self._get_data()

    def close(self):
        """Close the archive, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            self.encode_all(self._files, self._wrapped_stream)
        self._wrapped_stream.close()
        super().close()

    def list(self):
        """List full contents of archive."""
        return (
            tuple(self._data.keys())
            + tuple(self._files.keys())
        )

    def decode(self, name):
        """Open input stream on filter container."""
        filename = str(Path(self.root) / name)
        name = str(name)
        try:
            data = self._data[filename]
        except KeyError:
            if f'{filename}/' in self._data:
                raise IsADirectoryError(f"'{name}' is a directory")
            raise FileNotFoundError(
                f"No file with name '{name}' found in archive."
            )
        return Stream.from_data(data, mode='r', name=name)

    def encode(self, name, **kwargs):
        """Open output stream on filter container."""
        filename = str(Path(self.root) / name)
        name = str(name)
        if filename in self._files:
            raise FileExistsError(
                f"Cannot create multiple files of the same name '{name}'"
            )
        newfile = Stream(KeepOpen(BytesIO()), mode='w', name=name)
        self._files[filename] = {
            'outstream': newfile,
            **kwargs
        }
        return newfile

    def _get_data(self):
        """Read contents of archive into memory."""
        if self.mode == 'w':
            return
        if self._data:
            return
        self._data = self.decode_all(self._wrapped_stream)
        # create directory items, if not present
        for name in list(self._data.keys()):
            if '/' in name:
                for parent in Path(name).parents:
                    if parent != Path('.'):
                        self._data[f'{parent}/'] = b''

    @classmethod
    def decode_all(cls, instream):
        """Decode all files in readable archive."""
        raise NotImplementedError

    @classmethod
    def encode_all(cls, filedict, outstream, **kwargs):
        """Encode all files in writable archive."""
        raise NotImplementedError


class SerialContainer(FlatFilterContainer):

    @classmethod
    def encode_all(cls, data, outstream, **kwargs):
        outstream.write(cls._head())
        for count, (name, filedict) in enumerate(data.items()):
            filedata = filedict.pop('outstream').getvalue()
            cls._encode(
                name, filedata, outstream,
                **filedict
            )
            if count < len(data) - 1:
                outstream.write(cls._separator())
        outstream.write(cls._tail())

    @classmethod
    def _head(cls):
        return b''

    @classmethod
    def _tail(cls):
        return b''

    @classmethod
    def _separator(cls):
        return b''

    @classmethod
    def _encode(cls, name, data, outstream, **kwargs):
        raise NotImplementedError


class SerialTextContainer(SerialContainer):

    @classmethod
    def encode_all(cls, data, outstream, **kwargs):
        outstream = outstream.text
        return super().encode_all(data, outstream, **kwargs)

    @classmethod
    def _head(cls):
        return ''

    @classmethod
    def _tail(cls):
        return ''

    @classmethod
    def _separator(cls):
        return ''
