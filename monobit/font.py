"""
monobit.font - representation of font

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import scriptable
from .glyph import Glyph


class Font:
    """Representation of font glyphs and metadata."""

    def __init__(self, glyphs, labels=None, comments=(), properties=None):
        """Create new font."""
        self._glyphs = tuple(glyphs)
        if not labels:
            labels = {_i: _i for _i in range(len(glyphs))}
        self._labels = labels
        if isinstance(comments, dict):
            # per-property comments
            self._comments = comments
        else:
            # global comments only
            self._comments = {None: comments}
        self._properties = properties or {}

    def __iter__(self):
        """Iterate over labels, glyph pairs."""
        for index, glyph in enumerate(self._glyphs):
            labels = tuple(_label for _label, _index in self._labels.items() if _index == index)
            yield labels, glyph

    @property
    def max_ordinal(self):
        """Get maximum ordinal in font."""
        ordinals = self.ordinals
        if ordinals:
            return max(ordinals)
        return -1

    @property
    def ordinal_range(self):
        """Get range of ordinals."""
        return range(0, self.max_ordinal + 1)

    @property
    def ordinals(self):
        """Get tuple of defined ordinals."""
        default_key = self._labels.get(None, None)
        return sorted(_k for _k in self._labels if isinstance(_k, int) and _k != default_key)

    @property
    def all_ordinal(self):
        """All glyphs except the default have ordinals."""
        default_key = self._labels.get(None, None)
        return set(self._labels) - set(self.ordinals) <= set([default_key])

    @property
    def number_glyphs(self):
        """Get number of glyphs in font."""
        return len(self._glyphs)

    @property
    def fixed(self):
        """Font is fixed width."""
        sizes = set((_glyph.width, _glyph.height) for _glyph in self._glyphs)
        return len(sizes) <= 1

    @property
    def max_width(self):
        """Get maximum width."""
        return max(_glyph.width for _glyph in self._glyphs)

    @property
    def max_height(self):
        """Get maximum height."""
        return max(_glyph.height for _glyph in self._glyphs)

    def get_glyph(self, key, default=True):
        """Get glyph by key, default if not present."""
        try:
            index = self._labels[key]
        except KeyError:
            if not default:
                raise
            return self.get_default_glyph()
        return self._glyphs[index]

    def get_default_glyph(self):
        """Get default glyph."""
        try:
            default_key = self._labels[None]
            return self._glyphs[default_key]
        except KeyError:
            return Glyph.empty(self.max_width, self.max_height)


    ##########################################################################
    @scriptable
    def renumber(self, add:int=0):
        """Return a font with renumbered keys."""
        labels = {
            (_k + add if isinstance(_k, int) else _k): _v
            for _k, _v in self._labels.items()
        }
        return Font(self._glyphs, labels, self._comments, self._properties)

    @scriptable
    def subrange(self, from_:int=0, to_:int=None):
        """Return a continuous subrange of the font."""
        return self.subset(range(from_, to_))

    @scriptable
    def subset(self, keys:set=None):
        """Return a subset of the font."""
        if keys is None:
            keys = self._labels.keys()
        labels = {_k: _v for _k, _v in self._labels.items() if _k in keys}
        indexes = sorted(set(_v for _k, _v in self._labels.items()))
        glyphs = [self._glyphs[_i] for _i in indexes]
        return Font(glyphs, labels, self._comments, self._properties)

    # inject Glyph operations into Font

    for _name, _func in Glyph.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a font with modified glyphs."""
                glyphs = [
                    operation(_glyph, *args, **kwargs)
                    for _glyph in self._glyphs
                ]
                return Font(glyphs, self._comments, self._properties)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
