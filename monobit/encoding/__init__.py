"""
monobit.encoding - encoding classes

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from pathlib import Path

from .base import NotFoundError, EncodingName
from .registry import EncodingRegistry
from .charmaps import Charmap, Unicode, EncoderLoader
from .base import Encoder
from .indexers import Indexer
from .taggers import Tagmap
from .definitions import encodings
from ..core.labels import to_labels


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
    # if not registered, see if it is a file spec we can load
    filename, _, format = initialiser.partition(':')
    if not format:
        format = Path(filename).suffix[1:]
    try:
        if format == 'tbl':
            return Indexer.load(filename)
        return EncoderLoader(filename, format=format)()
    except (EnvironmentError, NotFoundError):
        return None
