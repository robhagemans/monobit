"""
monobit test suite
chart tests
"""

import os
import unittest

import monobit
from .base import BaseTester, assert_text_eq


class TestChart(BaseTester):

    # PDF chart

    def test_export_pdf(self):
        """Test exporting pdf files."""
        pdf_file = self.temp_path / '4x6.pdf'
        monobit.save(self.fixed4x6, pdf_file)
        self.assertTrue(os.path.getsize(pdf_file) > 0)


if __name__ == '__main__':
    unittest.main()
