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
palette:
    000000 .
    FF0000 1
    00FF00 2
    0000FF @

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
        rendered_text = monobit.render_text(font2, text).as_shades(border=(0,0,0))
        assert_text_eq(ascii(rendered_text), self.sampletext)

    def test_yaff_colour(self):
        self._render_colour('yaff')

    def test_amiga_colour(self):
        self._render_colour('amiga')

    def test_mac_colour(self):
        self._render_colour('mac')

    def test_sfnt_cbdt_bit_colour(self):
        self._render_colour('sfnt', char=True, save_kwargs=dict(bitmap_table='CBDT', strike_format='bit'))

    def test_sfnt_cbdt_byte_colour(self):
        self._render_colour('sfnt', char=True, save_kwargs=dict(bitmap_table='CBDT', strike_format='byte'))

    def test_sfnt_cbdt_png_colour(self):
        self._render_colour('sfnt', char=True, save_kwargs=dict(bitmap_table='CBDT', strike_format='png'))

    def test_sfnt_sbix_png_colour(self):
        self._render_colour('sfnt', char=True, save_kwargs=dict(bitmap_table='sbix', strike_format='png'))

    def test_sfnt_sbix_tiff_colour(self):
        self._render_colour('sfnt', char=True, save_kwargs=dict(bitmap_table='sbix', strike_format='tiff'))

    def test_bmfont_colour(self):
        self._render_colour('bmfont', save_kwargs={'packed': False})

    def test_bmf_colour(self):
        self._render_colour('bmf')

    def test_sfont_colour(self):
        self._render_colour('sfont')

    def test_image_colour_rgb(self):
        self._render_colour(
            'image',
            save_kwargs={'image_mode': 'rgb'},
            load_kwargs={'first_codepoint': ord('t')}
        )

    def test_image_colour_rgba(self):
        self._render_colour(
            'image',
            save_kwargs={'image_mode': 'rgba'},
            load_kwargs={'first_codepoint': ord('t')}
        )

    def test_imageset_colour_rgb(self):
        self._render_colour('imageset', save_kwargs={'image_mode': 'rgb'})

    def test_imageset_colour_rgba(self):
        self._render_colour('imageset', save_kwargs={'image_mode': 'rgba'})



rgbafont = """
name: RGBATest
levels: 4
palette:
    00000000 .
    FF000055 1
    00FF00AA 2
    0000FFFF @

't':
116:
    .12@
"""


class TestRGBA(BaseTester):
    """Test rgba features."""

    rendered = (
        (0, 0, 0, 0), (255, 0, 0, 85), (0, 255, 0, 170), (0, 0, 255, 255)
    )

    def _render_rgba(self, format, *, char=False, load_kwargs=(), save_kwargs=()):
        font1, *_ = monobit.load(get_stringio(rgbafont))
        monobit.save(
            font1, self.temp_path / f'rgba.{format}',
            format=format, **(save_kwargs or {}),
        )
        font2, *_ = monobit.load(
            self.temp_path / f'rgba.{format}',
            format=format, **(load_kwargs or {}),
        )
        if char:
            text = 't'
        else:
            text = b't'
        rendered = monobit.render_text(font2, text).as_image(image_mode='rgba', border=(0,0,0,0))
        assert tuple(rendered.getdata()) == self.rendered

    def test_yaff_rgba(self):
        self._render_rgba('yaff')

    def test_image_rgba(self):
        self._render_rgba(
            'image',
            save_kwargs={'image_mode': 'rgba'},
            load_kwargs={'first_codepoint': ord('t'), 'background': 'alpha'}
        )

    def test_imageset_rgba(self):
        self._render_rgba(
            'imageset',
            save_kwargs={'image_mode': 'rgba'},
            load_kwargs={'background': 'alpha'}
        )

    def test_sfnt_cbdt_bit_rgba(self):
        self._render_rgba('sfnt', char=True, save_kwargs=dict(bitmap_table='CBDT', strike_format='bit'))

    def test_sfnt_cbdt_byte_rgba(self):
        self._render_rgba('sfnt', char=True, save_kwargs=dict(bitmap_table='CBDT', strike_format='byte'))

    def test_sfnt_cbdt_png_rgba(self):
        self._render_rgba('sfnt', char=True, save_kwargs=dict(bitmap_table='CBDT', strike_format='png'))

    def test_sfnt_sbix_png_rgba(self):
        self._render_rgba('sfnt', char=True, save_kwargs=dict(bitmap_table='sbix', strike_format='png'))

    def test_sfnt_sbix_tiff_rgba(self):
        self._render_rgba('sfnt', char=True, save_kwargs=dict(bitmap_table='sbix', strike_format='tiff'))

    def test_bmfont_rgba(self):
        self._render_rgba('bmfont', save_kwargs={'packed': False})


if __name__ == '__main__':
    unittest.main()
