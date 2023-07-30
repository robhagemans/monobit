"""
monobit.encoding.registry - encoding registry

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from functools import partial

from .base import Encoder, EncodingName, NotFoundError
from .charmaps import Charmap, Unicode


class EncodingRegistry:
    """Register and retrieve charmaps."""

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
            normname = EncodingName(name)
            if normname in self._index:
                logging.warning(f"Redefining encoder '{normname}'")
            self._index[normname] = len(self._encoders)
        self._encoders.append(encoder_or_callable)

    def _get_index(self, name):
        """Get index from registry by name; raise NotFoundError if not found."""
        normname = EncodingName(name)
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

    ###

    def is_unicode(self, name):
        """Encoding name is equivalent to unicode."""
        try:
            return isinstance(self[name], Unicode)
        except NotFoundError:
            return False

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
