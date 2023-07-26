"""
monobit.encoding - encoding classes

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import NotFoundError, EncodingName
from .registry import CharmapRegistry
from .charmaps import register_charmaps, Charmap, LoadableCharmap, Unicode
from .base import Encoder
from .indexers import Indexer
from .taggers import tagmaps, Tagmap, LoadableTagmap
from ..labels import to_labels


def encoder(initialiser):
    """Retrieve or create a charmap from object or string."""
    if isinstance(initialiser, Encoder):
        return initialiser
    if initialiser is None or not str(initialiser):
        return None
    initialiser = str(initialiser)
    # numeric ranges - interpreted as indexer
    if initialiser[:1].isdigit():
        initialiser = to_labels(initialiser)
        return Indexer(code_range=initialiser)
    try:
        return charmaps[initialiser]
    except KeyError:
        pass
    try:
        return LoadableCharmap(initialiser)
    except NotFoundError:
        return None


def tagger(initialiser):
    """Retrieve or create a tagmap from object or string."""
    if isinstance(initialiser, Encoder):
        return initialiser
    if initialiser is None or not str(initialiser):
        return None
    initialiser = str(initialiser)
    try:
        return tagmaps[initialiser]
    except KeyError:
        pass
    return LoadableTagmap(initialiser)


charmaps = CharmapRegistry()
# charmaps.register(Indexer())

# unicode aliases
charmaps.register(Unicode())
charmaps.alias('ucs', 'unicode')
charmaps.alias('iso10646', 'unicode')
charmaps.alias('iso10646-1', 'unicode')

register_charmaps(charmaps)
