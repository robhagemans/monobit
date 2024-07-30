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
        f,  *_ = monobit.load(file, format='unifont')
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
        ), labels=(' ',), inklevels='.@')
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
        ), labels=('u',), inklevels='.@')
        assert f.get_glyph('u') == u, f.get_glyph('u')


    draw_glyph = """
0000:\t##--##
\t##--##
\t------
\t------
\t##--##
\t##--##
\t------
\t------
\t##--##
\t##--##
"""

    def test_draw_glyph(self):
        """Test HexDraw glyph."""
        file = get_stringio(self.draw_glyph)
        f,  *_ = monobit.load(file, format='hexdraw')
        assert len(f.glyphs) == 1, repr(f.glyphs)
        assert f.raster_size == (6, 10), f.raster_size


    draw_glyph_spaced = """
0000:
    ##--##
    ##--##
    ------
    ------
    ##--##
    ##--##
    ------
    ------
    ##--##
    ##--##
"""

    def test_draw_glyph_spaced(self):
        """Test HexDraw glyph with extra newline and spaces instead of tabs."""
        file = get_stringio(self.draw_glyph_spaced)
        f,  *_ = monobit.load(file, format='hexdraw')
        assert len(f.glyphs) == 1, repr(f.glyphs)
        assert f.raster_size == (6, 10), f.raster_size


if __name__ == '__main__':
    unittest.main()
