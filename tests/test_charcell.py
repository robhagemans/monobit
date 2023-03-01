"""
monobit test suite
charcacter-cell format tests
"""

import os
import unittest

import monobit
from .base import BaseTester, assert_text_eq



class TestCharCell(BaseTester):
    """Test character-cell export."""

    fixed8x8 = (
        BaseTester.fixed4x6
        .expand(right=4, bottom=2, adjust_metrics=False)
        .modify(shift_up=1)
    )
    fixed8x8r = (
        fixed8x8
        .modify(encoding='cp437')
        .label(codepoint_from='cp437')
        .subset(range(20, 256))
        .reduce()
    )

    fixed8x8_A = """\
.@......
@.@.....
@@@.....
@.@.....
@.@.....
........
........
........
"""

    def _test_export_charcell_reduced(self, format, count=191, label=b'A', **load_kwargs):
        """Test exporting a reduced-raster character-cell font."""
        file = self.temp_path / 'testfont.fnt'
        monobit.save(self.fixed8x8r, file, format=format)
        font, *_ = monobit.load(file, format=format, **load_kwargs)
        self.assertEqual(len(font.glyphs), count)
        assert_text_eq(font.get_glyph(label).as_text(), self.fixed8x8_A)


    def test_export_hex_r(self):
        """Test exporting extended hex files."""
        self._test_export_charcell_reduced('pcbasic', label='A')

    def test_export_psf_r(self):
        """Test exporting psf files."""
        self._test_export_charcell_reduced('psf', label='A')

    def test_export_dec_r(self):
        """Test exporting dec-drcs files."""
        self._test_export_charcell_reduced('dec', count=94)

    def test_export_raw_r(self):
        """Test exporting raw binary files."""
        self._test_export_charcell_reduced('raw', first_codepoint=0x20)

    def test_export_c_r(self):
        """Test exporting c source files."""
        self._test_export_charcell_reduced('c', first_codepoint=0x20)

    def test_export_py_r(self):
        """Test exporting Python source files."""
        self._test_export_charcell_reduced('python', first_codepoint=0x20)

    def test_export_json_r(self):
        """Test exporting JSON source files."""
        self._test_export_charcell_reduced('json', first_codepoint=0x20)

    def test_export_png_r(self):
        """Test exporting image files."""
        self._test_export_charcell_reduced('image', count=192, first_codepoint=0x20)

    def test_export_cpi_r(self):
        """Test exporting CPI (FONT) files."""
        self._test_export_charcell_reduced('cpi', count=256)

    def test_export_cp_r(self):
        """Test exporting kbd CP files"""
        self._test_export_charcell_reduced('kbd', count=256)

    def test_export_fontx_r(self):
        """Test exporting fontx files."""
        self._test_export_charcell_reduced('fontx', count=256)

    def test_export_bbc_r(self):
        """Test exporting bbc files."""
        self._test_export_charcell_reduced('bbc')

    def test_export_xbin_r(self):
        """Test exporting XBIN files."""
        self._test_export_charcell_reduced('xbin', count=256)

    def test_export_hbf_r(self):
        """Test exporting HBF files."""
        format = 'hbf'
        count = 727
        label = b'\1\0'
        glyph_0x100 = """\
........
@@@.....
.@......
@.@.....
@@@.....
@.@.....
........
........
"""
        file = self.temp_path / 'testfont.fnt'
        monobit.save(self.fixed8x8.reduce(), file, format=format)
        font, *_ = monobit.load(file, format=format)
        self.assertEqual(len(font.glyphs), count)
        assert_text_eq(font.get_glyph(label).as_text(), glyph_0x100)


if __name__ == '__main__':
    unittest.main()
