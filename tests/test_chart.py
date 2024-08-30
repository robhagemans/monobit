"""
monobit test suite
chart tests
"""

import os
import unittest

import monobit
from .base import BaseTester, assert_text_eq


class TestChart(BaseTester):

    prop, *_ = monobit.load(BaseTester.font_path / 'wbfont.amiga/wbfont_prop.font')


    def test_export_pdf(self):
        """Test exporting pdf files."""
        pdf_file = self.temp_path / 'chart.pdf'
        monobit.save(self.prop, pdf_file)
        # we're only checking a pdf file was produced
        # the file is timestamped so not fully reproducible
        with open(pdf_file, 'rb') as pdf:
            magic = pdf.readline()
        self.assertEqual(magic, b'%PDF-1.3\n')

    def test_export_chart(self):
        """Test exporting text chart."""
        txt_file = self.temp_path / 'chart.txt'
        monobit.save(self.prop, txt_file, format='chart')
        with open(txt_file) as output, open(self.font_path / 'chart.txt') as model:
            self.assertListEqual(list(output), list(model))

    def test_export_blocks(self):
        """Test exporting blocks chart."""
        txt_file = self.temp_path / 'blocks.txt'
        monobit.save(self.prop, txt_file, format='blocks')
        with open(txt_file) as output, open(self.font_path / 'blocks.txt') as model:
            self.assertListEqual(list(output), list(model))

    def test_export_shades(self):
        """Test exporting shaded blocks chart."""
        txt_file = self.temp_path / 'shades.txt'
        monobit.save(self.prop, txt_file, format='shades')
        with open(txt_file) as output, open(self.font_path / 'shades.txt') as model:
            self.assertListEqual(list(output), list(model))


if __name__ == '__main__':
    unittest.main()
