"""
monobit.encoding.registry - encoding registry

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .base import normalise_name, NotFoundError
from .charmaps import Charmap


###################################################################################################
# charmap registry


class CharmapRegistry:
    """Register and retrieve charmaps."""

    # table of user-registered or -overlaid charmaps
    _registered = {}

    # table of encoding aliases
    _aliases = {}

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

    @classmethod
    def register(cls, encoder):
        """Register a file to be loaded for a given charmap."""
        name = encoder.name
        normname = cls._normalise_for_match(name)
        if normname in cls._registered:
            logging.warning(
                f"Redefining character map '{name}'=='{cls._registered[normname].name}'."
            )
        cls._registered[normname] = encoder

    @classmethod
    def alias(cls, alias, name):
        """Define an alias for an encoding name."""
        name = cls._normalise_for_match(name)
        alias = cls._normalise_for_match(alias)
        if name == alias:
            # equal after normalisation
            return
        if alias in cls._registered:
            raise ValueError(
                f"Character set alias '{alias}' for '{name}' collides with registered name."
            )
        if alias in cls._aliases:
            logging.warning(
                'Redefining character set alias: now %s==%s (was %s).',
                alias, name, cls._aliases[alias]
            )
        cls._aliases[alias] = name

    @classmethod
    def is_unicode(cls, name):
        """Encoding name is equivalent to unicode."""
        return cls.match(name, 'unicode')

    normalise = staticmethod(normalise_name)

    @classmethod
    def match(cls, name1, name2):
        """Check if two names match."""
        return cls._normalise_for_match(name1) == cls._normalise_for_match(name2)

    @classmethod
    def _normalise_for_match(cls, name):
        """Further normalise names to base form and apply aliases for matching."""
        # all lowercase
        name = name.lower()
        # remove spaces, dashes and dots
        for char in '._- ':
            name = name.replace(char, '')
        try:
            # anything that's in the alias table
            return cls._aliases[name]
        except KeyError:
            pass
        # try replacements
        for start, replacement in cls._patterns.items():
            if name.startswith(start):
                name = replacement + name[len(start):]
                break
        # found in table after replacement?
        return cls._aliases.get(name, name)

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
