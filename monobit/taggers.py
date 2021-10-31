"""
monobit.taggers - glyph tagging

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata
import pkgutil
from pathlib import Path

from .encoding import unicode_name, is_printable, NotFoundError
from .font import Font


def extend_string(string, line):
    """Add a line to a multiline string."""
    if not string:
        return line
    if not line:
        return string
    return '\n'.join((string, line))


class Tagger:
    """Add tags or comments to a font's glyphs."""

    def set_comments(self, font):
        """Use tagger to add glyph comments."""
        glyphs = tuple(
            _glyph.modify(comments=extend_string(_glyph.comments, self.get_tag(_glyph)))
            for _glyph in font.glyphs
        )
        return Font(glyphs, font.get_comments(), font.nondefault_properties)

    def set_tags(self, font):
        """Use tagger to add glyph tags."""
        glyphs = tuple(
            _glyph.modify(tags=_glyph.tags + (self.get_tag(_glyph),))
            for _glyph in font.glyphs
        )
        return Font(glyphs, font.get_comments(), font.nondefault_properties)

    def get_tag(self, glyph):
        raise NotImplementedError


class UnicodeTagger(Tagger):
    """Tag with unicode names and characters."""

    def __init__(self, include_char=False):
        self.include_char = include_char

    def get_tag(self, glyph):
        """Add unicode glyph names as comments, if no comment already exists."""
        name = unicode_name(glyph.char)
        if self.include_char and is_printable(glyph.char):
            return '[{}] {}'.format(glyph.char, name)
        else:
            return '{}'.format(name)


class MappingTagger(Tagger):
    """Tag on the basis of a mapping table."""

    def __init__(self, mapping, name=''):
        """Set up mapping."""
        self._chr2tag = mapping

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

    def get_tag(self, glyph):
        """Add unicode glyph names as comments, if no comment already exists."""
        return self._chr2tag.get(glyph.char, '')


###################################################################################################
# tag map format readers

def _read_tagmap(data, separator=';', comment='#', joiner=' ', tag_column=0, unicode_column=1):
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


tagmaps = {
    'unicode': UnicodeTagger(),
    'adobe': MappingTagger.load('charmaps/agl/aglfn.txt', separator=';', unicode_column=0, tag_column=1),
    'sgml': MappingTagger.load('charmaps/misc/SGML.TXT', separator='\t', unicode_column=2),
}
