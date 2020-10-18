"""
monobit.pack - representation of collection of fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import logging
from functools import wraps
from contextlib import contextmanager
from pathlib import Path

from .base import (
    VERSION, DEFAULT_FORMAT, scriptable,
    DirContainer, ZipContainer, TextMultiStream, unique_name
)
from .font import Font


class Pack:
    """Holds one or more potentially unrelated fonts."""

    def __init__(self, fonts=()):
        """Create pack from sequence of fonts."""
        self._fonts = tuple(fonts)

    def __iter__(self):
        """Iterate over fonts in pack."""
        return iter(self._fonts)

    def __len__(self):
        """Number of fonts in pack."""
        return len(self._fonts)

    def __repr__(self):
        """Representation."""
        if self.names:
            return "<Pack \n    '" + "'\n    '".join(self.names) + "'\n>"
        return '<empty Pack>'

    def __getitem__(self, item):
        """Get a font by number."""
        if isinstance(item, str):
            for _font in self._fonts:
                if _font.name == item:
                    return _font
            raise KeyError(f'No font named {item} in collection.')
        return self._fonts[item]

    @property
    def names(self):
        """List names of fonts in collection."""
        return [_font.name for _font in self._fonts]

    # inject Font operations into Pack

    for _name, _func in Font.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a pack with modified fonts."""
                fonts = [
                    operation(_font, *args, **kwargs)
                    for _font in self._fonts
                ]
                return Pack(fonts)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
