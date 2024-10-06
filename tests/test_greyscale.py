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

    sampletext = '"""\\\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;68;68;68m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;17;17;17m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;17;17;17m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;17;17;17m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;17;17;17m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;17;17;17m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;119;119;119m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n"""'


# """\
# .4.......
# .7.......
# .7.......
# 777.1771.
# .7..7..7.
# .7..7777.
# .71.7....
# .17.177..
# .........
# """

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
            text = 'te'
        else:
            text = b'te'
        rendered_text = monobit.render(font2, text).as_shades(border=(0,0,0))
        assert_text_eq(ascii(rendered_text), self.sampletext)

    def test_yaff_greyscale(self):
        self._render_greyscale('yaff')

    def test_amiga_greyscale(self):
        self._render_greyscale('amiga')

    def test_bdf_greyscale(self):
        self._render_greyscale('bdf')

    def test_beos_greyscale(self):
        self._render_greyscale('beos')

    def test_nfnt_greyscale(self):
        self._render_greyscale('nfnt')

    def test_sfnt_greyscale(self):
        self._render_greyscale('sfnt', char=True)

    def test_bmfont_greyscale(self):
        self._render_greyscale('bmfont')

    def test_sfont_greyscale(self):
        self._render_greyscale('sfont')

    def test_image_greyscale(self):
        self._render_greyscale(
            'image',
            load_kwargs=dict(table_size=(32, 3), first_codepoint=0x20)
        )


if __name__ == '__main__':
    unittest.main()
