"""
monobit test suite
greyscale feature tests
"""

import os
import io
import unittest

import monobit
from .base import BaseTester, get_stringio, assert_text_eq



class TestGreyscale(BaseTester):
    """Test greyscale features."""

    sampletext = """\
.4.............4..............
.7.............7..7...........
.7.............7..............
777.1771.1777.777.7.7771.1777.
.7..7..7.71....7..7.7.17.71.7.
.7..7777.1771..7..7.7..7.71.7.
.71.7......17..71.7.7..7.1777.
.17.177..7771..17.7.7..7....7.
..........................771.
"""

    def _render_greyscale(self, format, *, char=False, load_kwargs=(), save_kwargs=()):
        font1, *_ = monobit.load(self.font_path / 'konatu-ascii.yaff')
        monobit.save(
            font1, self.temp_path / f'konatu-ascii.{format}',
            format=format, **(save_kwargs or {}),
        )
        font2, *_ = monobit.load(
            self.temp_path / f'konatu-ascii.{format}',
            format=format, **(load_kwargs or {}),
        )
        if char:
            text = 'testing'
        else:
            text = b'testing'
        rendered_text = monobit.render(font2, text).as_text(inklevels='.123456789abcde@', border='.')
        assert_text_eq(rendered_text, self.sampletext)

    def test_yaff_greyscale(self):
        self._render_greyscale('yaff')

    def test_bdf_greyscale(self):
        self._render_greyscale('bdf')

    def test_beos_greyscale(self):
        self._render_greyscale('beos')

    def test_nfnt_greyscale(self):
        self._render_greyscale('nfnt')

    def test_sfnt_greyscale(self):
        self._render_greyscale('sfnt', char=True)

    # def test_bmfont_greyscale(self):
    #     self._render_greyscale('bmfont')

    # def test_sfont_greyscale(self):
    #     self._render_greyscale('sfont')

    # def test_image_greyscale(self):
    #     self._render_greyscale('image')


if __name__ == '__main__':
    unittest.main()
