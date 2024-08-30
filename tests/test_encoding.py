"""
monobit test suite
tests for encoding-related features
"""

import os
import io
import unittest

import monobit
from .base import BaseTester, get_stringio, assert_text_eq


charcell = """
default-char: '1'
word-break: ' '
ascent: 7
descent: 1
shift-up: -1

'1':
    ........
    ...@@...
    .@@@@...
    ...@@...
    ...@@...
    ...@@...
    .@@@@@@.
    ........

'I':
    ........
    ..@@@@..
    ...@@...
    ...@@...
    ...@@...
    ...@@...
    ..@@@@..
    ........
"""


proportional = """
default-char: '1'
word-break: ' '
ascent: 7
descent: 1
shift-up: -1

'1':
    ........
    ...@@...
    .@@@@...
    ...@@...
    ...@@...
    ...@@...
    .@@@@@@.
    ........

'I':
    ......
    .@@@@.
    ..@@..
    ..@@..
    ..@@..
    ..@@..
    .@@@@.
    ......

# we need to define a third glyph with different width as we later remove '1'
# and a one-glyph font is always character-cell
'.':
    ....
    ....
    ....
    ....
    ....
    .@@.
    .@@.
    ....

"""


class TestEncoding(BaseTester):
    """Test encoding features."""

    I_I = """\
........................
..@@@@............@@@@..
...@@..............@@...
...@@..............@@...
...@@..............@@...
...@@..............@@...
..@@@@............@@@@..
........................
"""

    def test_generated_space_charcell(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        text = monobit.render(f, 'I I').as_text(inklevels='.@')
        assert_text_eq(text, self.I_I)


    I_I_prop = """\
...............
.@@@@.....@@@@.
..@@.......@@..
..@@.......@@..
..@@.......@@..
..@@.......@@..
.@@@@.....@@@@.
...............
"""

    def test_generated_space(self):
        file = get_stringio(proportional)
        f,  *_ = monobit.load(file)
        text = monobit.render(f, 'I I').as_text(inklevels='.@')
        assert_text_eq(text, self.I_I_prop)


    I_def_I = """\
........................
..@@@@.....@@.....@@@@..
...@@....@@@@......@@...
...@@......@@......@@...
...@@......@@......@@...
...@@......@@......@@...
..@@@@...@@@@@@...@@@@..
........................
"""

    def test_defined_default(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        text = monobit.render(f, 'IAI').as_text(inklevels='.@')
        assert_text_eq(text, self.I_def_I)

    I_block_I = """\
........@@@@@@@@........
..@@@@..@@@@@@@@..@@@@..
...@@...@@@@@@@@...@@...
...@@...@@@@@@@@...@@...
...@@...@@@@@@@@...@@...
...@@...@@@@@@@@...@@...
..@@@@..@@@@@@@@..@@@@..
........@@@@@@@@........
"""

    def test_generated_default(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        f = f.exclude('1')
        text = monobit.render(f, 'IAI').as_text(inklevels='.@')
        assert_text_eq(text, self.I_block_I)


    def test_generated_default_wordspace_charcell(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        f = f.exclude('1').modify(word_space=4)
        text = monobit.render(f, 'IAI').as_text(inklevels='.@')
        assert_text_eq(text, self.I_block_I)


    I_smallblock_I = """\
......@@@@......
.@@@@.@@@@.@@@@.
..@@..@@@@..@@..
..@@..@@@@..@@..
..@@..@@@@..@@..
..@@..@@@@..@@..
.@@@@.@@@@.@@@@.
......@@@@......
"""

    def test_generated_default_wordspace(self):
        file = get_stringio(proportional)
        f,  *_ = monobit.load(file)
        f = f.exclude('1').modify(word_space=4)
        text = monobit.render(f, 'IAI').as_text(inklevels='.@')
        assert_text_eq(text, self.I_smallblock_I)


    # encoders

    def test_indexer(self):
        """Test labelling codepoints from ordinal with a range indexer."""
        font, *_ = monobit.load(
            self.font_path / '4x6.raw',
            format='raw', cell='4x6', count=0x61
        )
        font = font.label(codepoint_from='0,0x20-', overwrite=True)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_indexer_tbl(self):
        """Test .tbl file indexer."""
        font, *_ = monobit.load(
            self.font_path / '4x6.raw',
            format='raw', cell='4x6', count=0x61
        )
        font = font.label(codepoint_from=str(self.font_path / '4x6-0x7f.tbl'), overwrite=True)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_charmap_labeller(self):
        """Test labelling codepoints from chars with a builtin charmap."""
        font = self.fixed4x6.label(codepoint_from=None, overwrite=True)
        assert not any(_g.codepoint for _g in font.glyphs)
        font = font.label(codepoint_from='cp437')
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_unicode_tag_labeller(self):
        """Test labelling tags from chars with unicode tagmap."""
        font = self.fixed4x6.label(tag_from='name', overwrite=True)
        assert_text_eq(font.get_glyph('"LATIN CAPITAL LETTER A"').reduce().as_text(), self.fixed4x6_A)

    def test_tagmap_labeller(self):
        """Test labelling chars from tags with a builtin tagmap."""
        font = self.fixed4x6.label(char_from=None, overwrite=True)
        font = font.label(char_from='adobe')
        assert_text_eq(font.get_glyph('"A"').reduce().as_text(), self.fixed4x6_A)

    def test_labelling_comments(self):
        """Test labelling comments from chars with unicode description tagmap."""
        font = self.fixed4x6.label(comment_from='desc')
        assert_text_eq(font.get_glyph('A').comment, '[A] LATIN CAPITAL LETTER A')



if __name__ == '__main__':
    unittest.main()
