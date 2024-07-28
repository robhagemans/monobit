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
        .subset(range(32, 256))
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

    def test_cell_size_r_no_vert(self):
        """Test cell size determination of reduced font."""
        font = self.fixed8x8.reduce()
        assert font.spacing == 'character-cell'
        assert font.cell_size == (8, 8)

    def test_cell_size_r(self):
        """Test cell size determination of reduced font."""
        assert self.fixed8x8r.spacing == 'character-cell'
        assert self.fixed8x8r.cell_size == (8, 8)

    def test_cell_size_(self):
        """Test cell size determination of reduced font."""
        assert self.fixed8x8.spacing == 'character-cell'
        assert self.fixed8x8.cell_size == (8, 8)


    def _test_export_charcell_reduced(
            self, format, container_format='', count=191, label=b'A', codepage=None,
            save_kwargs=None, **load_kwargs
        ):
        """Test exporting a reduced-raster character-cell font."""
        file = self.temp_path / 'testfont.fnt'
        save_kwargs = save_kwargs or {}
        font = self.fixed8x8r
        if codepage:
            font = font.modify(encoding=codepage)
            font = font.label(codepoint_from=codepage, overwrite=True)
        monobit.save(font, file, format=format, container_format=container_format, **save_kwargs)
        font, *_ = monobit.load(file, format=format, container_format=container_format, **load_kwargs)
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
        self._test_export_charcell_reduced('raw', container_format='c', first_codepoint=0x20)

    def test_export_py_r(self):
        """Test exporting Python source files."""
        self._test_export_charcell_reduced('raw', container_format='python', first_codepoint=0x20)

    def test_export_json_r(self):
        """Test exporting JSON source files."""
        self._test_export_charcell_reduced('raw', container_format='json', first_codepoint=0x20)

    def test_export_png_r(self):
        """Test exporting image files."""
        self._test_export_charcell_reduced(
            'image', first_codepoint=0x20, cell=(8, 8),
        )

    def test_export_cpi_r(self):
        """Test exporting CPI (FONT) files."""
        self._test_export_charcell_reduced('cpi', count=256, codepage='cp437')

    def test_export_cp_r(self):
        """Test exporting kbd CP files"""
        self._test_export_charcell_reduced('kbd', count=256, codepage='cp437')

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
        # HBF will store offsets and bearings
        # so the glyph raster is equalised to the font bounding box
        glyph_0x100 = """\
@@@.
.@..
@.@.
@@@.
@.@.
....
"""
        file = self.temp_path / 'testfont.fnt'
        monobit.save(self.fixed8x8.reduce(), file, format=format)
        font, *_ = monobit.load(file, format=format)
        self.assertEqual(len(font.glyphs), count)
        assert_text_eq(font.get_glyph(label).as_text(), glyph_0x100)



class TestBigCell(BaseTester):
    """Test exporting wider than 8 pixel charcell fonts."""

    gallant = monobit.load(BaseTester.font_path / 'gallant12x22.h', format='netbsd')

    gallant_A = """\
.....@@.....
.....@@.....
....@.@@....
....@.@@....
....@..@....
...@...@@...
...@...@@...
...@....@...
..@@@@@@@@..
..@.....@@..
..@......@..
.@.......@@.
.@.......@@.
@@@.....@@@@
"""

    def _export_bigcell(self, format, label='A'):
        """Test exporting freebsd vt font files with two-cell glyphs."""
        fnt_file = self.temp_path / 'gallant.fnt'
        monobit.save(self.gallant, fnt_file, format=format)
        font, *_ = monobit.load(fnt_file, format=format)
        self.assertEqual(font.get_glyph(label).reduce().as_text(), self.gallant_A)

    def test_bigcell_yaff(self):
        self._export_bigcell(format='yaff')

    def test_bigcell_dec(self):
        self._export_bigcell(format='dec')

    def test_bigcell_fontx(self):
        self._export_bigcell(format='fontx', label=b'A')

    def test_bigcell_grasp(self):
        self._export_bigcell(format='grasp', label=b'A')

    # HBF doesn't store latin range
    # def test_bigcell_hbf(self):
    #     self._export_bigcell(format='hbf')

    def test_bigcell_netbsd(self):
        self._export_bigcell(format='netbsd')

    def test_bigcell_psf(self):
        self._export_bigcell(format='psf')

    def test_bigcell_psf2txt(self):
        self._export_bigcell(format='psf2txt')

    def test_bigcell_vtfont(self):
        self._export_bigcell(format='vtfont')

    def test_bigcell_wsfont(self):
        self._export_bigcell(format='wsfont')


class TestMultiCell(BaseTester):
    """Test exporting multi-cell fonts."""

    unscii_16 = monobit.load(BaseTester.font_path / 'unscii-16.hex')

    unscii_16_A = """\
..@@..
.@@@@.
@@..@@
@@..@@
@@..@@
@@@@@@
@@..@@
@@..@@
@@..@@
@@..@@
@@..@@
"""

    unscii_16_A_wide = """\
....@@@@....
..@@@@@@@@..
@@@@....@@@@
@@@@....@@@@
@@@@....@@@@
@@@@@@@@@@@@
@@@@....@@@@
@@@@....@@@@
@@@@....@@@@
@@@@....@@@@
@@@@....@@@@
"""


    def _export_multicell(self, format):
        """Test exporting freebsd vt font files with two-cell glyphs."""
        fnt_file = self.temp_path / 'unscii-16.fnt'
        monobit.save(self.unscii_16, fnt_file, format=format)
        font, *_ = monobit.load(fnt_file, format=format)
        self.assertEqual(len(font.glyphs), 3240)
        self.assertEqual(font.spacing, 'multi-cell')
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.unscii_16_A)
        self.assertEqual(font.get_glyph('\uFF21').reduce().as_text(), self.unscii_16_A_wide)


    def test_export_yaff_multicell(self):
        self._export_multicell(format='yaff')

    def test_export_vtfont_multicell(self):
        self._export_multicell(format='vtfont')

    def test_export_hex_multicell(self):
        self._export_multicell(format='unifont')


if __name__ == '__main__':
    unittest.main()
