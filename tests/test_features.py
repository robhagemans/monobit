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
    """Test directionality, proportional rendering and negative bearings."""

    # vertical metrics

    verttext=("""\
......................
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
""" * 2)

    def test_render_bdf_vertical(self):
        vert2, *_ = monobit.load(self.font_path / 'vertical.bdf')
        text2 = monobit.render(vert2, b'\x27\x27', direction='top-to-bottom').as_text()
        assert text2 == self.verttext, f'"""{text2}"""\n != \n"""{self.verttext}"""'

    def test_render_yaff_vertical(self):
        vert1, *_ = monobit.load(self.font_path / 'vertical.yaff')
        text1 = monobit.render(vert1, b'\x27\x27', direction='top-to-bottom').as_text()
        assert text1 == self.verttext, f'"""{text1}"""\n != \n"""{self.verttext}"""'

    def test_render_sfnt_vertical(self):
        vert1, *_ = monobit.load(self.font_path / 'vertical.otb')
        # we currently don't support storing non-unicode encoding in sfnt
        text1 = monobit.render(vert1, '\x27\x27', direction='top-to-bottom').as_text()
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
........
""")

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
........
""")

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
........
""")

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
........
""")


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
........
""")


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
........
""")


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
........
""")

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
........
""")


    # proportional rendering

    proptext="""\
.@@....................@@...@@.................
.@@....................@@......................
@@@@@..@@@@@...@@@@@..@@@@@.@@.@@.@@@...@@@.@@.
.@@...@@...@@.@@.......@@...@@.@@@..@@.@@..@@@.
.@@...@@@@@@@..@@@@@...@@...@@.@@...@@.@@...@@.
.@@...@@...........@@..@@...@@.@@...@@..@@@@@@.
..@@@..@@@@@@.@@@@@@....@@@.@@.@@...@@......@@.
........................................@@@@@..
"""

    def test_amiga_proportional(self):
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        text1 = monobit.render(prop1, b'testing').as_text()
        assert_text_eq(text1, self.proptext)

    def _render_proportional(self, format, *, load_kwargs=(), save_kwargs=()):
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        monobit.save(
            prop1, self.temp_path / f'wbfont_prop.{format}',
            format=format, **(save_kwargs or {}),
        )
        prop2, *_ = monobit.load(
            self.temp_path / f'wbfont_prop.{format}',
            format=format, **(load_kwargs or {}),
        )
        text2 = monobit.render(prop2, b'testing').as_text()
        assert_text_eq(text2, self.proptext)

    def test_yaff_proportional(self):
        self._render_proportional('yaff')

    def test_bdf_proportional(self):
        self._render_proportional('bdf')

    def test_bmfont_proportional(self):
        self._render_proportional('bmfont')

    def test_consoleet_proportional(self):
        self._render_proportional('consoleet')

    def test_dosstart_proportional(self):
        self._render_proportional('dosstart')

    def test_edwin_proportional(self):
        self._render_proportional('edwin')

    def test_figlet_proportional(self):
        self._render_proportional('figlet')

    def test_fzx_proportional(self):
        self._render_proportional('fzx')

    def test_gdos_proportional(self):
        self._render_proportional('gdos')

    def test_geos_proportional(self):
        self._render_proportional('geos')

    def test_gfxfont_proportional(self):
        self._render_proportional('gfxfont')

    def test_draw_proportional(self):
        self._render_proportional('hexdraw')

    def test_hppcl_proportional(self):
        self._render_proportional('hppcl')

    def test_hppcl_landscape_proportional(self):
        self._render_proportional(
            'hppcl', save_kwargs=dict(orientation='landscape')
        )

    def test_image_proportional(self):
        self._render_proportional(
            'image', load_kwargs=dict(table_size=(32, 7), first_codepoint=0x20)
        )

    def test_imageset_proportional(self):
        self._render_proportional('imageset')

    def test_iigs_proportional(self):
        self._render_proportional('iigs')

    def test_dfont_proportional(self):
        self._render_proportional('mac')

    def test_mkwinfont_proportional(self):
        self._render_proportional('mkwinfont')

    def test_win_proportional(self):
        self._render_proportional('mzfon')

    def test_winv1_proportional(self):
        # windows v1 .fnt stores proportional fonts differently from v2 and 3
        self._render_proportional('win', save_kwargs=dict(version=1))

    def test_nfnt_proportional(self):
        self._render_proportional('nfnt')

    def test_pcf_proportional(self):
        self._render_proportional('pcf')

    def test_pcgeos_proportional(self):
        self._render_proportional('pcgeos')

    def test_pilfont_proportional(self):
        self._render_proportional('pilfont')

    def test_sfont_proportional(self):
        self._render_proportional('sfont')

    def test_vfont_proportional(self):
        self._render_proportional('vfont')

    def test_otb_proportional(self):
        format = 'sfnt'
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        monobit.save(prop1, self.temp_path / f'wbfont_prop.{format}', format=format)
        prop2, *_ = monobit.load(self.temp_path / f'wbfont_prop.{format}', format=format)
        # need unicode here
        text2 = monobit.render(prop2, 'testing').as_text()
        assert_text_eq(text2, self.proptext)


    # kerning

    kerntext="""\
.......................
......@..@..@@@.@..@.@.
...........@...........
.@@@..@..@.@@@..@..@.@.
@@....@..@.@....@..@.@.
..@@..@..@.@....@..@.@.
@@@...@..@.@....@..@.@.
......@.........@....@.
....@@........@@...@@..
"""

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

    def test_render_otb_kerning(self):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        monobit.save(webby_mod1, self.temp_path / 'webby-small-kerned.otb')
        webby_mod2, *_ = monobit.load(self.temp_path / 'webby-small-kerned.otb')
        text2 = monobit.render(webby_mod2, 'sjifjij').as_text()
        assert_text_eq(text2, self.kerntext)

    def test_render_mac_kerning(self):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        monobit.save(webby_mod1, self.temp_path / 'webby-small-kerned.dfont', resource_type='NFNT')
        webby_mod2, *_ = monobit.load(self.temp_path / 'webby-small-kerned.dfont')
        text2 = monobit.render(webby_mod2, 'sjifjij').as_text()
        assert_text_eq(text2, self.kerntext)


    # kerning and negative bearings using overlapping test font

    testtext="""\
..@..
..@..
@@@@@
..@..
..@..
"""

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

    def test_render_otb_kerning_bearings(self):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(font, self.temp_path / 'positioning.otb')
        font, *_ = monobit.load(self.temp_path / 'positioning.otb')
        text = monobit.render(font, '01234').as_text()
        assert_text_eq(text, self.testtext)

    def test_render_mac_kerning_bearings(self):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(font, self.temp_path / 'positioning.dfont', resource_type='NFNT')
        font, *_ = monobit.load(self.temp_path / 'positioning.dfont')
        text = monobit.render(font, '01234').as_text()
        assert_text_eq(text, self.testtext)

    bearing_testtext="""\
..@..
..@..
..@..
..@..
..@..
"""

    def _render_bearings(self, format, char=False, **save_kwargs):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(font, self.temp_path / f'positioning.{format}', format=format, **save_kwargs)
        font, *_ = monobit.load(self.temp_path / f'positioning.{format}', format=format)
        if char:
            text = monobit.render(font, '012').as_text()
        else:
            text = monobit.render(font, b'012').as_text()
        assert_text_eq(text, self.bearing_testtext)

    # proportional formats that have writers but don't support negative bearings:
    # consoleet
    # dosstart
    # edwin
    # figlet
    # geos
    # hexdraw
    # image, imageset
    # windows, mkwinfont
    # sfont

    def test_yaff_negbearings(self):
        self._render_bearings('yaff')

    def test_bdf_negbearings(self):
        self._render_bearings('bdf')

    def test_bmfont_negbearings(self):
        self._render_bearings('bmfont')

    def test_fzx_negbearings(self):
        self._render_bearings('fzx')

    def test_gdos_negbearings(self):
        self._render_bearings('gdos')

    def test_gfxfont_negbearings(self):
        self._render_bearings('gfxfont')

    def test_hppcl_negbearings(self):
        self._render_bearings('hppcl')

    def test_hppcl_negbearings_landscape(self):
        self._render_bearings('hppcl', orientation='landscape')

    def test_iigs_negbearings(self):
        self._render_bearings('iigs')

    def test_nfnt_negbearings(self):
        self._render_bearings('nfnt')

    def test_pcgeos_negbearings(self):
        self._render_bearings('pcgeos')

    def test_pcf_negbearings(self):
        self._render_bearings('pcf')

    def test_pilfont_negbearings(self):
        self._render_bearings('pilfont')

    def test_sfnt_negbearings(self):
        self._render_bearings('sfnt', char=True)

    def test_vfont_negbearings(self):
        self._render_bearings('vfont')

    # vertical negative bearings

    testvert = """\
....@
...@.
..@..
.@...
@....
"""

    def _render_vert_bearings(self, format, **save_kwargs):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(font, self.temp_path / f'positioning.{format}', format=format, **save_kwargs)
        font, *_ = monobit.load(self.temp_path / f'positioning.{format}', format=format)
        text = monobit.render(font, '678', direction='ttb').as_text()
        assert_text_eq(text, self.testvert)

    def test_vert_neg_bearings_yaff(self):
        self._render_vert_bearings('yaff')

    def test_vert_neg_bearings_bdf(self):
        self._render_vert_bearings('bdf')

    def test_vert_neg_bearings_otb(self):
        self._render_vert_bearings('sfnt')



    # composition

    # tiny sample from unscii-8.hex at https://github.com/viznut/unscii
    # "Licensing: You can consider it Public Domain (or CC-0)" for unscii-8
    unscii8_sample = """
00020:0000000000000000
00075:0000666666663E00
00305:FF00000000000000
00327:0000000000000818
"""

    composed = """\
@@@@@@@@........@@@@@@@@@@@@@@@@........
........................................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
..@@@@@...@@@@@.....@...............@...
...@@..............@@..............@@...
"""

    def test_compose(self):
        file = get_stringio(self.unscii8_sample)
        f,  *_ = monobit.load(file, format='unifont')
        text = monobit.render(
            f, 'u\u0305\u0327u \u0305\u0327 \u0305 \u0327'
        ).as_text()
        assert_text_eq(text, self.composed)


if __name__ == '__main__':
    unittest.main()
