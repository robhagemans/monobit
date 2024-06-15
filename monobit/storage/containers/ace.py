"""
monobit.storage.containers.ace - ace aechive reader

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

try:
    import acefile
except ImportError:
    acefile = None

from ..magic import FileFormatError, Magic
from ..base import containers
from ..containers.containers import FlatFilterContainer


if acefile:

    @containers.register(
        name='ace',
        patterns=('*.ace',),
        magic=(
            Magic.offset(7) + b'**ACE**',
        ),
    )
    class AceContainer(FlatFilterContainer):
        """Container for ACE archives."""

        def __init__(self, stream, mode='r', *, password:bytes=None):
            """
            ACE container access.

            password: password for encrypted archive entries. Individual per-file passwords not supported.
            """
            self._pwd = password
            super().__init__(stream, mode)

        def encode_all(self, data, outstream):
            """Write all items to archive."""
            raise ValueError(f'Writing to ACE archives not supported.')

        def decode_all(self, instream):
            """Read all items from archive."""
            data = {}
            try:
                with acefile.open(instream) as archive:
                    for entry in archive:
                        logging.debug(
                            "ACE file '%s' entry '%s'",
                            instream.name, entry.filename
                        )
                        name = entry.filename
                        if name == '.':
                            continue
                        if entry.is_dir():
                            data[name + '/'] = b''
                        else:
                            data[name] = archive.read(entry, pwd=self._pwd)
                        for path in Path(name).parents:
                            if path != Path('.'):
                                data[f'{path}/'] = b''
            except acefile.AceError as e:
                raise FileFormatError(e) from e
            return data
