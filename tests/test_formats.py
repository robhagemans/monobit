"""
monobit test suite
import/export tests
"""

import os
import unittest

import monobit
from .base import BaseTester, ensure_asset, assert_text_eq


class TestFormats(BaseTester):
    """Test monobit export/import."""

    # BDF

    def test_import_bdf(self):
        """Test importing bdf files."""
        font, *_ = monobit.load(self.font_path / '4x6.bdf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_bdf(self):
        """Test exporting bdf files."""
        file = self.temp_path / '4x6.bdf'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Windows

    def test_import_fon(self):
        """Test importing fon files."""
        font, *_ = monobit.load(self.font_path / '6x13.fon')
        # there will be fewer chars if we drop blanks as undefined
        self.assertEqual(len(font.glyphs), 256)

    def test_export_fon(self):
        """Test exporting fon files."""
        fon_file = self.temp_path / '4x6.fon'
        monobit.save(self.fixed4x6, fon_file, format='mzfon')
        # read back
        font, *_ = monobit.load(fon_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fnt(self):
        """Test importing fnt files."""
        font, *_ = monobit.load(self.font_path / '6x13.fnt')
        # there will be fewer chars if we drop blanks as undefined
        self.assertEqual(len(font.glyphs), 256)

    def test_export_fnt_v1(self):
        """Test exporting v1 fnt files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='win', version=1)
        # read back
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_fnt_v1_proportional(self):
        """Test exporting v1 fnt files."""
        webby_mod, *_ = monobit.load(self.font_path / 'webby-small-kerned.yaff')
        fnt_file = self.temp_path / 'webby.fnt'
        monobit.save(webby_mod, fnt_file, format='win', version=1)
        # read back
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(
            font.get_glyph(b'A').reduce().as_text(),
            webby_mod.get_glyph(b'A').reduce().as_text(),
        )

    def test_export_fnt_v2(self):
        """Test exporting fnt files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='win', version=2)
        # read back
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_fnt_v3(self):
        """Test exporting fnt files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='win', version=3)
        # read back
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Windows PE files
    pelib = 'https://github.com/cubiclesoft/windows-pe-artifact-library/raw/master/'

    def test_import_pe_32(self):
        """Test 32-bit PE executables."""
        file = ensure_asset(
            self.pelib + '32_pe/',
            '32_pe_data_dir_resources_dir_entries_rt_font.dat'
        )
        with self.assertRaises(monobit.FileFormatError):
            # sample file does not contain an actual font
            font, *_ = monobit.load(file)

    def test_import_pe_64(self):
        """Test 64-bit PE executables."""
        file = ensure_asset(
            self.pelib + '64_pe/',
            '64_pe_data_dir_resources_dir_entries_rt_font.dat'
        )
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 224)

    # ChiWriter

    horstmann = 'https://horstmann.com/ChiWriter/'

    def test_import_chiwriter_v4(self):
        """Test importing ChiWriter v4 files."""
        file = ensure_asset(self.horstmann, 'cw4.zip')
        font, *_ = monobit.load(file / 'CW4/BOLD.CFT')
        self.assertEqual(len(font.glyphs), 159)

    def test_import_chiwriter_v3(self):
        """Test importing ChiWriter v3 files."""
        file = ensure_asset(self.horstmann, 'cw4.zip')
        font, *_ = monobit.load(file / 'CW4/GREEK.CFT')
        self.assertEqual(len(font.glyphs), 59)

    # Signum

    sigfonts = 'http://cd.textfiles.com/atarilibrary/atari_cd11/GRAFIK/SIGFONTS/'

    def test_import_signum_p9(self):
        """Test importing Signum P9 files."""
        file = ensure_asset(self.sigfonts + '9NADEL/', 'FONT_001.P9')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)

    def test_import_signum_e24(self):
        """Test importing Signum E24 files."""
        file = ensure_asset(self.sigfonts + '9NADEL/', 'FONT_001.E24')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)

    def test_import_signum_p24(self):
        """Test importing Signum P24 files."""
        file = ensure_asset(self.sigfonts + '24NADEL/', 'FONT_001.P24')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)

    def test_import_signum_l30(self):
        """Test importing Signum L30 files."""
        file = ensure_asset(self.sigfonts + 'LASER/', 'FONT_001.L30')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)

    # Unifont

    def test_import_hex(self):
        """Test importing hex files."""
        self.assertEqual(len(self.fixed8x16.glyphs), 919)

    def test_export_hex(self):
        """Test exporting hex files."""
        hex_file = self.temp_path / '8x16.hex'
        monobit.save(self.fixed8x16, hex_file)
        font, *_ = monobit.load(hex_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_draw(self):
        """Test importing draw files."""
        font, *_ = monobit.load(self.font_path / '8x16.draw')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_hexdraw(self):
        """Test exporting hexdraw files."""
        draw_file = self.temp_path / '8x16.draw'
        monobit.save(self.fixed8x16, draw_file)
        font, *_ = monobit.load(draw_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    # other text formats

    def test_export_draw(self):
        """Test exporting non-8x16 draw files with comments."""
        draw_file = self.temp_path / '4x6.draw'
        monobit.save(self.fixed4x6, draw_file)
        font, *_ = monobit.load(draw_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_psf2txt(self):
        """Test importing psf2txt files."""
        font, *_ = monobit.load(self.font_path / '4x6.txt', format='psf2txt')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_psf2txt(self):
        """Test importing psf2txt files."""
        draw_file = self.temp_path / '4x6.txt'
        monobit.save(self.fixed4x6, draw_file, format='psf2txt')
        font, *_ = monobit.load(draw_file, format='psf2txt')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_clt(self):
        """Test importing consoleet files."""
        font, *_ = monobit.load(self.font_path / '4x6.clt', format='consoleet')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_clt(self):
        """Test exporting consolet files."""
        draw_loc = self.temp_path / '4x6'
        monobit.save(self.fixed4x6, draw_loc, format='consoleet')
        font, *_ = monobit.load(draw_loc, format='consoleet')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_mkwinfont(self):
        """Test importing mkwinfont .fd files."""
        font, *_ = monobit.load(self.font_path / '6x13.fd', format='mkwinfont')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_export_mkwinfont(self):
        """Test exporting mkwinfont .fd files."""
        draw_file = self.temp_path / '4x6.fd'
        monobit.save(self.fixed4x6, draw_file, format='mkwinfont')
        font, *_ = monobit.load(draw_file, format='mkwinfont')
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # PSF

    def test_import_psf(self):
        """Test importing psf files."""
        font, *_ = monobit.load(self.font_path / '4x6.psf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_psf(self):
        """Test exporting psf files."""
        psf_file = self.temp_path / '4x6.psf'
        monobit.save(self.fixed4x6, psf_file)
        font, *_ = monobit.load(psf_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_psf1(self):
        """Test exporting psf version 1 files."""
        psf_file = self.temp_path / '8x16.psf'
        monobit.save(self.fixed8x16, psf_file, version=1, count=256)
        font, *_ = monobit.load(psf_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    # FZX

    def test_import_fzx(self):
        """Test importing fzx files."""
        font, *_ = monobit.load(self.font_path / '4x6.fzx')
        self.assertEqual(len(font.glyphs), 191)

    def test_export_fzx(self):
        """Test exporting fzx files."""
        fzx_file = self.temp_path / '4x6.fzx'
        monobit.save(self.fixed4x6, fzx_file)
        # read back
        font, *_ = monobit.load(fzx_file)
        self.assertEqual(len(font.glyphs), 191)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # DEC DRCS

    def test_import_dec_drcs(self):
        """Test importing dec-drcs files."""
        font, *_ = monobit.load(self.font_path / '6x13.dec')
        self.assertEqual(len(font.glyphs), 94)

    def test_export_dec_drcs(self):
        """Test exporting dec-drcs files."""
        dec_file = self.temp_path / '8x16.dec'
        monobit.save(self.fixed8x16, dec_file, format='dec')
        font, *_ = monobit.load(dec_file)
        self.assertEqual(len(font.glyphs), 94)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    # yaff

    def test_import_yaff(self):
        """Test importing yaff files"""
        self.assertEqual(len(self.fixed4x6.glyphs), 919)

    def test_export_yaff(self):
        """Test exporting yaff files"""
        yaff_file = self.temp_path / '4x6.yaff'
        monobit.save(self.fixed4x6, yaff_file)
        font, *_ = monobit.load(yaff_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Raw binary

    def test_import_raw(self):
        """Test importing raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6.raw', cell=(4, 6))
        self.assertEqual(len(font.glyphs), 919)

    def test_export_raw(self):
        """Test exporting raw binary files."""
        fnt_file = self.temp_path / '4x6.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw')
        font, *_ = monobit.load(fnt_file, cell=(4, 6), first_codepoint=31)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_raw_wide(self):
        """Test exporting raw binary files with wiide strike."""
        fnt_file = self.temp_path / '4x6.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw', strike_count=256)
        font, *_ = monobit.load(
            fnt_file, format='raw', cell=(4, 6), first_codepoint=31,
            strike_count=256, count=919
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_raw_bitaligned(self):
        """Test importing bit-aligned raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6-bitaligned.raw', cell=(4, 6), align='bit')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_raw_bitaligned(self):
        """Test exporting raw binary files with wiide strike."""
        fnt_file = self.temp_path / '4x6-bit.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw', align='bit')
        font, *_ = monobit.load(
            fnt_file, format='raw', cell=(4, 6), first_codepoint=31, align='bit'
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_raw_inverted(self):
        """Test importing inverted raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6-inverted.raw', cell=(4, 6), ink=0)
        self.assertEqual(len(font.glyphs), 919)

    def test_export_raw_inverted(self):
        """Test exporting raw binary files with wiide strike."""
        fnt_file = self.temp_path / '4x6-inv.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw', ink=0)
        font, *_ = monobit.load(
            fnt_file, format='raw', cell=(4, 6), first_codepoint=31, ink=0
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_raw_msb_right(self):
        """Test importing raw binary files with most significant bit right."""
        font, *_ = monobit.load(self.font_path / '4x6-bitaligned.raw', cell=(4, 6), align='bit')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_raw_msb_right(self):
        """Test exporting raw binary files with most significant bit right."""
        fnt_file = self.temp_path / '4x6-msbr.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw', msb='r')
        font, *_ = monobit.load(
            fnt_file, format='raw', cell=(4, 6), first_codepoint=31, msb='r'
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


    # PDF chart

    def test_export_pdf(self):
        """Test exporting pdf files."""
        pdf_file = self.temp_path / '4x6.pdf'
        monobit.save(self.fixed4x6, pdf_file)
        self.assertTrue(os.path.getsize(pdf_file) > 0)

    # BMFont

    def test_import_bmf(self):
        """Test importing bmfont files."""
        base_path = self.font_path / '6x13.bmf'
        font, *_ = monobit.load(base_path / '6x13-text.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load(base_path / '6x13-xml.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load(base_path / '6x13-json.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load(base_path / '6x13-8bit.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load(base_path / '6x13-32bit-packed.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load(base_path / '6x13-32bit-nonpacked.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        font, *_ = monobit.load(base_path / '6x13-binary.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)

    def test_export_bmf_text(self):
        """Test exporting bmfont files with text descriptor."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(self.fixed4x6, fnt_file, format='bmfont')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_bmf_json(self):
        """Test exporting bmfont files with json descriptor."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(
            self.fixed4x6, fnt_file,
            format='bmfont', descriptor='json',
        )
        font, *_ = monobit.load(fnt_file, format='bmfont')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_bmf_xml(self):
        """Test exporting bmfont files with xml descriptor."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(
            self.fixed4x6, fnt_file,
            format='bmfont', descriptor='xml',
        )
        font, *_ = monobit.load(fnt_file, format='bmfont')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_bmf_binary(self):
        """Test exporting bmfont files with binary descriptor."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(
            self.fixed4x6, fnt_file,
            format='bmfont', descriptor='binary',
        )
        font, *_ = monobit.load(fnt_file, format='bmfont')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Image

    def test_import_png(self):
        """Test importing image files."""
        font, *_ = monobit.load(self.font_path / '4x6.png', cell=(4, 6), count=919, padding=(0,0))
        self.assertEqual(len(font.glyphs), 919)

    def test_export_png(self):
        """Test exporting image files."""
        file = self.temp_path / '4x6.png'
        monobit.save(self.fixed4x6, file, codepoint_range=range(256))
        font, *_ = monobit.load(file, cell=(4, 6))
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_imageset(self):
        """Test importing imageset directories."""
        font, *_ = monobit.load(self.font_path / '4x6.imageset', format='imageset')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_imageset(self):
        """Test exporting imageset directories."""
        dir = self.temp_path / '4x6'
        monobit.save(self.fixed4x6, dir, format='imageset')
        font, *_ = monobit.load(dir, format='imageset')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_pilfont(self):
        """Test importing PILfont files."""
        font, *_ = monobit.load(self.font_path / '4x6.pil')
        self.assertEqual(len(font.glyphs), 192)

    def test_export_pilfont(self):
        """Test exporting PILfont files."""
        file = self.temp_path / '4x6.pil'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_sfont(self):
        """Test exporting SFont files."""
        file = self.temp_path / '4x6.sfont'
        monobit.save(self.fixed4x6, file, format='sfont')
        font, *_ = monobit.load(file, format='sfont')
        self.assertEqual(len(font.glyphs), 93)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


    # CPI

    def test_import_cpi_font(self):
        """Test importing CPI (FONT) files."""
        fnt_file = self.font_path / '8x16-font.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)

    def test_export_cpi_font(self):
        """Test exporting CPI (FONT) files"""
        fnt_file = self.temp_path / '8x16.cpi'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, version='FONT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_cpi_fontnt(self):
        """Test importing CPI (FONT.NT) files"""
        fnt_file = self.font_path / '8x16-fontnt.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)

    def test_export_cpi_fontnt(self):
        """Test exporting CPI (FONT.NT) files"""
        fnt_file = self.temp_path / '8x16.cpi'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, version='FONT.NT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_cpi_drfont(self):
        """Test importing CPI (DRFONT) files"""
        fnt_file = self.font_path / '8x16-drfont.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)

    def test_export_cpi_drfont(self):
        """Test exporting CPI (DRFONT) files"""
        fnt_file = self.temp_path / '8x16.cpi'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, version='DRFONT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_cp(self):
        """Test importing kbd CP files"""
        fnt_file = self.font_path / '8x16.cp'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)

    def test_export_cp(self):
        """Test exporting kbd CP files"""
        fnt_file = self.temp_path / '8x16.cp'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, format='kbd')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_export_cp_nt(self):
        """Test exporting bare FONT.NT codepage."""
        fnt_file = self.temp_path / '8x16.cp'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, format='kbd', version='FONT.NT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_export_cp_drfont(self):
        """Test exporting bare DRFONT codepage."""
        fnt_file = self.temp_path / '8x16.cp'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, format='kbd', version='DRFONT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    # Figlet

    def test_import_flf(self):
        """Test importing flf files."""
        font, *_ = monobit.load(self.font_path / '4x6.flf')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_flf(self):
        """Test exporting flf files."""
        file = self.temp_path / '4x6.flf'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Apple

    def test_import_dfont(self):
        """Test importing dfont files."""
        font, *_ = monobit.load(self.font_path / '4x6.dfont')
        # only 195 glyphs in the font as it's in mac-roman encoding now
        self.assertEqual(len(font.glyphs), 195)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_dfont(self):
        """Test exporting dfont files with NFNT resource."""
        file = self.temp_path / '4x6.dfont'
        monobit.save(self.fixed4x6, file, resource_type='NFNT')
        font, *_ = monobit.load(file)
        # mac-roman only, plus missing glyph
        self.assertEqual(len(font.glyphs), 220)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_sbit(self):
        """Test exporting dfont files with bitmap sfnt resource."""
        file = self.temp_path / '4x6.dfont'
        monobit.save(self.fixed4x6, file, resource_type='sfnt')
        font, *_ = monobit.load(file)
        # 920 as missing glyph is added
        self.assertEqual(len(font.glyphs), 920)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_iigs(self):
        """Test importing Apple IIgs font files."""
        font, *_ = monobit.load(self.font_path / '4x6.iigs', format='iigs')
        # only 220 glyphs in the font as it's in mac-roman encoding now
        self.assertEqual(len(font.glyphs), 220)

    def test_export_iigs(self):
        """Test exporting Apple IIgs font files."""
        file = self.temp_path / '4x6.iigs'
        monobit.save(self.fixed4x6, file, format='iigs')
        font, *_ = monobit.load(file, format='iigs')
        self.assertEqual(len(font.glyphs), 220)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_iigs_v15(self):
        """Test exporting Apple IIgs v1.5 font files."""
        file = self.temp_path / '4x6.iigs'
        monobit.save(self.fixed4x6, file, format='iigs', version=0x105)
        font, *_ = monobit.load(file, format='iigs')
        self.assertEqual(len(font.glyphs), 220)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_mgtk(self):
        """Testing importing Apple II MouseGraphics ToolKit font files."""
        font, *_ = monobit.load(self.font_path / '4x6.mgtk', format='mgtk')
        self.assertEqual(len(font.glyphs), 128)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Bare NFNT
    lisafonts = 'https://github.com/azumanga/apple-lisa/raw/main/LISA_OS/FONTS/'

    def test_import_bare_nfnt(self):
        """Test importing bare NFNT files."""
        file = ensure_asset(self.lisafonts, 'TILE7R20S.F')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 193)

    def test_export_bare_nfnt(self):
        """Test exporting bare NFNT files."""
        file = self.temp_path / '4x6.nfnt'
        monobit.save(self.fixed4x6, file, format='nfnt')
        font, *_ = monobit.load(file, format='nfnt')
        self.assertEqual(len(font.glyphs), 220)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


    # Amiga

    def test_import_amiga(self):
        """Test importing amiga font files."""
        font, *_ = monobit.load(self.font_path / 'wbfont.amiga' / 'wbfont_prop.font')
        self.assertEqual(len(font.glyphs), 225)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
..@@@..
..@@@..
.@@.@@.
.@@.@@.
@@@@@@@
@@...@@
@@...@@
""")

    # GDOS

    def test_import_gdos(self):
        """Test importing uncompressed gdos font file."""
        font, *_ = monobit.load(
            self.font_path / 'gdos' / 'L2UNVB18.FNT', format='gdos'
        )
        self.assertEqual(len(font.glyphs), 252)

    def test_import_gdos_compressed(self):
        """Test importing compressed, chained gdos font file."""
        font, *_ = monobit.load(
            self.font_path / 'gdos' / 'AI360GVP.VGA', format='gdos'
        )
        self.assertEqual(len(font.glyphs), 194)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
.................@@.................
.................@@@................
.................@@@................
................@@@@................
................@@@@@...............
...............@@@@@@...............
...............@@@@@@@..............
..............@@.@@@@@..............
..............@@..@@@@@.............
.............@@...@@@@@.............
.............@@...@@@@@@............
............@@.....@@@@@............
............@@.....@@@@@............
...........@@.......@@@@@...........
...........@@.......@@@@@...........
..........@@@........@@@@@..........
..........@@.........@@@@@..........
.........@@@.........@@@@@@.........
.........@@...........@@@@@.........
.........@@...........@@@@@@........
........@@@@@@@@@@@@@@@@@@@@........
........@@@@@@@@@@@@@@@@@@@@........
.......@@...............@@@@@.......
.......@@...............@@@@@.......
......@@@...............@@@@@@......
......@@.................@@@@@......
.....@@@.................@@@@@@.....
.....@@...................@@@@@.....
....@@@...................@@@@@@....
....@@@...................@@@@@@....
...@@@@...................@@@@@@@...
..@@@@@@.................@@@@@@@@@..
@@@@@@@@@@.............@@@@@@@@@@@@@
""")

    def test_export_gdos(self):
        """Test exporting uncompressed gdos files."""
        file = self.temp_path / '4x6.gft'
        monobit.save(self.fixed4x6, file, format='gdos')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # pcl

    def test_import_hppcl(self):
        """Test importing PCL files."""
        fnt_file = self.font_path / '4x6.sfp'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_hppcl(self):
        """Test exporting PCL files."""
        fnt_file = self.temp_path / '4x6.sft'
        monobit.save(self.fixed4x6, fnt_file, format='hppcl')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


    def test_export_hppcl_landscape(self):
        """Test exporting PCL files in landscape orientation."""
        fnt_file = self.temp_path / '4x6.sft'
        monobit.save(self.fixed4x6, fnt_file, format='hppcl', orientation='landscape')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # vfont

    def test_import_vfont_le(self):
        """Test importing little-endian vfont file."""
        font, *_ = monobit.load(
            self.font_path / '4x6.vfontle',
            first_codepoint=0x1f
        )
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_vfont_be(self):
        """Test importing big-endian vfont file."""
        font, *_ = monobit.load(
            self.font_path / '4x6.vfontbe',
            first_codepoint=0x1f
        )
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_vfont(self):
        """Test exporting vfont files."""
        file = self.temp_path / '4x6.vfont'
        monobit.save(self.fixed4x6, file, format='vfont')
        font, *_ = monobit.load(file)
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # fontx

    def test_import_fontx_sbcs(self):
        """Test importing single-page fontx file."""
        font, *_ = monobit.load(
            self.font_path / '8x16-fontx-sbcs.fnt',
        )
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_fontx_dbcs(self):
        """Test importing multi-page fontx file."""
        font, *_ = monobit.load(
            self.font_path / '8x16-fontx.fnt',
        )
        # including 1000 blanks due to (our way of dealing with) contiguous-block structure
        self.assertEqual(len(font.glyphs), 1919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_export_fontx(self):
        """Test exporting fontx files."""
        file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, file, format='fontx')
        font, *_ = monobit.load(file)
        # including 1032 blanks due to (our way of dealing with) contiguous-block structure
        # note 4x6 has a glyph at 0x0
        self.assertEqual(len(font.glyphs), 1951)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Daisy-Dot

    def test_import_daisy2(self):
        """Test importing daisy-dot II file."""
        font, *_ = monobit.load(
            self.font_path / 'daisy' / 'times.nlq',
        )
        self.assertEqual(len(font.glyphs), 91)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
.....@.....
.....@.....
....@@@....
....@@@....
...@..@....
...@..@@...
...@..@@...
..@....@...
..@@@@@@@..
..@....@@..
.@......@@.
.@......@@.
@@@....@@@@
""")

    def test_import_daisy3(self):
        """Test importing daisy-dot III file."""
        font, *_ = monobit.load(
            self.font_path / 'daisy' / 'swiss.nlq',
        )
        # the space glyph should be generated
        self.assertEqual(len(font.glyphs), 91)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
.......@.......
.......@.......
.......@.......
......@.@......
......@.@......
.....@...@.....
.....@...@.....
....@.....@....
....@.....@....
...@.......@...
...@.......@...
..@@@@@@@@@@@..
..@.........@..
..@.........@..
.@...........@.
.@...........@.
@.............@
@.............@
""")

    def test_import_daisy_mag(self):
        """Test importing daisy-dot III Magnified files."""
        font, *_ = monobit.load(
            self.font_path / 'daisy' / 'big1.nlq',
        )
        # the space glyph should be generated
        self.assertEqual(len(font.glyphs), 91)

    # BBC

    def test_import_bbc(self):
        """Test importing bbc files."""
        font, *_ = monobit.load(self.font_path / '8x8.bbc')
        self.assertEqual(len(font.glyphs), 224)

    def test_export_bbc(self):
        """Test exporting bbc files."""
        file = self.temp_path / '4x6.bbc'
        font = self.fixed4x6.expand(right=4, bottom=2, adjust_metrics=False)
        monobit.save(font, file, format='bbc')
        font, *_ = monobit.load(file)
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self.assertEqual(len(font.glyphs), 191)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # HBF

    def test_import_hbf(self):
        """Test importing HBF files."""
        font, *_ = monobit.load(self.font_path / '8x16.hbf')
        self.assertEqual(len(font.glyphs), 727)

    def test_export_hbf(self):
        """Test exporting HBF files."""
        file = self.temp_path / '4x6.hbf'
        font = self.fixed4x6
        monobit.save(font, file, format='hbf')
        font, *_ = monobit.load(file)
        # excludes 192 sbcs codepoints
        self.assertEqual(len(font.glyphs), 727)
        glyph_0x100 = """\
@@@
.@.
@.@
@@@
@.@
"""
        self.assertEqual(font.get_glyph(b'\1\0').reduce().as_text(), glyph_0x100)

    # XBIN

    def test_import_xbin(self):
        """Test importing XBIN files."""
        font, *_ = monobit.load(self.font_path / '8X16.XB')
        self.assertEqual(len(font.glyphs), 256)

    def test_export_xbin(self):
        """Test exporting XBIN files."""
        fnt_file = self.temp_path / '8x16.xb'
        monobit.save(self.fixed8x16, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    # Optiks PCR

    telparia = 'https://telparia.com/fileFormatSamples/font/pcrFont/'

    def test_optiks(self):
        """Test importing Optiks PCR files."""
        file = ensure_asset(self.telparia, 'FONT1.PCR')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 256)

    def test_export_optiks(self):
        """Test exporting Optiks PCR files."""
        file = self.temp_path / '4x6.pcr'
        font = self.fixed4x6.expand(right=4, bottom=2, adjust_metrics=False)
        monobit.save(font, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Write On!

    def test_import_writeon(self):
        """Test importing Write On! files."""
        font, *_ = monobit.load(self.font_path / '4x6.wof')
        self.assertEqual(len(font.glyphs), 919)

    def test_export_writeon(self):
        """Test exporting Write On! files."""
        fnt_file = self.temp_path / '8x16.wof'
        monobit.save(self.fixed4x6, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 128)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Wyse

    def test_import_wyse(self):
        """Test importing Wyse-60 files."""
        font, *_ = monobit.load(self.font_path / '4x6.wyse', format='wyse')
        # only encoding codepoints < 0x0400 (4 banks)
        self.assertEqual(len(font.glyphs), 512)

    def test_export_wyse(self):
        """Test exporting Wyse-60 files."""
        fnt_file = self.temp_path / '8x16.wyse'
        # only encoding codepoints < 0x0400 (4 banks)
        # explicitly remove to avoid noisy warnings
        font = self.fixed4x6.subset(codepoints=range(0x400))
        monobit.save(font, fnt_file, format='wyse')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 105)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # 64c

    def test_export_64c(self):
        """Test exporting 64c files."""
        fnt_file = self.temp_path / '8x8.64c'
        font = self.fixed4x6.expand(right=4, bottom=2, adjust_metrics=False)
        monobit.save(font, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 919)

    # +3DOS

    def test_export_plus3dos(self):
        """Test exporting plus3dos files."""
        fnt_file = self.temp_path / '8x8.p3d'
        font = self.fixed4x6.expand(right=4, bottom=2, adjust_metrics=False)
        monobit.save(font, fnt_file, format='plus3dos')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 96)

    # GRASP / PCPaint old format

    def test_export_grasp(self):
        """Test exporting GRASP files."""
        fnt_file = self.temp_path / '4x6.set'
        monobit.save(self.fixed4x6, fnt_file, format='grasp')
        font, *_ = monobit.load(fnt_file, format='grasp')
        self.assertEqual(len(font.glyphs), 255)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # wsfont

    def test_import_wsfont(self):
        """Test importing wsfont files."""
        font, *_ = monobit.load(self.font_path / 'ter-i12n.wsf')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), """\
.@@@.
@...@
@...@
@...@
@@@@@
@...@
@...@
@...@
""")

    def test_export_wsfont(self):
        """Test exporting wsfont files."""
        fnt_file = self.temp_path / '4x6.wsf'
        monobit.save(self.fixed4x6, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # freebsd vtfont

    def test_import_vfnt2(self):
        """Test importing freebsd vtfont files."""
        font, *_ = monobit.load(self.font_path / 'ter-u28.fnt')
        self.assertEqual(len(font.glyphs), 1185)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), """\
..@@@@@@@..
.@@.....@@.
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@@@@@@@@@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
""")

    def test_export_vfnt2(self):
        """Test exporting freebsd vt font files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='vfnt2')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # COM loaders

    def test_import_frapt(self):
        """Test importing Fontraptor files."""
        font, *_ = monobit.load(self.font_path / '8X16-FRA.COM')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_frapt_tsr(self):
        """Test importing Fontraptor TSR files."""
        font, *_ = monobit.load(self.font_path / '8X16-TSR.COM')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_mania(self):
        """Test importing Font Mania files."""
        font, *_ = monobit.load(self.font_path / '8X16-REX.COM')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_fontedit(self):
        """Test importing FONTEDIT files."""
        font, *_ = monobit.load(self.font_path / '8X16-FE.COM')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_psfcom(self):
        """Test importing PSF2AMS files."""
        font, *_ = monobit.load(
            self.font_path / '4x6-ams.com',
            first_codepoint=0x1f
        )
        self.assertEqual(len(font.glyphs), 512)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    udg = 'https://www.seasip.info/Unix/PSF/Amstrad/UDG/'

    def test_import_udgcom(self):
        """Test importing UDG .COM files."""
        file = ensure_asset(self.udg, 'udg.zip')
        font, *_ = monobit.load(file / 'charset1.com')
        self.assertEqual(len(font.glyphs), 256)

    letafont = 'https://www.seasip.info/Unix/PSF/Amstrad/Letafont/'

    def test_import_letafont(self):
        """Test importing LETAFONT .COM files."""
        font, *_ = monobit.load(self.font_path / '8x8-letafont.com')
        self.assertEqual(len(font.glyphs), 256)

    # TeX PKFONT

    def test_import_pkfont(self):
        """Test importing PKFONT files."""
        font, *_ = monobit.load(self.font_path / 'cmbx10.120pk')
        self.assertEqual(len(font.glyphs), 128)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
.....@.....
....@@@....
....@@@....
....@@@....
...@.@@@...
...@.@@@...
...@.@@@...
..@...@@@..
..@@@@@@@..
.@....@@@@.
@@@@.@@@@@@
""")

    # sfnt

    def test_import_fonttosfnt(self):
        """Test importing sfnt bitmap files produced by fonttosfnt."""
        font, *_ = monobit.load(self.font_path / '4x6.ttf')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fontforge(self):
        """Test importing sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.otb')
        self.assertEqual(len(font.glyphs), 922)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fontforge_fakems(self):
        """Test importing 'fake MS' sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.ffms.ttf')
        self.assertEqual(len(font.glyphs), 922)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fontforge_dfont(self):
        """Test importing dfont-wrapped sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.sfnt.dfont')
        self.assertEqual(len(font.glyphs), 922)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_sfnt_otb(self):
        """Test exporting otb files."""
        file = self.temp_path / '4x6.otb'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        # 920 as .notdef is added
        self.assertEqual(len(font.glyphs), 920)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_sfnt_apple_sbit(self):
        """Test exporting apple-style sbit files (bare, not in dfont container)."""
        file = self.temp_path / '4x6.ttf'
        monobit.save(self.fixed4x6, file, version='apple')
        font, *_ = monobit.load(file)
        # 920 as .notdef is added
        self.assertEqual(len(font.glyphs), 920)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_sfnt_ttc(self):
        """Test exporting ttc files."""
        file = self.temp_path / '4x6.ttc'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        # 920 as .notdef is added
        self.assertEqual(len(font.glyphs), 920)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # geos

    def test_import_geos(self):
        """Test importing GEOS fonts."""
        font, *_ = monobit.load(self.font_path / 'SHILLING.cvt.gz', extract_del=True)
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(font.get_glyph(b'\x2a').reduce().as_text(), """\
.@@@.
.@@@.
.@@@.
.@@@.
.@@@.
@@@@@
.@@@.
..@..
""")

    def test_export_vlir(self):
        """Test exporting GEOS VLIR resources."""
        fnt_file = self.temp_path / '4x6.vlir'
        monobit.save(self.fixed4x6, fnt_file, format='vlir')
        font, *_ = monobit.load(fnt_file, format='vlir', extract_del=True)
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_geos(self):
        """Test exporting GEOS convert files."""
        fnt_file = self.temp_path / '4x6.cvt'
        monobit.save(self.fixed4x6, fnt_file, format='geos')
        font, *_ = monobit.load(fnt_file, format='geos', extract_del=True)
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_geos_mega(self):
        """Test exporting GEOS convert files inn mega format."""
        fnt_file = self.temp_path / '4x6.cvt'
        monobit.save(self.fixed4x6, fnt_file, format='geos', mega=True)
        font, *_ = monobit.load(fnt_file, format='geos', extract_del=True)
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # pc/geos


    bison_fnt = 'https://github.com/bluewaysw/pcgeos/raw/master/FontData/'

    def test_import_pcgeos(self):
        """Test importing PC/GEOS files."""
        file = ensure_asset(self.bison_fnt, 'Bison.fnt')
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 4)
        self.assertEqual(len(fonts[0].glyphs), 251)
        self.assertEqual(fonts[0].get_glyph(b'A').reduce().as_text(), """\
.@@@.
@...@
@...@
@@@@@
@...@
@...@
@...@
""")

    def test_export_pcgeos(self):
        """Test exporting PC/GEOS files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='pcgeos')
        font, *_ = monobit.load(fnt_file, format='pcgeos')
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # palm

    def test_import_palm(self):
        """Test importing Palm OS fonts."""
        font, *_ = monobit.load(self.font_path / 'Alpha-2B.pdb')
        self.assertEqual(len(font.glyphs), 230)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
...@@...
...@@...
..@@@@..
..@@@@..
..@..@..
.@@..@@.
.@@..@@.
.@@@@@@.
@@....@@
@@....@@
"""
)

    # OS/2

    def test_import_os2_lx(self):
        """Test importing OS/2 fonts (LX container)."""
        font, *_ = monobit.load(self.font_path / 'WARPSANS.FON')
        self.assertEqual(len(font.glyphs), 950)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), """\
...@...
...@...
..@.@..
..@.@..
.@...@.
.@...@.
.@@@@@.
@.....@
@.....@
@.....@
""")

    bgafon = 'http://discmaster.textfiles.com/file/21050/NOVEMBER.bin/nov95/nov9/nov9022.zip/whbdlt1.zip/BGAFON.ZIP/'

    def test_import_os2_ne(self):
        """Test importing OS/2 NE FON files."""
        file = ensure_asset(self.bgafon, 'sysmono.fon')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 382)

    # The Print Shop

    printshop = 'https://archive.org/download/msdos_broderbund_print_shop/printshop.zip/'

    def test_import_printshop(self):
        """Test importing The Print Shop for DOS files."""
        file = ensure_asset(self.printshop, 'FONT8.PSF')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 95)

    # DosStart

    dosstart = 'https://archive.org/download/dosstart-19b/dosstart.zip/'

    def test_import_dosstart_bitmap(self):
        """Test importing DosStart bitmap files."""
        file = ensure_asset(self.dosstart, 'COUR.DSF')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 95)

    def test_export_dosstart_bitmap(self):
        """Test exporting DosStart bitmap files."""
        fnt_file = self.temp_path / '4x6.dsf'
        monobit.save(self.fixed4x6, fnt_file, format='dosstart')
        font, *_ = monobit.load(fnt_file, format='dosstart')
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # bepf

    ohlfs = 'https://github.com/AlexHorovitz/Ohlfs-font-to-ttf-conversion/raw/master/Ohlfs.font/'

    def test_import_bepf(self):
        """Test importing Adobe prebuilt files."""
        file = ensure_asset(self.ohlfs, 'Ohlfs.bepf')
        font, *_ = monobit.load(file, format='prebuilt')
        self.assertEqual(len(font.glyphs), 228)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
.@@.
@..@
@..@
@..@
@@@@
@..@
@..@
""")

    # Xerox Alto

    alto = 'https://xeroxalto.computerhistory.org/_cd8_/alto/'

    def test_import_al(self):
        """Test importing Alto .AL files."""
        file = ensure_asset(self.alto, 'sysfont.al!2')
        font, *_ = monobit.load(file, format='alto')
        self.assertEqual(len(font.glyphs), 95)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
....@....
....@....
...@.@...
...@.@...
..@...@..
..@@@@@..
.@.....@.
@@@...@@@
""")


    alto2 = 'https://xeroxalto.computerhistory.org/Indigo/AltoFonts/'

    def test_import_ks(self):
        """Test importing Alto .KS files."""
        file = ensure_asset(self.alto2, 'Elite10.ks!1')
        font, *_ = monobit.load(file, format='bitblt')
        self.assertEqual(len(font.glyphs), 88)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
...@...
..@.@..
..@.@..
.@...@.
.@...@.
.@@@@@.
.@...@.
@@...@@
""")

    def test_import_strike(self):
        """Test importing Alto .STRIKE files."""
        file = ensure_asset(self.alto2, 'Elite10.strike!2')
        font, *_ = monobit.load(file, format='bitblt')
        self.assertEqual(len(font.glyphs), 88)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
...@...
..@.@..
..@.@..
.@...@.
.@...@.
.@@@@@.
.@...@.
@@...@@
""")

    alto3 = 'https://xeroxalto.computerhistory.org/Indigo/PressFonts/'

    def test_import_prepress(self):
        """Test importing Xerox PrePress .AC files."""
        file = ensure_asset(self.alto3, 'TESTFONT12.AC!1')
        font, *_ = monobit.load(file, format='prepress')
        self.assertEqual(len(font.glyphs), 75)
        # I'd check a glyph but they are *huge*


    # pcf

    def test_import_pcf(self):
        """Test importing PCF files"""
        pcf_files = (
            # big-endian bytes, big-endian bits
            '4x6_Bbu1p1.pcf', '4x6_Bbu2p2.pcf', '4x6_Bbu4p4.pcf',
            # big-endian bytes, little-endian bits
            '4x6_Blu1p1.pcf', '4x6_Blu1p2.pcf', '4x6_Blu1p4.pcf',
            '4x6_Blu2p2.pcf', '4x6_Blu4p2.pcf', '4x6_Blu4p4.pcf',
            # little-endian bytes, big-endian bits
            '4x6_Lbu1p1.pcf', '4x6_Lbu1p2.pcf', '4x6_Lbu1p4.pcf',
            '4x6_Lbu2p1.pcf', '4x6_Lbu2p2.pcf', '4x6_Lbu4p2.pcf',
            '4x6_Lbu4p4.pcf',
            # little-endian bytes, little-endian bits
            '4x6_Llu1p1.pcf', '4x6_Llu2p2.pcf', '4x6_Llu4p4.pcf',
        )
        # files generated by bdftopcf that don't work:
        # - with -p 8, which don't seem to get the correct
        # - where the bitmap size is not a multiple of the scan unit
        # both appear to be different bugs in bdftopcf
        for pcf_file in pcf_files:
            file = self.font_path / 'pcf' / pcf_file
            font, *_ = monobit.load(file)
            self.assertEqual(len(font.glyphs), 919)
            self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_pcf(self):
        """Test exporting PCF files"""
        for byte_order in ('big', 'little'):
            for bit_order in ('big', 'little'):
                for scan_unit in (1, 2, 4, 8):
                    for padding_bytes in (1, 2, 4, 8):
                        file = self.temp_path / f'4x6_{byte_order[0].upper()}{bit_order[0]}u{scan_unit}p{padding_bytes}.pcf'
                        monobit.save(
                            self.fixed4x6, file, format='pcf',
                            byte_order=byte_order, bit_order=bit_order,
                            scan_unit=scan_unit, padding_bytes=padding_bytes,
                            overwrite=True
                        )
                        font, *_ = monobit.load(file)
                        self.assertEqual(len(font.glyphs), 919)
                        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)


    # EDWIN

    def test_import_edwin(self):
        """Test importing EDWIN files."""
        font, *_ = monobit.load(self.font_path / '4x6.edwin.fnt', format='edwin')
        self.assertEqual(len(font.glyphs), 127)

    def test_export_edwin(self):
        """Test exporting EDWIN files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='edwin')
        font, *_ = monobit.load(fnt_file, format='edwin')
        self.assertEqual(len(font.glyphs), 127)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


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
