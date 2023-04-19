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
........................"""

    def test_generated_space(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        text = monobit.render(f, 'I I').as_text()
        assert_text_eq(text, self.I_I)

    I_def_I = """\
........................
..@@@@.....@@.....@@@@..
...@@....@@@@......@@...
...@@......@@......@@...
...@@......@@......@@...
...@@......@@......@@...
..@@@@...@@@@@@...@@@@..
........................"""

    def test_defined_default(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        text = monobit.render(f, 'IAI').as_text()
        assert_text_eq(text, self.I_def_I)

    I_block_I = """\
........@@@@@@@@........
..@@@@..@@@@@@@@..@@@@..
...@@...@@@@@@@@...@@...
...@@...@@@@@@@@...@@...
...@@...@@@@@@@@...@@...
...@@...@@@@@@@@...@@...
..@@@@..@@@@@@@@..@@@@..
........@@@@@@@@........"""

    def test_generated_default(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        f = f.exclude('1')
        text = monobit.render(f, 'IAI').as_text()
        assert_text_eq(text, self.I_block_I)


    I_smallblock_I = """\
........@@@@........
..@@@@..@@@@..@@@@..
...@@...@@@@...@@...
...@@...@@@@...@@...
...@@...@@@@...@@...
...@@...@@@@...@@...
..@@@@..@@@@..@@@@..
........@@@@........"""

    def test_generated_default_wordspace(self):
        file = get_stringio(charcell)
        f,  *_ = monobit.load(file)
        f = f.exclude('1').modify(word_space=4)
        text = monobit.render(f, 'IAI').as_text()
        assert_text_eq(text, self.I_smallblock_I)


if __name__ == '__main__':
    unittest.main()
