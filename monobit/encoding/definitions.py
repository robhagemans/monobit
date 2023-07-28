"""
monobit.encoding.definitions - character map definitions

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import json
import logging
from pathlib import Path
from importlib.resources import files

from .charmaps import LoadableCharmap
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
        charmaps.register(charmap, name=_name)
        for _alias in _dict.get('aliases', ()):
            charmaps.alias(_alias, _name)
