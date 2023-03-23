"""
monobit test suite
feature tests
"""

import os
import io
import unittest

import monobit
from .base import BaseTester, get_stringio, assert_text_eq



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

    # all directions

    def test_render_ltr_ttb(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='l t f').as_text()
        assert_text_eq(text, """\
.@......
@@@.....
.@......
.@......
..@.....
........
.@...@..
@@..@.@.
.@....@.
.@...@..
@@@.@@@.
........""")

    def test_render_ltr_btt(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='l b f').as_text()
        assert_text_eq(text, """\
.@...@..
@@..@.@.
.@....@.
.@...@..
@@@.@@@.
........
.@......
@@@.....
.@......
.@......
..@.....
........""")

    def test_render_rtl_ttb(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='r t f').as_text()
        assert_text_eq(text, """\
.....@..
....@@@.
.....@..
.....@..
......@.
........
.@...@..
@.@.@@..
..@..@..
.@...@..
@@@.@@@.
........""")

    def test_render_rtl_btt(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='r b f').as_text()
        assert_text_eq(text, """\
.@...@..
@.@.@@..
..@..@..
.@...@..
@@@.@@@.
........
.....@..
....@@@.
.....@..
.....@..
......@.
........""")


    def test_render_ttb_rtl(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='t r f').as_text()
        assert_text_eq(text, """\
.@...@..
@@..@@@.
.@...@..
.@...@..
@@@...@.
........
.@......
@.@.....
..@.....
.@......
@@@.....
........""")


    def test_render_ttb_ltr(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='t l f').as_text()
        assert_text_eq(text, """\
.@...@..
@@@.@@..
.@...@..
.@...@..
..@.@@@.
........
.....@..
....@.@.
......@.
.....@..
....@@@.
........""")


    def test_render_btt_rtl(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='b r f').as_text()
        assert_text_eq(text, """\
.@......
@.@.....
..@.....
.@......
@@@.....
........
.@...@..
@@..@@@.
.@...@..
.@...@..
@@@...@.
........""")

    def test_render_btt_ltr(self):
        text = monobit.render(self.fixed4x6, 't\n12', direction='b l f').as_text()
        assert_text_eq(text, """\
.....@..
....@.@.
......@.
.....@..
....@@@.
........
.@...@..
@@@.@@..
.@...@..
.@...@..
..@.@@@.
........""")


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
        assert_text_eq(text1, self.proptext)

    def _render_proportional(self, format, **save_kwargs):
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        monobit.save(prop1, self.temp_path / f'wbfont_prop.{format}', format=format, **save_kwargs)
        prop2, *_ = monobit.load(self.temp_path / f'wbfont_prop.{format}', format=format)
        text2 = monobit.render(prop2, b'testing').as_text()
        assert_text_eq(text2, self.proptext)

    def test_yaff_proportional(self):
        self._render_proportional('yaff')

    def test_draw_proportional(self):
        self._render_proportional('hexdraw')

    def test_win_proportional(self):
        self._render_proportional('mzfon')

    def test_fzx_proportional(self):
        self._render_proportional('fzx')

    def test_bdf_proportional(self):
        self._render_proportional('bdf')

    def test_gdos_proportional(self):
        self._render_proportional('gdos')

    def test_figlet_proportional(self):
        self._render_proportional('figlet')

    def test_vfont_proportional(self):
        self._render_proportional('vfont')

    def test_iigs_proportional(self):
        self._render_proportional('iigs')

    def test_nfnt_proportional(self):
        self._render_proportional('nfnt')

    def test_hppcl_proportional(self):
        self._render_proportional('hppcl')

    def test_hppcl_landscape_proportional(self):
        self._render_proportional('hppcl', orientation='landscape')

    # kerning

    kerntext="""
.......................
......@..@..@@@.@..@.@.
...........@...........
.@@@..@..@.@@@..@..@.@.
@@....@..@.@....@..@.@.
..@@..@..@.@....@..@.@.
@@@...@..@.@....@..@.@.
......@.........@....@.
....@@........@@...@@..
""".strip()

    def test_render_yaff_kerning(self):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        text1 = monobit.render(webby_mod1, b'sjifjij').as_text()
        assert_text_eq(text1, self.kerntext)

    def test_render_bmf_kerning(self):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        monobit.save(
            webby_mod1, self.temp_path / 'webby-small-kerned.bmf',
            format='bmfont',
        )
        webby_mod2, *_ = monobit.load(self.temp_path / 'webby-small-kerned.bmf')
        text2 = monobit.render(webby_mod2, b'sjifjij').as_text()
        assert_text_eq(text2, self.kerntext)


    # kerning and negative bearings using overlapping test font

    testtext="""
..@..
..@..
@@@@@
..@..
..@..
""".strip()

    def test_render_yaff_kerning_bearings(self):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        text = monobit.render(font, b'01234').as_text()
        assert_text_eq(text, self.testtext)

    def _render_bmf_kerning_bearings(self, descriptor):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(
            font, self.temp_path / 'positioning.fnt',
            format='bmfont', descriptor=descriptor,
        )
        font, *_ = monobit.load(self.temp_path / 'positioning.fnt', format='bmfont')
        text = monobit.render(font, b'01234').as_text()
        assert_text_eq(text, self.testtext)

    def test_render_bmf_kerning_bearings_binary(self):
        self._render_bmf_kerning_bearings('binary')

    def test_render_bmf_kerning_bearings_text(self):
        self._render_bmf_kerning_bearings('text')

    def test_render_bmf_kerning_bearings_xml(self):
        self._render_bmf_kerning_bearings('xml')

    def test_render_bmf_kerning_bearings_json(self):
        self._render_bmf_kerning_bearings('json')


    bearing_testtext="""
..@..
..@..
..@..
..@..
..@..
""".strip()

    def _render_bearings(self, format, **save_kwargs):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(font, self.temp_path / f'positioning.{format}', format=format, **save_kwargs)
        font, *_ = monobit.load(self.temp_path / f'positioning.{format}', format=format)
        text = monobit.render(font, b'012').as_text()
        assert_text_eq(text, self.bearing_testtext)

    # def test_win_negbearings(self):
    #     self._render_bearings('mzfon')

    def test_fzx_negbearings(self):
        self._render_bearings('fzx')

    def test_bdf_negbearings(self):
        self._render_bearings('bdf')

    def test_gdos_negbearings(self):
        self._render_bearings('gdos')

    def test_iigs_negbearings(self):
        self._render_bearings('iigs')

    def test_nfnt_negbearings(self):
        self._render_bearings('nfnt')

    # def test_figlet_negbearings(self):
    #     self._render_bearings('figlet')

    def test_vfont_negbearings(self):
        self._render_bearings('vfont')

    def test_hppcl_negbearings(self):
        self._render_bearings('hppcl')

    def test_hppcl_negbearings_landscape(self):
        self._render_bearings('hppcl', orientation='landscape')

    # composition

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
        f,  *_ = monobit.load(file, format='unifont')
        text = monobit.render(
            f, 'u\u0305\u0327u \u0305\u0327 \u0305 \u0327'
        ).as_text()
        assert_text_eq(text, self.composed)


if __name__ == '__main__':
    unittest.main()
