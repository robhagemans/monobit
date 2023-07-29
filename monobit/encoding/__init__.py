"""
monobit.encoding - encoding classes

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import NotFoundError, EncodingName
from .registry import EncodingRegistry
from .charmaps import Charmap, LoadableCharmap, Unicode
from .base import Encoder
from .indexers import Indexer
from .taggers import Tagmap, LoadableTagmap
from .definitions import encodings
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
        return encodings[initialiser]
    except KeyError:
        pass
    try:
        return LoadableCharmap(initialiser)
    except NotFoundError:
        pass
    try:
        return LoadableTagmap(initialiser)
    except NotFoundError:
        return None
