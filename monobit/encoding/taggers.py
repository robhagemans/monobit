"""
monobit.encoding.taggers - glyph tagging

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata
from pathlib import Path
from importlib.resources import files
from functools import partial, wraps, cached_property

from .unicode import unicode_name, is_printable
from ..core.labels import to_label, Tag, Char, Codepoint
from ..base import reverse_dict
from .base import NotFoundError, Encoder, register_reader
from . import tables


def _get_label(labels, labeltype):
    """Get first label of given type from list."""
    for label in labels:
        label = to_label(label)
        if isinstance(label, labeltype):
            return label
    return labeltype()

_get_char = partial(_get_label, labeltype=Char)
_get_codepoint = partial(_get_label, labeltype=Codepoint)
_get_tag = partial(_get_label, labeltype=Tag)


class UnicodeNameTagger(Encoder):
    """Tag with unicode name."""

    def __init__(self):
        super().__init__(name='name')

    def tag(self, *labels):
        """Get unicode glyph name."""
        char = _get_char(labels)
        if not char:
            return Tag()
        return Tag(unicode_name(char.value))

    def char(self, *labels):
        """Get char from unicode glyph name."""
        tag = _get_tag(labels)
        elements = tag.value.split(',')
        try:
            return Char(''.join(
                unicodedata.lookup(elem.strip())
                for elem in elements
            ))
        except KeyError:
            return Char()


class DescriptionTagger(Encoder):
    """Tag with unicode names and characters."""

    def __init__(self):
        super().__init__(name='desc')

    def tag(self, *labels):
        """Get unicode glyph name."""
        char = _get_char(labels)
        if not char:
            return Tag()
        char = char.value
        name = unicode_name(char)
        if is_printable(char):
            return Tag('[{}] {}'.format(char, name))
        return Tag(name)


class CharTagger(Encoder):
    """Tag with unicode characters."""

    def __init__(self):
        super().__init__(name='char')

    def tag(self, *labels):
        """Get printable char."""
        char = _get_char(labels).value
        if is_printable(char):
            return Tag(char)
        return Tag()


class FallbackTagger(Encoder):
    """Algorithmically generate tags."""

    def __init__(self, unmapped='glyph{count:04}'):
        """Set up mapping."""
        super().__init__(name='fallback')
        self._pattern = unmapped
        self._count = -1

    def tag(self, *labels):
        """Get value from tagmap."""
        self._count += 1
        return Tag(self._pattern.format(
            count=self._count,
            char=_get_char(labels),
            codepoint=_get_codepoint(labels),
            tag=_get_tag(labels),
        ))


class CodepointTagger(Encoder):
    """Tag with codepoint numbers."""

    def __init__(self, prefix=''):
        """Create codepoint tagger with prefix"""
        super().__init__(name='codepoint')
        self._prefix = prefix

    def tag(self, *labels):
        """Get codepoint string."""
        cp = _get_codepoint(labels)
        if not cp:
            return Tag()
        return Tag(f'{self._prefix}{cp}')


class Tagmap(Encoder):
    """Tag on the basis of a mapping table."""

    def __init__(self, mapping, name='', fallback=None):
        """Set up mapping."""
        super().__init__(name=name)
        self._chr2tag = mapping
        self._fallback = fallback or FallbackTagger()

    @cached_property
    def _tag2chr(self):
        return reverse_dict(self._chr2tag)

    def tag(self, *labels):
        """Get value from tagmap."""
        char = _get_char(labels)
        try:
            return Tag(self._chr2tag[char])
        except KeyError:
            return self._fallback.tag(*labels)

    def char(self, *labels):
        """Get char value from tagmap."""
        for label in labels:
            if isinstance(label, Tag):
                try:
                    return Char(self._tag2chr[label.value])
                except KeyError:
                    pass
        return Char()

    @property
    def mapping(self):
        return {**self._chr2tag}

    def __or__(self, other):
        """Return encoding overlaid with all characters defined in right-hand side."""
        return Tagmap(mapping=self._chr2tag | other._chr2tag, name=f'{self.name}')

    def table(self):
        """Mapping table"""
        return '\n'.join(
            f'u+{ord(_k):04X}: "{_v}"' for _k, _v in self._chr2tag.items()
        )

class AdobeFallbackTagger(Encoder):
    """Fallback tagger following AGL conventions."""

    def __init__(self):
        super().__init__(name='adobe-fallback')

    def tag(self, *labels):
        """Construct a default tag for unmapped glyphs."""
        char = _get_char(labels)
        # following agl recommendation for naming sequences
        cps = (ord(_c) for _c in char)
        return Tag('_'.join(
            f'uni{_cp:04X}' if _cp < 0x10000 else f'u{_cp:06X}'
            for _cp in cps
        ))


class SGMLFallbackTagger(Encoder):
    """Fallback tagger following SGML conventions."""

    def __init__(self):
        super().__init__(name='sgml-fallback')

    def tag(self, *labels):
        """Construct a default tag for unmapped glyphs."""
        char = _get_char(labels)
        cps = (ord(_c) for _c in char)
        # joining numeric references by semicolons
        # note that each entity should really start with & and end with ; e.g. &eacute;
        return Tag(';'.join(f'#{_cp:X}' for _cp in cps))


###################################################################################################
# tag map format readers

def _tagmap_loader(fn):
    """Decorator for the shared parts of tagmap loaders."""

    @wraps(fn)
    def _load(name, path, *args, fallback, **kwargs):
        try:
            data = path.read_bytes()
        except EnvironmentError as exc:
            raise NotFoundError(f'Could not load tagmap file `{str(path)}`: {exc}')
        if not data:
            raise NotFoundError(f'No data in tagmap file `{str(path)}`')
        mapping = fn(data, *args, **kwargs)
        return Tagmap(mapping, name=name, fallback=fallback)

    return _load


@register_reader('tagmap')
@_tagmap_loader
def _read_tagmap(data, separator=':', comment='#', joiner=',', tag_column=0, unicode_column=1):
    """Read a tag map from file data."""
    chr2tag = {}
    for line in data.decode('utf-8').splitlines():
        if line.startswith(comment):
            continue
        columns = line.split(separator)
        if len(columns) > max(tag_column, unicode_column):
            tag = columns[tag_column]
            unicode_str = columns[unicode_column]
            try:
                char = ''.join(chr(int(_str, 16)) for _str in unicode_str.split(joiner))
            except ValueError:
                pass
            else:
                chr2tag[char] = tag
    return chr2tag
