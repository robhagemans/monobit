"""
monobit.encoding - encoding classes

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import NotFoundError, EncodingName
from .registry import CharmapRegistry
from .charmaps import register_charmaps, Charmap, Unicode
from .base import Encoder
from .indexers import Indexer
from .taggers import Tagger, tagger, tagmaps
from ..labels import to_labels


# for use in function annotations
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
        return Charmap.load(initialiser)
    except NotFoundError:
        return None


charmaps = CharmapRegistry()
charmaps.add_type('index', Indexer)

# unicode aliases
charmaps.add_type('unicode', Unicode)
charmaps.alias('ucs', 'unicode')
charmaps.alias('iso10646', 'unicode')
charmaps.alias('iso10646-1', 'unicode')

register_charmaps(charmaps)
