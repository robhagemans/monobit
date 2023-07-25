"""
monobit.encoding.registry - encoding registry

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..labels import Char, to_labels
from .base import normalise_name, NotFoundError
from .charmaps import Unicode, Charmap
from .base import Encoder
from .indexers import Indexer


###################################################################################################
# charmap registry


class CharmapRegistry:
    """Register and retrieve charmaps."""

    # table of user-registered or -overlaid charmaps
    _registered = {}
    _overlays = {}

    # directly stored encoders
    _stored = {}

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
    def register(cls, name, filename, format=None, **kwargs):
        """Register a file to be loaded for a given charmap."""
        normname = cls._normalise_for_match(name)
        if normname in cls._registered:
            logging.warning(
                f"Redefining character map '{name}'=='{cls._registered[normname]['name']}'."
            )
        if normname in cls._overlays:
            del cls._overlays[normname]
        cls._registered[normname] = dict(name=name, filename=filename, format=format, **kwargs)

    @classmethod
    def add_type(cls, name, encoder_class):
        """Add an encoder class to the registry."""
        normname = cls._normalise_for_match(name)
        if normname in cls._registered:
            logging.warning(
                f"Redefining character map '{name}'=='{cls._registered[normname]['name']}'."
            )
        cls._stored[normname] = encoder_class

    @classmethod
    def overlay(cls, name, filename, overlay_range, format=None, **kwargs):
        """Overlay a given charmap with an additional file."""
        normname = cls._normalise_for_match(name)
        ovr_dict = dict(
            name=name, filename=filename, format=format, codepoint_range=overlay_range,
            **kwargs
        )
        try:
            cls._overlays[normname].append(ovr_dict)
        except KeyError:
            cls._overlays[normname] = [(ovr_dict)]

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

    @staticmethod
    def load(*args, **kwargs):
        """Create new charmap from file."""
        return Charmap.load(*args, **kwargs)

    @staticmethod
    def create(*args, **kwargs):
        """Create new charmap from mapping."""
        return Charmap(*args, **kwargs)

    def __iter__(self):
        """Iterate over names of registered charmaps."""
        return iter(_v['name'] for _v in self._registered.values())

    def __getitem__(self, name):
        """Get charmap from registry by name; raise NotFoundError if not found."""
        normname = self._normalise_for_match(name)
        try:
            return self._stored[normname]()
        except KeyError:
            pass
        try:
            charmap_dict = self._registered[normname]
        except KeyError as exc:
            raise NotFoundError(
                f"No registered character map matches '{name}' ['{normname}']."
            ) from None
        charmap = self.load(**charmap_dict)
        for ovr_dict in self._overlays.get(normname, ()):
            # copy so pop() doesn't change the stored dict
            ovr_dict = {**ovr_dict}
            ovr_rng = ovr_dict.pop('codepoint_range')
            overlay = self.load(**ovr_dict)
            charmap = charmap.overlay(overlay, ovr_rng)
        return charmap

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

    def __repr__(self):
        """String representation."""
        return (
            "CharmapRegistry('"
            + "', '".join(self)
            + "')"
        )
