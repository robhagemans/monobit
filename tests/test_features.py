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
        text2 = monobit.render(vert2, b'\x27\x27', direction='top-to-bottom').as_text(inklevels='.@')
        assert text2 == self.verttext, f'"""{text2}"""\n != \n"""{self.verttext}"""'

    def test_render_yaff_vertical(self):
        vert1, *_ = monobit.load(self.font_path / 'vertical.yaff')
        text1 = monobit.render(vert1, b'\x27\x27', direction='top-to-bottom').as_text(inklevels='.@')
        assert text1 == self.verttext, f'"""{text1}"""\n != \n"""{self.verttext}"""'

    def test_render_sfnt_vertical(self):
        vert1, *_ = monobit.load(self.font_path / 'vertical.otb')
        # we currently don't support storing non-unicode encoding in sfnt
        text1 = monobit.render(vert1, '\x27\x27', direction='top-to-bottom').as_text(inklevels='.@')
        assert text1 == self.verttext, f'"""{text1}"""\n != \n"""{self.verttext}"""'


    # proportional spacing

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

    def _render_proportional(
            self, format, *, char=False, load_kwargs=(), save_kwargs=(),
            inklevels='.@',
        ):
        prop1, *_ = monobit.load(self.font_path / 'wbfont.amiga/wbfont_prop.font')
        monobit.save(
            prop1, self.temp_path / f'wbfont_prop.{format}',
            format=format, **(save_kwargs or {}),
        )
        prop2, *_ = monobit.load(
            self.temp_path / f'wbfont_prop.{format}',
            format=format, **(load_kwargs or {}),
        )
        if char:
            text = 'testing'
        else:
            text = b'testing'
        rendered_text = monobit.render(prop2, text).as_text(inklevels=inklevels)
        assert_text_eq(rendered_text, self.proptext)

    def test_amiga_proportional(self):
        self._render_proportional('amiga')

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
        self._render_proportional('sfnt', char=True)

    def test_beos_proportional(self):
        self._render_proportional('beos', inklevels='.123456789ABCDE@')

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

    def _render_kerning(self, format, char=False):
        webby_mod1, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        monobit.save(
            webby_mod1, self.temp_path / f'webby-small-kerned.{format}',
            format=format,
        )
        webby_mod2, *_ = monobit.load(
            self.temp_path / f'webby-small-kerned.{format}',
            format=format,
        )
        if char:
            text = 'sjifjij'
        else:
            text = b'sjifjij'
        rendered_text = monobit.render(webby_mod2, text).as_text(inklevels='.@')
        assert_text_eq(rendered_text, self.kerntext)

    def test_render_yaff_kerning(self):
        self._render_kerning('yaff')

    def test_render_bmf_kerning(self):
        self._render_kerning('bmfont')

    def test_render_otb_kerning(self):
        self._render_kerning('sfnt', char=True)

    def test_render_mac_kerning(self):
        self._render_kerning('mac')


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
        text = monobit.render(font, b'01234').as_text(inklevels='.@')
        assert_text_eq(text, self.testtext)

    def _render_kerning_bearings(self, format, char=False, **save_kwargs):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(
            font, self.temp_path / 'positioning.fnt',
            format=format, **save_kwargs,
        )
        font, *_ = monobit.load(self.temp_path / 'positioning.fnt', format=format)
        if char:
            text = '01234'
        else:
            text = b'01234'
        rendered_text = monobit.render(font, text).as_text(inklevels='.@')
        assert_text_eq(rendered_text, self.testtext)

    def test_render_bmf_kerning_bearings_binary(self):
        self._render_kerning_bearings('bmfont', descriptor='binary')

    def test_render_bmf_kerning_bearings_text(self):
        self._render_kerning_bearings('bmfont', descriptor='text')

    def test_render_bmf_kerning_bearings_xml(self):
        self._render_kerning_bearings('bmfont', descriptor='xml')

    def test_render_bmf_kerning_bearings_json(self):
        self._render_kerning_bearings('bmfont', descriptor='json')

    def test_render_otb_kerning_bearings(self):
        self._render_kerning_bearings('sfnt', char=True)

    def test_render_mac_kerning_bearings(self):
        self._render_kerning_bearings('mac', resource_type='NFNT')

    bearing_testtext="""\
..@..
..@..
..@..
..@..
..@..
"""

    def _render_bearings(self, format, char=False, inklevels='.@', **save_kwargs):
        font, *_ = monobit.load(self.font_path / 'positioning.yaff')
        monobit.save(font, self.temp_path / f'positioning.{format}', format=format, **save_kwargs)
        font, *_ = monobit.load(self.temp_path / f'positioning.{format}', format=format)
        if char:
            text = monobit.render(font, '012').as_text(inklevels=inklevels)
        else:
            text = monobit.render(font, b'012').as_text(inklevels=inklevels)
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

    def test_yaff_negbearings(self):
        self._render_bearings('amiga')

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

    def test_beos_negbearings(self):
        self._render_bearings('beos', inklevels='.123456789ABCDE@')


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
        text = monobit.render(font, '678', direction='ttb').as_text(inklevels='.@')
        assert_text_eq(text, self.testvert)

    def test_vert_neg_bearings_yaff(self):
        self._render_vert_bearings('yaff')

    def test_vert_neg_bearings_bdf(self):
        self._render_vert_bearings('bdf')

    def test_vert_neg_bearings_otb(self):
        self._render_vert_bearings('sfnt')


if __name__ == '__main__':
    unittest.main()
