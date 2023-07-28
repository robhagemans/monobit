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
from .taggers import (
    LoadableTagmap, CharTagger, CodepointTagger,
    UnicodeNameTagger, DescriptionTagger,
    FallbackTagger, AdobeFallbackTagger, SGMLFallbackTagger,
)
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


###############################################################################

# truetype mapping is adobe mapping *but* with .null for NUL
# https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6post.html
_truetype = LoadableTagmap(
    'agl/aglfn.txt', name='truetype',
    separator=';', unicode_column=0, tag_column=1,
    fallback=AdobeFallbackTagger()
)
_truetype._chr2tag['\0'] = '.null'


for tagmap in (
        CharTagger(),
        CodepointTagger(),
        UnicodeNameTagger(),
        DescriptionTagger(),
        LoadableTagmap(
            'agl/aglfn.txt', name='adobe',
            separator=';', unicode_column=0, tag_column=1,
            fallback=AdobeFallbackTagger()
        ),
        LoadableTagmap(
            'misc/SGML.TXT', name='sgml', separator='\t', unicode_column=2,
            fallback=SGMLFallbackTagger()
        ),
        _truetype,
    ):
    encodings[tagmap.name] = tagmap
