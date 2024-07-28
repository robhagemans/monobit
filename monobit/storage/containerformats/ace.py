"""
monobit.storage.containers.ace - ace aechive reader

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import PurePosixPath

try:
    import acefile
except ImportError:
    acefile = None

from ..magic import FileFormatError, Magic
from ..base import containers
from ..streams import Stream
from ..containers import Archive


if acefile:

    @containers.register(
        name='ace',
        patterns=('*.ace',),
        magic=(
            Magic.offset(7) + b'**ACE**',
        ),
    )
    class AceContainer(Archive):
        """Container for ACE archives."""

        def __init__(self, stream, mode='r'):
            """Read ACE archives."""
            if mode != 'r':
                raise ValueError('Writing to ACE archives not supported')
            super().__init__(stream, mode)
            self._archive = acefile.open(stream)
            self._entries = tuple(self._archive)

        def close(self):
            """Close the archive."""
            if self.closed:
                return
            try:
                self._archive.close()
            except EnvironmentError as e:
                logging.debug(e)
            self._entries = ()
            super().close()

        def list(self):
            entries =  tuple(
                f'{_e.filename}/' if _e.is_dir() else _e.filename
                for _e in self._entries
            )
            return entries

        def decode(self, name, *, password:bytes=None):
            """
            Extract file from ACE archive.

            password: password for encrypted archive entry.
            """
            filename = str(PurePosixPath(self.root) / name)
            try:
                for entry in self._entries:
                    if entry.filename == filename:
                        if entry.is_dir():
                            raise IsADirectoryError(
                                f"Entry '{filename}' is a directory in archive {self}"
                            )
                        data = self._archive.read(entry, pwd=password)
                        return Stream.from_data(data, mode='r', name=name)
            except acefile.AceError as e:
                raise FileFormatError(e) from e
            raise FileNotFoundError(
                f"Entry '{filename}' not found in archive {self}"
            )

        def encode(self, name):
            """Writing to ACE archives not supported."""
            raise ValueError(f'Writing to ACE archives not supported.')
