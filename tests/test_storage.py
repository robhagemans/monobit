"""
monobit test suite
storage tests
"""

import os
import io
import unittest
import logging
import glob

import monobit
from .base import BaseTester, ensure_asset


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

    def test_double_gzip2(self):
        """Test importing doubly gzip compressed files."""
        self._test_double('gz')

    def test_double_lzma(self):
        """Test importing doubly lzma compressed files."""
        self._test_double('xz')

    def test_double_bz2(self):
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

    def test_email(self):
        """Test importing/exporting MIME messages."""
        self._test_container('eml')

    def test_7zip(self):
        """Test importing/exporting 7-zip files."""
        self._test_container('7z')

    def test_cpio(self):
        """Test importing/exporting CPIO files."""
        self._test_container('cpio')

    def test_pax(self):
        """Test importing/exporting PAX files."""
        self._test_container('pax')

    def test_xar(self):
        """Test importing/exporting XAR files."""
        self._test_container('xar')

    def test_ar(self):
        """Test importing/exporting AR files."""
        self._test_container('ar')

    def test_warc(self):
        """Test importing/exporting WARC files."""
        self._test_container('warc')

    def test_iso9660(self):
        """Test importing/exporting ISO9660 files."""
        self._test_container('iso')

    def test_dir(self):
        """Test exporting to directory."""
        dir = self.temp_path / f'test4x6/4x6'
        monobit.save(self.fixed4x6, dir)
        self.assertTrue(dir.is_dir())
        fonts = monobit.load(dir)
        self.assertEqual(len(fonts), 1)

    def test_recursive_tgz(self):
        """Test recursively traversing tar.gz container."""
        container_file = self.font_path / 'fontdir.tar.gz'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_zip(self):
        """Test recursively traversing zip container."""
        container_file = self.font_path / 'fontdir.zip'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_rar(self):
        """Test recursively traversing rar container."""
        container_file = self.font_path / 'fontdir.rar'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_7z(self):
        """Test recursively traversing 7-zip container."""
        container_file = self.font_path / 'fontdir.7z'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    @unittest.skip
    def test_recursive_iso(self):
        """Test recursively traversing ISO 9660 container."""
        container_file = self.font_path / 'fontdir.iso'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_cpio(self):
        """Test recursively traversing CPIO container."""
        container_file = self.font_path / 'fontdir.cpio'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_cab(self):
        """Test recursively traversing Cabinet container."""
        container_file = self.font_path / 'fontdir.cab'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    def test_recursive_dir(self):
        """Test recursively traversing directory."""
        container_file = self.font_path / 'fontdir'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 3)

    @unittest.skip
    def test_ar(self):
        """Test recursively traversing AR container."""
        container_file = self.font_path / 'twofonts.ar'
        fonts = monobit.load(container_file)
        self.assertEqual(len(fonts), 2)

    def test_empty(self):
        """Test empty container."""
        container_file = self.font_path / 'empty.zip'
        with self.assertRaises(monobit.FileFormatError):
            fonts = monobit.load(container_file)

    def test_baddeeplink_tgz(self):
        """Test deep linking into tar.gz container."""
        file = self.font_path / 'fontdir.tar.gz' / 'not_the_subdir' / '6x13.fon.bz2'
        with self.assertRaises(FileNotFoundError):
            fonts = monobit.load(file)

    def test_baddeeplink_zip(self):
        """Test deep linking into zip container."""
        file = self.font_path / 'fontdir.zip' / 'not_the_subdir' / '6x13.fon.bz2'
        with self.assertRaises(FileNotFoundError):
            fonts = monobit.load(file)

    def test_deeplink_tgz(self):
        """Test deep linking into tar.gz container."""
        file = self.font_path / 'fontdir.tar.gz' / 'subdir' / '6x13.fon.bz2'
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 1)

    def test_deeplink_zip(self):
        """Test deep linking into zip container."""
        file = self.font_path / 'fontdir.zip' / 'subdir' / '6x13.fon.bz2'
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 1)

    def test_deeplink_dir(self):
        """Test deep linking into directory."""
        file = self.font_path / 'fontdir' / 'subdir' / '6x13.fon.bz2'
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 1)

    def test_deeplink_dir_case_insensitive(self):
        """Test case insensitive deep linking into directory."""
        file = self.font_path / 'fontdir' / 'SUBDIR' / '6x13.FON.bz2'
        fonts = monobit.load(str(file).upper())
        self.assertEqual(len(fonts), 1)

    def test_deeplink_dir_case_sensitive(self):
        """Test case sensitive deep linking into directory."""
        file = self.font_path / 'fontdir' / 'SUBDIR' / '6x13.FON.bz2'
        with self.assertRaises(FileNotFoundError):
            fonts = monobit.load(str(file).upper(), match_case=True)
            print(fonts)

    def test_nested_zip(self):
        """Test zipfile in zipfile."""
        fonts = monobit.load(self.font_path / 'zipinzip.zip')
        self.assertEqual(len(fonts), 1)
        fonts1 = monobit.load(self.font_path / 'zipinzip.zip' / 'zipinzip.zip')
        self.assertEqual(len(fonts1), 1)

    def test_deeplink_nested_zip(self):
        """Test deeplinking into zipfile in zipfile."""
        fonts = monobit.load(
            self.font_path / 'zipinzip.zip' / 'zipinzip.zip' / '4x6.yaff'
        )
        self.assertEqual(len(fonts), 1)

    def test_deeplink_nested_zip_write(self):
        """Test writing deep linked into nested zip container."""
        file = self.temp_path / 'fontdir.zip' / 'a' / 'subdir.zip' / 'b' / '4x6.yaff'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 919)

    def test_deeplink_lha(self):
        """Test deep linking into LHA container."""
        file = self.font_path / 'wbfont.lha' / 'fonts' / 'wbfont_prop.font'
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 1)


class TestForks(BaseTester):

    def test_import_macbinary(self):
        """Test importing macbinary files."""
        font, *_ = monobit.load(self.font_path / '4x6.bin', container_format='macbin')
        self.assertEqual(len(font.glyphs), 195)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_hexbin(self):
        """Test importing hexbin files."""
        font, *_ = monobit.load(self.font_path / '4x6.hqx')
        self.assertEqual(len(font.glyphs), 195)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    macfonts = 'https://github.com/JohnDDuncanIII/macfonts/raw/master/Macintosh%20OS%201-6/Originals/'

    def test_import_appledouble(self):
        """Test importing appledouble files."""
        file = ensure_asset(self.macfonts, 'Originals.zip')
        font, *_ = monobit.load(file / '__MACOSX/._Times  9')
        self.assertEqual(len(font.glyphs), 228)


class TestWrappers(BaseTester):
    """Test wrappers."""

    # Source coded binary and textbin wrappers

    def test_import_c(self):
        """Test importing c source files."""
        font, *_ = monobit.load(
            self.font_path / '4x6.c' / 'font_Fixed_Medium_6',
            cell=(4, 6)
        )
        self.assertEqual(len(font.glyphs), 919)

    def test_import_bas(self):
        """Test importing BASIC source files."""
        font, *_ = monobit.load(
            self.font_path / '4x6.bas', cell=(4, 6)
        )
        self.assertEqual(len(font.glyphs), 919)

    def test_import_intel(self):
        """Test importing Intel Hex files."""
        font, *_ = monobit.load(
            self.font_path / '4x6.ihex', cell=(4, 6)
        )
        self.assertEqual(len(font.glyphs), 919)

    def _test_export_textbin(self, suffix, container_format=''):
        file = self.temp_path / f'4x6.{suffix}'
        monobit.save(
            self.fixed4x6, file, format='raw', container_format=container_format
        )
        font, *_ = monobit.load(
            file, format='raw', cell=(4, 6), first_codepoint=31,
            container_format=container_format
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_c(self):
        """Test exporting c source files."""
        self._test_export_textbin(suffix='c')

    def test_export_py(self):
        """Test exporting Python source files."""
        self._test_export_textbin(suffix='py')

    def test_export_json(self):
        """Test exporting JSON source files."""
        self._test_export_textbin(suffix='json')

    def test_export_pas(self):
        """Test exporting Pascal source files."""
        self._test_export_textbin(suffix='pas')

    def test_export_bas(self):
        """Test exporting BASIC source files."""
        self._test_export_textbin(suffix='bas')

    def test_export_intel(self):
        """Test exporting Intel Hex files."""
        self._test_export_textbin(suffix='ihex')

    def test_export_base64(self):
        """Test exporting base64 files."""
        self._test_export_textbin(suffix='b64', container_format='base64')

    def test_export_quopri(self):
        """Test exporting quoted-printable files."""
        self._test_export_textbin(suffix='qp', container_format='quopri')

    def test_export_uuencode(self):
        """Test exporting uuencoded files."""
        self._test_export_textbin(suffix='uu', container_format='uuencode')

    def test_export_yencode(self):
        """Test exporting yencoded files."""
        self._test_export_textbin(suffix='yenc', container_format='yenc')


class TestStreams(BaseTester):
    """Test stream i/o."""

    def test_binary_stream(self):
        """Test importing psf files from binary stream."""
        with open(self.font_path / '4x6.psf', 'rb') as f:
            fontbuffer = f.read()
        # we need peek()
        with io.BufferedReader(io.BytesIO(fontbuffer)) as stream:
            font, *_ = monobit.load(stream)
        self.assertEqual(len(font.glyphs), 919)

    def test_text_stream(self):
        """Test importing bdf files from text stream."""
        # we still need an underlying binary buffer, which StringIO doesn't have
        with open(self.font_path / '4x6.bdf', 'rb') as f:
            fontbuffer = f.read()
        with io.TextIOWrapper(io.BufferedReader(io.BytesIO(fontbuffer))) as stream:
            font, *_ = monobit.load(stream)
        self.assertEqual(len(font.glyphs), 919)

    def test_output_stream(self):
        """Test outputting multi-yaff file to text stream."""
        # we still need an underlying binary buffer, which StringIO doesn't have
        fnt_file = self.font_path / '8x16-font.cpi'
        fonts = monobit.load(fnt_file)
        with io.BytesIO() as stream:
            monobit.save(fonts, stream)
            output = stream.getvalue()
            self.assertTrue(len(output) > 80000)
            self.assertTrue(stream.getvalue().startswith(b'---'))


if __name__ == '__main__':
    unittest.main()
