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


if __name__ == '__main__':
    unittest.main()
