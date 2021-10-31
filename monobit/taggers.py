"""
monobit.taggers - glyph tagging

(c) 2020--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import unicodedata
from .encoding import unicode_name, is_printable
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
