"""
monobit test suite
hex format tests
"""

import os
import io
import unittest

import monobit
from monobit import Glyph
from .base import BaseTester, get_stringio


class TestHex(BaseTester):
    """Test the (extended) hex format."""

    # glyph definitions

    # tiny sample from unscii-8.hex at https://github.com/viznut/unscii
    # "Licensing: You can consider it Public Domain (or CC-0)" for unscii-8
    unscii8_u = """
00020:0000000000000000
00075:0000666666663E00
"""
    # note first line is empty

    def test_glyphs(self):
        file = get_stringio(self.unscii8_u)
        f,  *_ = monobit.load(file, format='hex')
        assert len(f.glyphs) == 2, repr(f.glyphs)
        assert f.raster_size == (8, 8), f.raster_size
        space = Glyph((
            '........',
            '........',
            '........',
            '........',
            '........',
            '........',
            '........',
            '........',
        ), labels=(' ',), _0='.', _1='@')
        assert f.get_glyph(' ') == space, f.get_glyph(' ')
        u = Glyph((
            '........',
            '........',
            '.@@..@@.',
            '.@@..@@.',
            '.@@..@@.',
            '.@@..@@.',
            '..@@@@@.',
            '........',
        ), labels=('u',), _0='.', _1='@')
        assert f.get_glyph('u') == u, f.get_glyph('u')


if __name__ == '__main__':
    unittest.main()
