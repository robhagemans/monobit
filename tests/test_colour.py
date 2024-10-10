"""
monobit test suite
colour feature tests
"""

import os
import io
import unittest

import monobit
from .base import BaseTester, get_stringio, assert_text_eq


colourfont = """
name: ColourTest
levels: 4
amiga.ctf-ColorTable:
    0 0 0
    255 0 0
    0 255 0
    0 0 255

't':
116:
    .12@
"""


class TestColour(BaseTester):
    """Test colour features."""

    sampletext = '"""\\\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;0;0m\\u2588\x1b[0m\x1b[38;2;0;255;0m\\u2588\x1b[0m\x1b[38;2;0;0;255m\\u2588\x1b[0m\n"""'

    def _render_colour(self, format, *, char=False, load_kwargs=(), save_kwargs=()):
        font1, *_ = monobit.load(get_stringio(colourfont))
        monobit.save(
            font1, self.temp_path / f'colours.{format}',
            format=format, **(save_kwargs or {}),
        )
        font2, *_ = monobit.load(
            self.temp_path / f'colours.{format}',
            format=format, **(load_kwargs or {}),
        )
        if char:
            text = 't'
        else:
            text = b't'
        rendered_text = monobit.render(font2, text).as_shades(border=(0,0,0))
        assert_text_eq(ascii(rendered_text), self.sampletext)

    def test_yaff_colour(self):
        self._render_colour('yaff')

    def test_amiga_colour(self):
        self._render_colour('amiga')

    # def test_nfnt_colour(self):
    #     self._render_colour('nfnt')
    #
    # def test_sfnt_colour(self):
    #     self._render_colour('sfnt', char=True)

    def test_bmfont_colour(self):
        self._render_colour('bmfont', save_kwargs={'packed': False})

    def test_sfont_colour(self):
        self._render_colour('sfont')

    def test_image_colour(self):
        self._render_colour('image', load_kwargs={'first_codepoint': ord('t')})


if __name__ == '__main__':
    unittest.main()
