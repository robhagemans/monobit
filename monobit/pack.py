"""
monobit.pack - collection of fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .font import Font, FontProperties
from .scripting import scriptable, get_scriptables


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

    @scriptable(pack_operation=True)
    def get(self, index:int=0):
        """
        Get a single-font pack by index.

        index: which font to pick; 0 is first, -1 is last (default: zero)
        """
        return self[index]

    @scriptable(
        pack_operation=True,
        script_args=FontProperties.__annotations__.items()
    )
    def select(self, **properties):
        """Get a subset of fonts from the pack by property. E.g. select(name='Times')."""
        return Pack(
            _font
            for _font in self
            if all(
                getattr(_font, _property) == _value
                for _property, _value in properties.items()
            )
        )

    def list_by(self, property):
        """List property of fonts in collection."""
        return tuple(getattr(_font, property) for _font in self._fonts)

    def itergroups(self, property):
        """Iterate over subpacks with one value for a property."""
        for value in sorted(set(self.list_by(property))):
            yield value, self.select(**{property: value})


# scriptable font/glyph operations
operations = get_scriptables(Pack)
