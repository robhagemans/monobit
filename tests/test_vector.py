"""
monobit test suite
vector format import/export tests
"""

import os
import unittest

import monobit
from .base import BaseTester, ensure_asset, assert_text_eq


class TestVector(BaseTester):
    """Test monobit export/import."""

    # vector formats

    def test_import_hershey(self):
        """Test importing Hershey font in Jim Hurt's format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey-az.jhf')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_import_svg(self):
        """Test importing Hershey font in SVG format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.svg')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_import_vector_fon(self):
        """Test importing Hershey font in Windows vector format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.fon')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_import_vector_yaff(self):
        """Test importing Hershey font in yaff format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.yaff')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_import_chr(self):
        """Test importing Hershey font in Borland CHR format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.chr')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    dosstart = 'https://archive.org/download/dosstart-19b/dosstart.zip/'

    def test_import_dosstart_stroke(self):
        """Test importing DosStart stroke files."""
        file = ensure_asset(self.dosstart, 'DOSSTART.DSF')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 95)

    gimms = 'https://gtoal.com/vectrex/vector_fonts/gimms/'

    def test_import_gimms(self):
        """Test importing GIMMS files."""
        file = ensure_asset(self.gimms, 'GIMMS.BIN')
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 31)
        self.assertEqual(len(fonts[6].glyphs), 57)
        self.assertEqual(
            str(fonts[6].glyphs[29].path),
            'm 5 9\nl -4 -9\nm 4 9\nl 4 -9\nm -6 3\nl 4 0\nm 3 -3'
        )

    def test_export_svg(self):
        """Test exporting Hershey font in SVG format."""
        monobit.save(self.hershey, self.temp_path / 'hershey.svg')
        font, *_ = monobit.load(self.temp_path / 'hershey.svg')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_export_vector_fon(self):
        """Test exporting Hershey font in Windows vector format."""
        monobit.save(
            self.hershey, self.temp_path / 'hershey.fon',
            format='mzfon', vector=True
        )
        font, *_ = monobit.load(self.temp_path / 'hershey.fon')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_export_vector_yaff(self):
        """Test exporting Hershey font in yaff format."""
        monobit.save(self.hershey, self.temp_path / 'hershey.yaff')
        font, *_ = monobit.load(self.temp_path / 'hershey.yaff')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)

    def test_export_chr(self):
        """Test exporting Hershey font in Borland CHR format."""
        monobit.save(self.hershey, self.temp_path / 'hershey.chr', format='borland')
        font, *_ = monobit.load(self.temp_path / 'hershey.chr')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(str(font.glyphs[0].path), self.hershey_A_path)


if __name__ == '__main__':
    unittest.main()
