"""
monobit test suite
import/export tests
"""

import os
import unittest

import monobit
from .base import BaseTester


class TestFormats(BaseTester):
    """Test monobit export/import."""

    def test_import_bdf(self):
        """Test importing bdf files."""
        font, *_ = monobit.load(self.font_path / '4x6.bdf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_bdf(self):
        """Test exporting bdf files."""
        bdf_file = self.temp_path / '4x6.bdf'
        monobit.save(self.fixed4x6, bdf_file)
        self.assertTrue(os.path.getsize(bdf_file) > 0)

    def test_import_draw(self):
        """Test importing draw files."""
        font, *_ = monobit.load(self.font_path / '8x16.draw')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_draw(self):
        """Test exporting draw files."""
        draw_file = self.temp_path / '8x16.draw'
        monobit.save(self.fixed8x16, draw_file)
        self.assertTrue(os.path.getsize(draw_file) > 0)

    def test_import_fon(self):
        """Test importing fon files."""
        font, *_ = monobit.load(self.font_path / '6x13.fon')
        # there will be fewer chars if we drop blanks as undefined
        self.assertEqual(len(font.glyphs), 256)

    def test_export_fon(self):
        """Test exporting fon files."""
        fon_file = self.temp_path / '4x6.fon'
        monobit.save(self.fixed4x6, fon_file)
        self.assertTrue(os.path.getsize(fon_file) > 0)

    def test_import_fnt(self):
        """Test importing fnt files."""
        font, *_ = monobit.load(self.font_path / '6x13.fnt')
        # there will be fewer chars if we drop blanks as undefined
        self.assertEqual(len(font.glyphs), 256)

    def test_export_fnt(self):
        """Test exporting fnt files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_hex(self):
        """Test importing hex files."""
        self.assertEqual(len(self.fixed8x16.glyphs), 919)

    def test_export_hex(self):
        """Test exporting hex files."""
        hex_file = self.temp_path / '8x16.hex'
        monobit.save(self.fixed8x16, hex_file)
        self.assertTrue(os.path.getsize(hex_file) > 0)

    def test_import_psf(self):
        """Test importing psf files."""
        font, *_ = monobit.load(self.font_path / '4x6.psf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_psf(self):
        """Test exporting psf files."""
        psf_file = self.temp_path / '4x6.psf'
        monobit.save(self.fixed4x6, psf_file)
        self.assertTrue(os.path.getsize(psf_file) > 0)

    def test_import_fzx(self):
        """Test importing fzx files."""
        font, *_ = monobit.load(self.font_path / '4x6.fzx')
        self.assertEqual(len(font.glyphs), 191)

    def test_export_fzx(self):
        """Test exporting fzx files."""
        fzx_file = self.temp_path / '4x6.fzx'
        monobit.save(self.fixed4x6, fzx_file)
        self.assertTrue(os.path.getsize(fzx_file) > 0)

    def test_import_dec_drcs(self):
        """Test importing dec-drcs files."""
        font, *_ = monobit.load(self.font_path / '6x13.dec')
        self.assertEqual(len(font.glyphs), 94)

    def test_export_dec_drcs(self):
        """Test exporting dec-drcs files."""
        dec_file = self.temp_path / '8x16.dec'
        monobit.save(self.fixed8x16, dec_file)
        self.assertTrue(os.path.getsize(dec_file) > 0)

    def test_import_yaff(self):
        """Test importing yaff files"""
        self.assertEqual(len(self.fixed4x6.glyphs), 919)

    def test_export_yaff(self):
        """Test exporting yaff files"""
        yaff_file = self.temp_path / '4x6.yaff'
        monobit.save(self.fixed4x6, yaff_file)
        self.assertTrue(os.path.getsize(yaff_file) > 0)

    def test_import_raw(self):
        """Test importing raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6.raw', cell=(4, 6))
        self.assertEqual(len(font.glyphs), 919)

    def test_export_raw(self):
        """Test exporting raw binary files."""
        fnt_file = self.temp_path / '4x6.raw'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_export_pdf(self):
        """Test exporting pdf files."""
        pdf_file = self.temp_path / '4x6.pdf'
        monobit.save(self.fixed4x6, pdf_file)
        self.assertTrue(os.path.getsize(pdf_file) > 0)

    def test_import_bmf(self):
        """Test importing bmfont files."""
        base_path = self.font_path / '6x13.bmf'
        font, *_ = monobit.load('6x13-text.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load('6x13-xml.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load('6x13-json.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load('6x13-8bit.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load('6x13-32bit-packed.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load('6x13-32bit-nonpacked.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load('6x13-binary.fnt', where=base_path, format='bmf')
        self.assertEqual(len(font.glyphs), 189)

    def test_export_bmf(self):
        """Test exporting bmfont files."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(self.fixed4x6, fnt_file, where=self.temp_path)
        self.assertTrue(os.path.getsize(fnt_file) > 0)
        monobit.save(self.fixed4x6, fnt_file, where=self.temp_path, descriptor='json', overwrite=True)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_c(self):
        """Test importing c source files."""
        font, *_ = monobit.load(
            self.font_path / '4x6.c',
            identifier='char font_Fixed_Medium_6', cell=(4, 6)
        )
        self.assertEqual(len(font.glyphs), 919)

    def test_export_c(self):
        """Test exporting c source files."""
        fnt_file = self.temp_path  / '4x6.c'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_export_py(self):
        """Test exporting Python source files."""
        fnt_file = self.temp_path  / '4x6.py'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_export_json(self):
        """Test exporting JSON source files."""
        fnt_file = self.temp_path  / '4x6.json'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_png(self):
        """Test importing image files."""
        font, *_ = monobit.load(self.font_path / '4x6.png', cell=(4, 6), count=919)
        self.assertEqual(len(font.glyphs), 919)

    def test_export_png(self):
        """Test exporting image files."""
        fnt_file = self.temp_path / '4x6.png'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_cpi_font(self):
        """Test importing CPI (FONT) files"""
        fnt_file = self.font_path / '8x16-font.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)

    def test_import_cpi_fontnt(self):
        """Test importing CPI (FONT.NT) files"""
        fnt_file = self.font_path / '8x16-fontnt.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)

    def test_import_cpi_drfont(self):
        """Test importing CPI (DRFONT) files"""
        fnt_file = self.font_path / '8x16-drfont.cpi'
        pack = monobit.load(fnt_file)
        font = pack[0]
        self.assertEqual(len(font.glyphs), 256)

    def test_import_cp(self):
        """Test importing kbd CP files"""
        fnt_file = self.font_path / '8x16.cp'
        pack = monobit.load(fnt_file)
        font = pack[0]
        self.assertEqual(len(font.glyphs), 256)

    def test_import_flf(self):
        """Test importing flf files."""
        font, *_ = monobit.load(self.font_path / '4x6.flf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_flf(self):
        """Test exporting flf files."""
        file = self.temp_path / '4x6.flf'
        monobit.save(self.fixed4x6, file)
        self.assertTrue(os.path.getsize(file) > 0)

    def test_import_dfont(self):
        """Test importing dfont files."""
        font, *_ = monobit.load(self.font_path / '4x6.dfont')
        # only 195 glyphs in the font as it's in mac-roman encoding now
        self.assertEqual(len(font.glyphs), 195)

    def test_import_amiga(self):
        """Test importing amiga font files."""
        font, *_ = monobit.load(self.font_path / 'wbfont.amiga' / 'wbfont_prop.font')
        self.assertEqual(len(font.glyphs), 225)


if __name__ == '__main__':
    unittest.main()
