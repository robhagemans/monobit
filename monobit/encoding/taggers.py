"""
monobit.encoding.taggers - glyph tagging

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata
from pathlib import Path
from importlib.resources import files
from functools import partial, cached_property

from ..unicode import unicode_name, is_printable
from ..labels import to_label, Tag, Char, Codepoint
from ..properties import reverse_dict
from .base import NotFoundError, Encoder
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
    """Algorithmically generatte tags."""

    def __init__(self, unmapped='glyph{count:04}'):
        """Set up mapping."""
        super().__init__(name='fallback')
        self._pattern = unmapped
        self._count = -1

    def tag(self, *labels):
        """Get value from tagmap."""
        self._pattern += 1
        return self._pattern.format(
            count=self._count,
            char=_get_char(labels),
            codepoint=_get_codepoint(labels),
            tag=_get_tag(labels),
        )


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


class BaseTagmap(Encoder):

    def __init__(self, *, name='', fallback=None):
        super().__init__(name)
        self._fallback = fallback or FallbackTagger()

    @cached_property
    def _chr2tag(self):
        raise NotImplementedError()

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


class Tagmap(BaseTagmap):
    """Tag on the basis of a mapping table."""

    def __init__(self, mapping, name='', fallback=None):
        """Set up mapping."""
        super().__init__(name=name, fallback=fallback)
        self._chr2tag = mapping


class LoadableTagmap(BaseTagmap):
    """Tag on the basis of a mapping table from a file."""

    def __init__(self, filename, *, name='', fallback=None, **kwargs):
        """Create new charmap from file."""
        if not name:
            name = Path(filename).stem
        super().__init__(name=name, fallback=fallback)
        try:
            self._load_path = (files(tables) / filename)
        except EnvironmentError as exc:
            raise NotFoundError(f'Could not load tagmap file `{filename}`: {exc}')
        if not self._load_path.exists():
            raise NotFoundError(f'Charmap file `{filename}` does not exist')
        self._load_kwargs = kwargs

    @cached_property
    def _chr2tag(self):
        data = self._load_path.read_bytes()
        if not data:
            raise NotFoundError(f'No data in tagmap file `{self._load_path}`.')
        return _read_tagmap(data, **self._load_kwargs)


###################################################################################################
# tag map format readers

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
