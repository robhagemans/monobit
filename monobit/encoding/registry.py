"""
monobit.encoding.registry - encoding registry

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .base import normalise_name, NotFoundError
from .charmaps import Charmap, Unicode


class CharmapRegistry:
    """Register and retrieve charmaps."""

    # replacement patterns for normalisation
    # longest first to avoid partial match
    _patterns = {
        'microsoftcp': 'windows',
        'microsoft': 'windows',
        'msdoscp': 'oem',
        'oemcp': 'oem',
        'msdos': 'oem',
        'ibmcp': 'ibm',
        'apple': 'mac',
        'macos': 'mac',
        'doscp': 'oem',
        'mscp': 'windows',
        'dos': 'oem',
        'pc': 'oem',
        'ms': 'windows',
        # mac-roman also known as x-mac-roman etc.
        'x': '',
    }

    def __init__(self):
        self._registered = {}

    def register(self, encoder):
        """Register a file to be loaded for a given charmap."""
        name = encoder.name
        normname = self._normalise_for_match(name)
        if normname in self._registered:
            logging.warning(
                f"Redefining character map '{name}'=='{self._registered[normname].name}'."
            )
        self._registered[normname] = encoder

    def alias(self, alias, name):
        """Define an alias for an encoding name."""
        name = self._normalise_for_match(name)
        alias = self._normalise_for_match(alias)
        if name == alias:
            # equal after normalisation
            return
        if alias in self._registered:
            logging.warning(
                f"Redefining character map alias '{alias}'."
            )
        self._registered[alias] = self._registered[name]

    def is_unicode(self, name):
        """Encoding name is equivalent to unicode."""
        try:
            return isinstance(self[name], Unicode)
        except NotFoundError:
            return False

    normalise = staticmethod(normalise_name)

    def match(self, name1, name2):
        """Check if two names match."""
        return self._normalise_for_match(name1) == self._normalise_for_match(name2)

    def _normalise_for_match(self, name):
        """Further normalise names to base form."""
        # all lowercase
        name = name.lower()
        # remove spaces, dashes and dots
        for char in '._- ':
            name = name.replace(char, '')
        # try replacements
        for start, replacement in self._patterns.items():
            if name.startswith(start):
                name = replacement + name[len(start):]
                break
        return name

    def __iter__(self):
        """Iterate over names of registered charmaps."""
        return iter(_v.name for _v in self._registered)

    def __getitem__(self, name):
        """Get charmap from registry by name; raise NotFoundError if not found."""
        normname = self._normalise_for_match(name)
        try:
            return self._registered[normname]
        except KeyError as exc:
            raise NotFoundError(
                f"No registered character map matches '{name}' ['{normname}']."
            ) from None

    def fit(self, charmap):
        """Return best-fit registered charmap."""
        min_dist = len(charmap)
        fit = Charmap()
        for registered in self:
            registered_map = self[registered]
            dist = charmap.distance(registered_map)
            if dist == 0:
                return registered_map
            elif dist < min_dist:
                min_dist = dist
                fit = registered_map
        return fit
