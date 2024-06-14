"""
monobit.storage.containers.uselibarchive - archive formats supported by libarchive

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from pathlib import Path

try:
    import libarchive
    from libarchive.entry import FileType
except importError:
    libarchive = None

from ..magic import FileFormatError
from ..base import containers
from ..containers.containers import FlatFilterContainer


if libarchive:

    class LibArchiveContainer(FlatFilterContainer):
        """Container for formats supported by libarchive."""

        def __init__(self, stream, mode='r'):
            """Container access using libarchive."""
            super().__init__(stream, mode)

        @classmethod
        def encode_all(cls, data, outstream):
            format = cls.libarchive_format
            if not format:
                raise ValueError(f'Writing not supported for this format.')
            with libarchive.custom_writer(outstream.write, format) as archive:
                for name, payload in data.items():
                    archive.add_file_from_memory(name, len(payload), payload)

        @classmethod
        def decode_all(cls, instream):
            """Read all items from archive."""
            data = {}
            try:
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
            except libarchive.ArchiveError as e:
                raise FileFormatError(e) from e
            return data


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
        libarchive_format = '7zip'


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
        libarchive_format = 'iso9660'


    @containers.register(
        name='lharc',
        patterns=('*.lha', '*.lzh'),
    )
    class LHArcContainer(LibArchiveContainer):
        pass


    @containers.register(
        name='cpio',
        patterns=('*.cpio',),
        magic=(
            b'\x71\xC7',
            b'\xC7\x71',
            b'0707',
        ),
    )
    class CPIOContainer(LibArchiveContainer):
        libarchive_format = 'cpio'


    @containers.register(
        name='pax',
        patterns=('*.pax',),
    )
    class PaxContainer(LibArchiveContainer):
        libarchive_format = 'pax'


    @containers.register(
        name='ar',
        patterns=('*.ar',),
        magic=(b'!<arch>\n',),
    )
    class ArContainer(LibArchiveContainer):
        libarchive_format = 'ar'


    @containers.register(
        name='xar',
        patterns=('*.xar',),
        magic=(b'xar!',),
    )
    class XArContainer(LibArchiveContainer):
        libarchive_format = 'xar'


    @containers.register(
        name='warc',
        patterns=('*.warc',),
        magic=(b'WARC/',),
    )
    class WARCContainer(LibArchiveContainer):
        libarchive_format = 'warc'
