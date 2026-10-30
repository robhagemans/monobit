"""
monobit test suite
greyscale feature tests
"""
import unittest

import monobit

from .base import BaseTester, get_stringio, assert_text_eq


class TestGreyscale(BaseTester):
    """Test greyscale features."""

    sampletext = '"""\\\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;153;153;153m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;34;34;34m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;34;34;34m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;34;34;34m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;34;34;34m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;34;34;34m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n"""'

    # BMF colour palette is affected by rounding 8bit -> 6bit -> 8bit
    bmf_sampletext = '"""\\\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;153;153;153m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;32;32;32m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;32;32;32m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;32;32;32m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;32;32;32m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;32;32;32m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;255;255;255m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\x1b[38;2;0;0;0m\\u2588\x1b[0m\n"""'

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

    def _render_greyscale(self, format, *, char=False, load_kwargs=(), save_kwargs=(), model=sampletext):
        font1, *_ = monobit.load(self.font_path / 'konatu-ascii.yaff')
        path = self.temp_path / f'konatu-ascii.{format}'
        monobit.save(font1, path, format=format, **(save_kwargs or {}))
        font2, *_ = monobit.load(path, format=format, **(load_kwargs or {}))
        if char:
            text = 'te'
        else:
            text = b'te'
        rendered_text = monobit.render_text(font2, text).as_shades(border=(0,0,0))
        assert_text_eq(ascii(rendered_text), model)

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

    def test_bmfont_greyscale_packed(self):
        self._render_greyscale('bmfont', save_kwargs=dict(packed=True))

    def test_bmf_greyscale(self):
        self._render_greyscale('bmf', model=self.bmf_sampletext)

    def test_bmf_greyscale_alpha(self):
        self._render_greyscale('bmf', save_kwargs=dict(alpha_greyscale=True))

    def test_sfont_greyscale(self):
        self._render_greyscale('sfont')

    def test_image_greyscale_grey(self):
        self._render_greyscale(
            'image',
            save_kwargs=dict(image_mode='grey'),
            load_kwargs=dict(table_size=(32, 3), first_codepoint=0x20)
        )

    def test_image_greyscale_rgb(self):
        self._render_greyscale(
            'image',
            save_kwargs=dict(image_mode='rgb'),
            load_kwargs=dict(table_size=(32, 3), first_codepoint=0x20)
        )

    def test_image_greyscale_rgba(self):
        self._render_greyscale(
            'image',
            save_kwargs=dict(image_mode='rgba'),
            load_kwargs=dict(table_size=(32, 3), first_codepoint=0x20)
        )

    def test_imageset_greyscale_grey(self):
        self._render_greyscale(
            'imageset',
            save_kwargs=dict(image_mode='grey'),
        )

    def test_imageset_greyscale_rgb(self):
        self._render_greyscale(
            'imageset',
            save_kwargs=dict(image_mode='rgb'),
        )

    def test_imageset_greyscale_rgba(self):
        self._render_greyscale(
            'imageset',
            save_kwargs=dict(image_mode='rgba'),
        )



greyfont4 = """
name: DefaultGreyscaleTest
levels: 4

't':
116:
    .12@
    ...1
"""


class TestDefaultGrey4(BaseTester):
    """Test default 4-level greyscale."""

    rendered = (
        (0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255),
        (0, 0, 0), (0, 0, 0), (0, 0, 0), (85, 85, 85),
    )

    def _render_grey4(self, format, *, char=False, load_kwargs=(), save_kwargs=()):
        font1, *_ = monobit.load(get_stringio(greyfont4))
        monobit.save(
            font1, self.temp_path / f'grey4.{format}',
            format=format, **(save_kwargs or {}),
        )
        font2, *_ = monobit.load(
            self.temp_path / f'grey4.{format}',
            format=format, **(load_kwargs or {}),
        )
        if char:
            text = 't'
        else:
            text = b't'
        rendered = monobit.render_text(font2, text).as_image(image_mode='rgb', border=(0,0,0))
        assert tuple(rendered.getdata()) == self.rendered

    def test_yaff_grey4(self):
        self._render_grey4('yaff')

    def test_amiga_grey4(self):
        self._render_grey4('amiga')

    def test_bdf_grey4(self):
        self._render_grey4('bdf')

    def test_nfnt_grey4(self):
        self._render_grey4('nfnt')

    def test_sfnt_grey4(self):
        self._render_grey4('sfnt', char=True)


greyfont16 = """
name: DefaultGreyscaleTest
levels: 16

't':
116:
    .123
    4567
    89AB
    CDE@
"""


class TestDefaultGrey16(BaseTester):
    """Test default 16-level greyscale."""

    rendered = (
        (0, 0, 0), (17, 17, 17), (34, 34, 34), (51, 51, 51),
        (68, 68, 68), (85, 85, 85), (102, 102, 102), (119, 119, 119),
        (136, 136, 136), (153, 153, 153), (170, 170, 170), (187, 187, 187),
        (204, 204, 204), (221, 221, 221), (238, 238, 238), (255, 255, 255)
    )

    def _render_grey16(self, format, *, char=False, load_kwargs=(), save_kwargs=()):
        font1, *_ = monobit.load(get_stringio(greyfont16))
        monobit.save(
            font1, self.temp_path / f'grey16.{format}',
            format=format, **(save_kwargs or {}),
        )
        font2, *_ = monobit.load(
            self.temp_path / f'grey16.{format}',
            format=format, **(load_kwargs or {}),
        )
        if char:
            text = 't'
        else:
            text = b't'
        rendered = monobit.render_text(font2, text).as_image(image_mode='rgb', border=(0,0,0))
        assert tuple(rendered.getdata()) == self.rendered

    def test_yaff_grey16(self):
        self._render_grey16('yaff')

    def test_amiga_grey16(self):
        self._render_grey16('amiga')

    def test_bdf_grey16(self):
        self._render_grey16('bdf')

    def test_nfnt_grey16(self):
        self._render_grey16('nfnt')

    def test_sfnt_grey16(self):
        self._render_grey16('sfnt', char=True)


if __name__ == '__main__':
    unittest.main()
