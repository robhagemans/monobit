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
from .charmaps import Unicode, EncoderLoader
from .taggers import (
    Tagmap, CharTagger, CodepointTagger,
    UnicodeNameTagger, DescriptionTagger,
    FallbackTagger, AdobeFallbackTagger, SGMLFallbackTagger,
)
from . import tables


def register_charmaps(charmaps):
    """Register charmap files"""
    for _name, _dict in json.loads((files(tables) / 'charmaps.json').read_text()).items():
        charmap = EncoderLoader(
            name=_name, filename=_dict['filename'],
            format=_dict.get('format', None),
            **_dict.get('kwargs', {}),
        )
        if 'range' in _dict:
            charmap = charmap.subset(_dict['range'])
        # overlays must be defined first
        for _overlay in _dict.get('overlays', ()):
            charmap |= charmaps.getter(_overlay)
        aliases = (_name, *_dict.get('aliases', ()))
        charmaps[aliases] = charmap


encodings = EncodingRegistry()

# unicode aliases
encodings['unicode', 'ucs', 'iso10646', 'iso10646-1'] = Unicode()

register_charmaps(encodings)


###############################################################################

for tagmap in (
        CharTagger(),
        CodepointTagger(),
        UnicodeNameTagger(),
        DescriptionTagger(),
    ):
    encodings[tagmap.name] = tagmap


encodings['adobe'] = EncoderLoader(
    'agl/aglfn.txt', name='adobe', format='tagmap',
    separator=';', unicode_column=0, tag_column=1,
    fallback=AdobeFallbackTagger()
)

encodings['sgml'] = EncoderLoader(
    'misc/SGML.TXT', name='sgml', format='tagmap',
    separator='\t', unicode_column=2,
    fallback=SGMLFallbackTagger()
)

# truetype mapping is adobe mapping *but* with .null for NUL
# https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6post.html
encodings['truetype'] = EncoderLoader(
    'agl/aglfn.txt', name='truetype', format='tagmap',
    separator=';', unicode_column=0, tag_column=1,
    fallback=AdobeFallbackTagger()
) | Tagmap({'\0': '.null'})
