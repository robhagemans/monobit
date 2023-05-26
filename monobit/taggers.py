"""
monobit.taggers - glyph tagging

(c) 2020--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata
import pkgutil
from pathlib import Path

from .encoding import unicode_name, is_printable, NotFoundError
from .labels import to_label, Tag
from .properties import reverse_dict


class Tagger:
    """Add tags or comments to a font's glyphs."""

    name = 'unknown-tagger'

    def comment(self, *labels):
        raise NotImplementedError

    def tag(self, *labels):
        return Tag(self.comment(*labels))

    def __repr__(self):
        """Representation."""
        return f"{type(self).__name__}(name='{self.name}')"

    def __str__(self):
        """Yaff representation."""
        return self.name


def _get_char(labels):
    """Get first char label from list."""
    for label in labels:
        char = to_label(label)
        if isinstance(char, str):
            return char
    return ''

def _get_codepoint(labels):
    """Get first codepoint label from list."""
    for label in labels:
        cp = to_label(label)
        if isinstance(cp, bytes):
            return cp
    return b''


class UnicodeTagger(Tagger):
    """Tag with unicode names and characters."""

    def __init__(self, include_char=False):
        self.include_char = include_char
        if include_char:
            self.name = 'desc'
        else:
            self.name = 'name'

    def comment(self, *labels):
        """Get unicode glyph name."""
        char = _get_char(labels)
        if not char:
            return ''
        char = char.value
        name = unicode_name(char)
        if self.include_char and is_printable(char):
            return '[{}] {}'.format(char, name)
        return '{}'.format(name)


class CharTagger(Tagger):
    """Tag with unicode characters."""

    name = 'char'

    def comment(self, *labels):
        """Get printable char."""
        char = _get_char(labels).value
        if is_printable(char):
            return char
        return ''


class CodepointTagger(Tagger):
    """Tag with codepoint numbers."""

    name = 'codepoint'

    def __init__(self, prefix=''):
        """Create codepoint tagger with prefix"""
        self._prefix = prefix

    def comment(self, *labels):
        """Get codepoint string."""
        cp = _get_codepoint(labels)
        if not cp:
            return ''
        return f'{self._prefix}{cp}'


class MappingTagger(Tagger):
    """Tag on the basis of a mapping table."""

    def __init__(self, mapping, name=''):
        """Set up mapping."""
        self._chr2tag = mapping
        self._tag2chr = reverse_dict(mapping)
        self.name = name

    @classmethod
    def load(cls, filename, *, name='', **kwargs):
        """Create new charmap from file."""
        try:
            data = pkgutil.get_data(__name__, filename)
        except EnvironmentError as exc:
            raise NotFoundError(f'Could not load tagmap file `{filename}`: {exc}')
        if not data:
            raise NotFoundError(f'No data in tagmap file `{filename}`.')
        mapping = _read_tagmap(data, **kwargs)
        if not name:
            name = Path(filename).stem
        return cls(mapping, name=name)

    def comment(self, *labels):
        """Get value from tagmap."""
        char = _get_char(labels)
        try:
            return self._chr2tag[char]
        except KeyError:
            return self.get_default_tag(char)

    def get_default_tag(self, char):
        """Construct a default tag for unmapped glyphs."""
        return ''

    def char(self, *labels):
        """Get char value from tagmap."""
        for label in labels:
            if isinstance(label, Tag):
                try:
                    return self._tag2chr[label.value]
                except KeyError:
                    pass
        return ''


class AdobeTagger(MappingTagger):

    name = 'adobe'

    def get_default_tag(self, char):
        """Construct a default tag for unmapped glyphs."""
        if not char:
            return ''
        cps = [ord(_c) for _c in char]
        # following agl recommendation for naming sequences
        return '_'.join(f'uni{_cp:04X}' if _cp < 0x10000 else f'u{_cp:06X}' for _cp in cps)


class SGMLTagger(MappingTagger):

    name = 'sgml'

    def get_default_tag(self, char):
        """Construct a default tag for unmapped glyphs."""
        if not char:
            return ''
        cps = [ord(_c) for _c in char]
        # joining numeric references by semicolons
        # note that each entity should really start with & and end with ; e.g. &eacute;
        return ';'.join(f'#{_cp:X}' for _cp in cps)



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


###################################################################################################

# for use in function annotations
def tagger(initialiser):
    """Retrieve or create a tagmap from object or string."""
    if isinstance(initialiser, Tagger):
        return initialiser
    if initialiser is None or not str(initialiser):
        return None
    initialiser = str(initialiser)
    try:
        return tagmaps[initialiser]
    except KeyError:
        pass
    return MappingTagger.load(initialiser)


tagmaps = {
    'char': CharTagger(),
    'codepoint': CodepointTagger(),
    'name': UnicodeTagger(),
    'desc': UnicodeTagger(include_char=True),
    'adobe': AdobeTagger.load('charmaps/agl/aglfn.txt', name='adobe', separator=';', unicode_column=0, tag_column=1),
    'truetype': AdobeTagger.load('charmaps/agl/aglfn.txt', name='truetype', separator=';', unicode_column=0, tag_column=1),
    'sgml': SGMLTagger.load('charmaps/misc/SGML.TXT', name='sgml', separator='\t', unicode_column=2),
}

# truetype mapping is adobe mapping *but* with .null for NUL
# https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6post.html
tagmaps['truetype']._chr2tag['\0'] = '.null'
