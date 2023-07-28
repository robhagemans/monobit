"""
monobit.encoding.definitions - character map definitions

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import json
import logging
from pathlib import Path
from importlib.resources import files

from .registry import EncodingRegistry
from .charmaps import LoadableCharmap, Unicode
from .taggers import TAGMAPS
from . import tables


def register_charmaps(charmaps):
    """Register charmap files"""
    for _name, _dict in json.loads((files(tables) / 'charmaps.json').read_text()).items():
        charmap = LoadableCharmap(
            name=_name, filename=_dict['filename'],
            format=_dict.get('format', None),
            **_dict.get('kwargs', {}),
        )
        if 'range' in _dict:
            charmap = charmap.subset(_dict['range'])
        # overlays must be defined first
        for _overlay in _dict.get('overlays', ()):
            charmap |= charmaps[_overlay]
        charmaps[_name] = charmap
        for _alias in _dict.get('aliases', ()):
            charmaps[_alias] = charmap


encodings = EncodingRegistry()
# encodings.register(Indexer())

# unicode aliases
encodings['unicode'] = Unicode()
encodings['ucs'] = encodings['unicode']
encodings['iso10646'] = encodings['unicode']
encodings['iso10646-1'] = encodings['unicode']

register_charmaps(encodings)

for tagmap in TAGMAPS:
    encodings[tagmap.name] = tagmap
