"""
Basic monobit test coverage

usage::

    $ python3 -m tests.test_monobit

    $ coverage run tests/test_monobit.py
    $ coverage report monobit/*py
"""

import os
import io
import tempfile
import unittest
import logging
from pathlib import Path

import monobit


class BaseTester(unittest.TestCase):
    """Base class for testers."""

    logging.basicConfig(level=logging.WARNING)

    font_path = Path('tests/fonts/')

    # fonts are immutable so no problem in loading only once
    fixed4x6, *_ = monobit.load(font_path / '4x6.yaff')
    fixed8x16, *_ = monobit.load(font_path / '8x16.hex')

    def setUp(self):
        """Setup ahead of each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()


class TestCodecs(BaseTester):
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
        self.assertEqual(len(font.glyphs), 249)

    def test_export_fon(self):
        """Test exporting fon files."""
        fon_file = self.temp_path / '4x6.fon'
        monobit.save(self.fixed4x6, fon_file)
        self.assertTrue(os.path.getsize(fon_file) > 0)

    def test_import_fnt(self):
        """Test importing fnt files."""
        font, *_ = monobit.load(self.font_path / '6x13.fnt')
        self.assertEqual(len(font.glyphs), 249)

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

    def test_export_pdf(self):
        """Test exporting pdf files."""
        pdf_file = self.temp_path / '4x6.pdf'
        monobit.save(self.fixed4x6, pdf_file)
        self.assertTrue(os.path.getsize(pdf_file) > 0)

    def test_export_png(self):
        """Test exporting png files."""
        png_file = self.temp_path / '4x6.png'
        monobit.save(self.fixed4x6, png_file)
        self.assertTrue(os.path.getsize(png_file) > 0)

    def test_import_psf(self):
        """Test importing psf files."""
        font, *_ = monobit.load(self.font_path / '4x6.psf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_psf(self):
        """Test exporting psf files."""
        psf_file = self.temp_path / '4x6.psf'
        monobit.save(self.fixed4x6, psf_file)
        self.assertTrue(os.path.getsize(psf_file) > 0)

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
        """Test exporting to pdf."""
        fnt_file = self.temp_path / '4x6.pdf'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

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
        monobit.save(self.fixed4x6, fnt_file, where=self.temp_path, overwrite=True)
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

    def test_import_png(self):
        """Test importing image files."""
        font, *_ = monobit.load(self.font_path / '4x6.png', cell=(4, 6), n_chars=919)
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


class TestCompressed(BaseTester):
    """Test compression formats."""

    def _test_compressed(self, format):
        """Test importing/exporting compressed files."""
        compressed_file = self.temp_path / f'4x6.yaff.{format}'
        monobit.save(self.fixed4x6, compressed_file)
        self.assertTrue(os.path.getsize(compressed_file) > 0)
        font, *_ = monobit.load(compressed_file)
        self.assertEqual(len(font.glyphs), 919)

    def test_gzip(self):
        """Test importing/exporting gzip compressed files."""
        self._test_compressed('gz')

    def test_lzma(self):
        """Test importing/exporting lzma compressed files."""
        self._test_compressed('xz')

    def test_bz2(self):
        """Test importing/exporting bzip2 compressed files."""
        self._test_compressed('bz2')


    def _test_double(self, format):
        """Test doubly compressed files."""
        container_file = self.font_path / f'double.yaff.{format}'
        font, *_ = monobit.load(container_file)
        self.assertEqual(len(font.glyphs), 919)

    def test_gzip2(self):
        """Test importing doubly gzip compressed files."""
        self._test_double('gz')

    def test_lzma(self):
        """Test importing doubly lzma compressed files."""
        self._test_double('xz')

    def test_bz2(self):
        """Test importing doubly bzip2 compressed files."""
        self._test_double('bz2')


class TestContainers(BaseTester):
    """Test container formats."""

    def _test_container(self, format):
        """Test importing/exporting container files."""
        container_file = self.temp_path / f'4x6.yaff.{format}'
        monobit.save(self.fixed4x6, container_file)
        self.assertTrue(os.path.getsize(container_file) > 0)
        font, *_ = monobit.load(container_file)
        self.assertEqual(len(font.glyphs), 919)

    def test_zip(self):
        """Test importing/exporting zip files."""
        self._test_container('zip')

    def test_tar(self):
        """Test importing/exporting tar files."""
        self._test_container('tar')

    def test_tgz(self):
        """Test importing/exporting compressed tar files."""
        self._test_container('tar.gz')

    def test_recursive(self):
        """Test recursively traversing container."""
        container_file = self.font_path / f'fontdir.tar.gz'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_dir(self):
        """Test recursively traversing directory."""
        container_file = self.font_path / 'fontdir'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_empty(self):
        """Test empty container."""
        container_file = self.font_path / 'empty.zip'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 0)


class TestStreams(BaseTester):
    """Test stream i/o."""

    def test_binary_stream(self):
        """Test importing psf files from binary stream."""
        fontbuffer = open(self.font_path / '4x6.psf', 'rb').read()
        # we need peek()
        stream = io.BufferedReader(io.BytesIO(fontbuffer))
        font, *_ = monobit.load(stream)
        self.assertEqual(len(font.glyphs), 919)

    def test_text_stream(self):
        """Test importing bdf files from text stream."""
        # we still need an underlying binary buffer, which StringIO doesn't have
        fontbuffer = open(self.font_path / '4x6.bdf', 'rb').read()
        stream = io.TextIOWrapper(io.BufferedReader(io.BytesIO(fontbuffer)))
        font, *_ = monobit.load(stream)
        self.assertEqual(len(font.glyphs), 919)

    def test_output_stream(self):
        """Test outputting multi-yaff file to text stream."""
        # we still need an underlying binary buffer, which StringIO doesn't have
        fnt_file = self.font_path / '8x16-font.cpi'
        fonts = monobit.load(fnt_file)
        stream = io.BytesIO()
        monobit.save(fonts, stream)
        output = stream.getvalue()
        self.assertTrue(len(output) > 80000)
        self.assertTrue(stream.getvalue().startswith(b'---'))


if __name__ == '__main__':
    unittest.main()
