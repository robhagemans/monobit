"""
monobit.pack - collection of fonts

(c) 2019--2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .font import Font


class Pack:
    """Holds one or more potentially unrelated fonts."""

    def __init__(self, fonts=()):
        """Create pack from sequence of fonts."""
        if isinstance(fonts, Font):
            fonts = fonts,
        self._fonts = tuple(fonts)

    def __repr__(self):
        """Representation."""
        return 'Pack' + repr(self._fonts)

    def __len__(self):
        return len(self._fonts)

    def __iter__(self):
        return iter(self._fonts)

    def __getitem__(self, index):
        return self._fonts[index]

    def __add__(self, other):
        return Pack(self._fonts + Pack(other)._fonts)

    def select(self, **properties):
        """Get a subset from the pack by property. E.g. select(name='Times')."""
        return Pack(
            _font
            for _font in self._fonts
            if all(
                getattr(_font, _property) == _value
                for _property, _value in properties.items()
            )
        )

    def list_by(self, property):
        """List property of fonts in collection."""
        return tuple(getattr(_font, property) for _font in self._fonts)
