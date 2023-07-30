"""
monobit.encoding.registry - encoding registry

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from functools import partial

from .base import normalise_name, NotFoundError
from .base import Encoder
from .charmaps import Charmap, Unicode


class EncodingRegistry:
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
        self._index = {}
        self._encoders = []

    def __setitem__(self, names, encoder_or_callable):
        """Register an encoder to one or more aliases."""
        if isinstance(names, str):
            aliases = (names,)
        else:
            aliases = names
        for name in aliases:
            normname = self._normalise_for_match(name)
            if normname in self._index:
                logging.warning(f"Redefining encoder '{name}'~'{normname}'")
            self._index[normname] = len(self._encoders)
        self._encoders.append(encoder_or_callable)

    def _get_index(self, name):
        """Get index from registry by name; raise NotFoundError if not found."""
        normname = self._normalise_for_match(name)
        try:
            return self._index[normname]
        except KeyError as exc:
            raise NotFoundError(
                f"No registered character map matches '{name}' ['{normname}']."
            ) from exc

    def getter(self, name):
        """Get charmap or builder from registry by name; raise NotFoundError if not found."""
        index = self._get_index(name)
        return self._encoders[index]

    def __getitem__(self, name):
        index = self._get_index(name)
        encoder = self._encoders[index]
        """Get charmap from registry by name; raise NotFoundError if not found."""
        # must be either an Encoder or a callable that produces one
        if not isinstance(encoder, Encoder):
            encoder = encoder()
            self._encoders[index] = encoder
        return encoder


    ## to EncodingName

    @classmethod
    def match(cls, name1, name2):
        """Check if two names match."""
        return cls._normalise_for_match(name1) == cls._normalise_for_match(name2)

    @classmethod
    def _normalise_for_match(cls, name):
        """Further normalise names to base form."""
        # all lowercase
        name = name.lower()
        # remove spaces, dashes and dots
        for char in '._- ':
            name = name.replace(char, '')
        # try replacements
        for start, replacement in cls._patterns.items():
            if name.startswith(start):
                name = replacement + name[len(start):]
                break
        return name

    ###

    def is_unicode(self, name):
        """Encoding name is equivalent to unicode."""
        try:
            return isinstance(self[name], Unicode)
        except NotFoundError:
            return False

    normalise = staticmethod(normalise_name)

    def __iter__(self):
        """Iterate over names of registered charmaps."""
        return iter(self._index.keys())

    def fit(self, charmap):
        """Return best-fit registered charmap."""
        min_dist = len(charmap)
        fit = Charmap()
        for registered in self:
            registered_map = self[registered]
            if not isinstance(registered_map, Charmap):
                continue
            dist = charmap.distance(registered_map)
            if dist == 0:
                return registered_map
            elif dist < min_dist:
                min_dist = dist
                fit = registered_map
        return fit
