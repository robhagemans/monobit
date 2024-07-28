"""
monobit.storage.containers.apple - AppleSingle and AppleDouble containers

(c) 2021--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from monobit.base.struct import big_endian as be
from ..streams import Stream
from ..magic import FileFormatError, Magic
from ..base import containers
from ..containers import FlatFilterContainer


##############################################################################
# AppleSingle/AppleDouble container
# v1: see https://web.archive.org/web/20160304101440/http://kaiser-edv.de/documents/Applesingle_AppleDouble_v1.html
# v2: https://web.archive.org/web/20160303215152/http://kaiser-edv.de/documents/AppleSingle_AppleDouble.pdf
# the difference between v1 and v2 affects the file info sections
# not the resource fork which is what we care about

_APPLESINGLE_MAGIC = 0x00051600
_APPLEDOUBLE_MAGIC = 0x00051607


_APPLE_HEADER = be.Struct(
    magic='uint32',
    version='uint32',
    home_fs='16s',
    number_entities='uint16',
)
_APPLE_ENTRY = be.Struct(
    entry_id='uint32',
    offset='uint32',
    length='uint32',
)

# Entry IDs
_ID_DATA = 1
_ID_RESOURCE = 2
_ID_NAME = 3

_APPLE_ENTRY_TYPES = {
    1: 'data fork',
    2: 'resource fork',
    3: 'real name',
    4: 'comment',
    5: 'icon, b&w',
    6: 'icon, color',
    7: 'file info', # v1 only
    8: 'file dates info', # v2
    9: 'finder info',
    # the following are all v2
    10: 'macintosh file info',
    11: 'prodos file info',
    12: 'ms-dos file info',
    13: 'short name',
    14: 'afp file info',
    15: 'directory id',
}


class AppleContainer(FlatFilterContainer):


    def decode(self, name):
        """
        Decode data and resource fork from AppleSingle/AppeDouble container.
        """
        return super().decode(name)

    def encode(self, name):
        """
        Writing to AppleSingle/AppleDouble is not supported.
        """
        raise ValueError(
            'Writing to AppleSingle/AppleDouble is not supported.'
        )

    def decode_all(self, stream):
        """Parse an AppleSingle or AppleDouble file."""
        data = stream.read()
        header = _APPLE_HEADER.from_bytes(data)
        if header.magic == _APPLESINGLE_MAGIC:
            container = 'AppleSingle'
        elif header.magic == _APPLEDOUBLE_MAGIC:
            container = 'AppleDouble'
        else:
            raise FileFormatError('Not an AppleSingle or AppleDouble file.')
        entry_array = _APPLE_ENTRY.array(header.number_entities)
        entries = entry_array.from_bytes(data, _APPLE_HEADER.size)
        name, data_fork, rsrc_fork = '', b'', b''
        for i, entry in enumerate(entries):
            entry_type = _APPLE_ENTRY_TYPES.get(entry.entry_id, 'unknown')
            logging.debug(
                '%s container: entry #%d, %s [%d]',
                container, i, entry_type, entry.entry_id
            )
            if entry.entry_id == _ID_RESOURCE:
                rsrc_fork = data[entry.offset:entry.offset+entry.length]
            if entry.entry_id == _ID_DATA:
                data_fork = data[entry.offset:entry.offset+entry.length]
            if entry.entry_id == _ID_NAME:
                name = data[entry.offset:entry.offset+entry.length]
                name = name.decode('mac-roman')
        if name:
            return {
                f'data/{name}': data_fork,
                f'rsrc/{name}': rsrc_fork,
            }
        else:
            return {
                f'data': data_fork,
                f'rsrc': rsrc_fork,
            }


containers.register(
    name='apple1',
    magic=(
        _APPLESINGLE_MAGIC.to_bytes(4, 'big'),
    ),
    patterns=('*.as',),
)(AppleContainer)

containers.register(
    name='apple2',
    magic=(
        _APPLEDOUBLE_MAGIC.to_bytes(4, 'big'),
    ),
    # .adf, .rsrc - per http://fileformats.archiveteam.org/wiki/AppleDouble
    # ._<name> is OS X representation
    patterns=('*.adf', '*.rsrc', '._*'),
)(AppleContainer)
