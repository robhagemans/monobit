"""
monobit.storage.containers.uselibarchive - archive formats supported by libarchive

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import libarchive
from pathlib import Path

from ..magic import FileFormatError
from ..base import containers
from ..containers.containers import FlatFilterContainer


class LibArchiveContainer(FlatFilterContainer):

    def __init__(
            self, stream, mode='r',
        ):
        """Container access using libarchive."""
        super().__init__(stream, mode)
        self.encode_kwargs = {}
        self.decode_kwargs = {}

    @classmethod
    def encode_all(cls, data, outstream):
        raise ValueError('Writing not supported.')

    @classmethod
    def decode_all(cls, instream):
        data = {}
        with libarchive.stream_reader(instream) as archive:
            for entry in archive:
                name = Path(str(entry)).as_posix()
                if name == '.':
                    continue
                if entry.isdir:
                    data[name + '/'] = b''
                elif entry.isreg:
                    data[name] = b''.join(list(entry.get_blocks()))
                    for path in Path(name).parents:
                        if path != Path('.'):
                            data[f'{path}/'] = b''
        return data

    def is_dir(self, name):
        """Item at `name` is a directory."""
        if Path(name) == Path('.'):
            return True
        name = Path(name).as_posix() + '/'
        for found in self.list():
            if found.startswith(name):
                return True
        return False


@containers.register(
    name='rar',
    patterns=('*.rar',),
    magic=(
        # RAR 1.5 -- 4.0
        b'\x52\x61\x72\x21\x1A\x07\x00',
        # RAR 5+
        b'\x52\x61\x72\x21\x1A\x07\x01\x00',
    ),
)
class RARContainer(LibArchiveContainer):
    pass


@containers.register(
    name='7zip',
    patterns=('*.7z',),
    magic=(
        b'7z\xBC\xAF\x27\x1C',
    ),
)
class SevenZipContainer(LibArchiveContainer):
    pass


@containers.register(
    name='cabinet',
    patterns=('*.cab',),
    magic=(
        b'MSCF',
    ),
)
class CabinetContainer(LibArchiveContainer):
    pass


@containers.register(
    name='iso9660',
    patterns=('*.iso',),
)
class ISO9660Container(LibArchiveContainer):
    pass
