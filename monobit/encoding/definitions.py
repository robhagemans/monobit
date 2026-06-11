"""
monobit.encoding.definitions - character map definitions

(c) 2020--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import json
import logging
from pathlib import Path
from importlib.resources import files

from .registry import EncodingRegistry
from .charmaps import Unicode, EncoderLoader, Charmap
from .taggers import (
    Tagmap, CharTagger, CodepointTagger,
    UnicodeNameTagger, DescriptionTagger,
    FallbackTagger, AdobeFallbackTagger, SGMLFallbackTagger,
)
from . import tables


def register_charmaps(charmaps):
    """Register charmap files"""
    for _name, _dict in json.loads((files(tables) / 'charmaps.json').read_text()).items():
        if 'filename' in _dict:
            charmap = EncoderLoader(
                name=_name, filename=_dict['filename'],
                format=_dict.get('format', None),
                **_dict.get('kwargs', {}),
            )
        else:
            charmap = Charmap()
        if 'range' in _dict:
            charmap = charmap.subset(_dict['range'])
        # overlays must be defined first
        for _overlay in _dict.get('overlays', ()):
            charmap |= charmaps.getter(_overlay)
        aliases = (_name, *_dict.get('aliases', ()))
        charmaps[aliases] = charmap


def create_encoding_registry():
    # unicode aliases
    encodings = EncodingRegistry()

    encodings['unicode', 'ucs', 'iso10646', 'iso10646-1'] = Unicode()

    register_charmaps(encodings)

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

    return encodings


class LazyEncodingRegistry():

    _registry = None

    def _build(self):
        self._registry = create_encoding_registry()

    def __getattr__(self, attr):
        if self._registry is None:
            self._build()
        return getattr(self._registry, attr)


for _dunder in ('__getitem__', '__setitem__', '__iter__'):

    def _create_delegate(dunder):
        def _delegated_fn(self, *args, **kwargs):
            if self._registry is None:
                self._build()
            fn = getattr(self._registry, dunder)
            return fn(*args, **kwargs)
        return _delegated_fn

    fn = _create_delegate(_dunder)
    setattr(LazyEncodingRegistry, _dunder, fn)


encodings = LazyEncodingRegistry()

###############################################################################
