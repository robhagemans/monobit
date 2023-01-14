"""
monobit test suite
feature tests
"""

import os
import io
import unittest

import monobit
from .base import BaseTester, get_stringio


class TestFeatures(BaseTester):
    """Test specific features."""

    # vertical metrics

    verttext=("""......................
......................
......@......@........
.......@....@.........
................@.....
...@@@@@@@@@@@@@@@....
..........@...........
....@@@@@@@@@@@@......
..........@...........
..........@......@....
..@@@@@@@@@@@@@@@@@...
..........@...........
..........@.....@.....
..@@@@@@@@@@@@@@@@....
.........@.@..........
........@...@.........
.......@.....@........
.....@@.......@@......
...@@...........@@....
......................
......................
......................
""" * 2).strip()

    def test_render_bdf_vertical(self):
        vert2, *_ = monobit.load(self.font_path / 'vertical.bdf')
        text2 = monobit.render(vert2, b'\x27\x27', direction='top-to-bottom').as_text()
        assert text2 == self.verttext, f'"""{text2}"""\n != \n"""{self.verttext}"""'

    def test_render_yaff_vertical(self):
        vert1, *_ = monobit.load(self.font_path / 'vertical.yaff')
        text1 = monobit.render(vert1, b'\x27\x27', direction='top-to-bottom').as_text()
        assert text1 == self.verttext, f'"""{text1}"""\n != \n"""{self.verttext}"""'


    # proportional rendering

    proptext="""
.@@....................@@...@@.................
.@@....................@@......................
@@@@@..@@@@@...@@@@@..@@@@@.@@.@@.@@@...@@@.@@.
.@@...@@...@@.@@.......@@...@@.@@@..@@.@@..@@@.
.@@...@@@@@@@..@@@@@...@@...@@.@@...@@.@@...@@.
.@@...@@...........@@..@@...@@.@@...@@..@@@@@@.
..@@@..@@@@@@.@@@@@@....@@@.@@.@@...@@......@@.
........................................@@@@@..
""".strip()

    def test_render_amiga_proportional(self):
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        text1 = monobit.render(prop1, b'testing').as_text()
        assert text1 == self.proptext, f'"""{text1}"""\n != \n"""{self.proptext}"""'

    def test_render_yaff_proportional(self):
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        monobit.save(prop1, self.temp_path / 'wbfont_prop.yaff')
        prop2, *_ = monobit.load(self.temp_path / 'wbfont_prop.yaff')
        text2 = monobit.render(prop2, b'testing').as_text()
        assert text2 == self.proptext, f'"""{text2}"""\n != \n"""{self.proptext}"""'


    # kerning

    kerntext="""
.........................
......@..@..@@@.@..@.@...
...........@.............
.@@@..@..@.@@@..@..@.@...
@@....@..@.@....@..@.@...
..@@..@..@.@....@..@.@...
@@@...@..@.@....@..@.@...
......@.........@....@...
....@@........@@...@@....
""".strip()

    def test_render_yaff_kerning(self):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        text1 = monobit.render(webby_mod1, b'sjifjij').as_text()
        assert text1 == self.kerntext, f'"""{text1}"""\n != \n"""{self.kerntext}"""'

    def test_render_bmf_kerning(self):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        monobit.save(webby_mod1, self.temp_path / 'webby-small-kerned.bmf', where=self.temp_path)
        webby_mod2, *_ = monobit.load(self.temp_path / 'webby-small-kerned.bmf')
        text2 = monobit.render(webby_mod2, b'sjifjij').as_text()
        assert text2 == self.kerntext, f'"""{text2}"""\n != \n"""{self.kerntext}"""'


    # tiny sample from unscii-8.hex at https://github.com/viznut/unscii
    # "Licensing: You can consider it Public Domain (or CC-0)" for unscii-8
    unscii8_sample = """
00020:0000000000000000
00075:0000666666663E00
00305:FF00000000000000
00327:0000000000000818
"""

    composed = """
@@@@@@@@........@@@@@@@@@@@@@@@@........
........................................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
..@@@@@...@@@@@.....@...............@...
...@@..............@@..............@@...
""".strip()

    def test_compose(self):
        file = get_stringio(self.unscii8_sample)
        f,  *_ = monobit.load(file, format='hex')
        text = monobit.render(
            f, 'u\u0305\u0327u \u0305\u0327 \u0305 \u0327'
        ).as_text()
        assert text == self.composed, f'"""{text}"""\n != \n"""{self.composed}"""'


if __name__ == '__main__':
    unittest.main()
