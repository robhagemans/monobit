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
        monobit.save(self.fixed4x6, fon_file)
        # read back
        font, *_ = monobit.load(fon_file)
        self.assertEqual(len(font.glyphs), 224)
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
        self.assertEqual(len(font.glyphs), 224)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_fnt_v2(self):
        """Test exporting fnt files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='win', version=2)
        # read back
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 224)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_fnt_v3(self):
        """Test exporting fnt files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='win', version=3)
        # read back
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 224)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

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

    def test_export_draw(self):
        """Test exporting draw files."""
        draw_file = self.temp_path / '8x16.draw'
        monobit.save(self.fixed8x16, draw_file)
        font, *_ = monobit.load(draw_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)


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

    def test_export_bmf_text(self):
        """Test exporting bmfont files with text descriptor."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(self.fixed4x6, fnt_file, where=self.temp_path)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_bmf_json(self):
        """Test exporting bmfont files with json descriptor."""
        fnt_file = self.temp_path / '4x6.bmf'
        monobit.save(self.fixed4x6, fnt_file, where=self.temp_path, descriptor='json', overwrite=True)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Source coded binary

    def test_import_c(self):
        """Test importing c source files."""
        font, *_ = monobit.load(
            self.font_path / '4x6.c',
            identifier='char font_Fixed_Medium_6', cell=(4, 6)
        )
        self.assertEqual(len(font.glyphs), 919)

    def test_export_c(self):
        """Test exporting c source files."""
        file = self.temp_path  / '4x6.c'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file, cell=(4, 6), first_codepoint=31)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_py(self):
        """Test exporting Python source files."""
        file = self.temp_path  / '4x6.py'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file, cell=(4, 6), first_codepoint=31)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_json(self):
        """Test exporting JSON source files."""
        file = self.temp_path  / '4x6.json'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file, cell=(4, 6), first_codepoint=31)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Image

    def test_import_png(self):
        """Test importing image files."""
        font, *_ = monobit.load(self.font_path / '4x6.png', cell=(4, 6), count=919)
        self.assertEqual(len(font.glyphs), 919)

    def test_export_png(self):
        """Test exporting image files."""
        file = self.temp_path / '4x6.png'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file, cell=(4, 6), first_codepoint=31)
        # we pick up empty glyphs due to matrix chart structure
        self.assertEqual(len(font.glyphs), 928)
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

    def test_export_cp(self):
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

    def test_import_macbinary(self):
        """Test importing macbinary files."""
        font, *_ = monobit.load(self.font_path / '4x6.bin')
        self.assertEqual(len(font.glyphs), 195)

    def test_import_hexbin(self):
        """Test importing hexbin files."""
        font, *_ = monobit.load(self.font_path / '4x6.hqx')
        self.assertEqual(len(font.glyphs), 195)

    # Amiga

    def test_import_amiga(self):
        """Test importing amiga font files."""
        font, *_ = monobit.load(self.font_path / 'wbfont.amiga' / 'wbfont_prop.font')
        self.assertEqual(len(font.glyphs), 225)

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

    def test_export_gdos(self):
        """Test exporting uncompressed gdos files."""
        file = self.temp_path / '4x6.gft'
        monobit.save(self.fixed4x6, file, format='gdos')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 224)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # vfont

    def test_import_vfont_le(self):
        """Test importing little-endian vfont file."""
        font, *_ = monobit.load(
            self.font_path / '4x6.vfontle',
        )
        self.assertEqual(len(font.glyphs), 256)

    def test_import_vfont_be(self):
        """Test importing big-endian vfont file."""
        font, *_ = monobit.load(
            self.font_path / '4x6.vfontbe',
        )
        self.assertEqual(len(font.glyphs), 256)

    def test_export_vfont(self):
        """Test exporting vfont files."""
        file = self.temp_path / '4x6.vfont'
        monobit.save(self.fixed4x6, file, format='vfont')
        font, *_ = monobit.load(file)
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self.assertEqual(len(font.glyphs), 191)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # fontx

    def test_import_fontx_sbcs(self):
        """Test importing single-page fontx file."""
        font, *_ = monobit.load(
            self.font_path / '8x16-fontx-sbcs.fnt',
        )
        self.assertEqual(len(font.glyphs), 256)

    def test_import_fontx_dbcs(self):
        """Test importing multi-page fontx file."""
        font, *_ = monobit.load(
            self.font_path / '8x16-fontx.fnt',
        )
        # including 1000 blanks due to (our way of dealing with) contiguous-block structure
        self.assertEqual(len(font.glyphs), 1919)

    def test_export_fontx(self):
        """Test exporting fontx files."""
        file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, file, format='fontx')
        font, *_ = monobit.load(file)
        # including 1000 blanks due to (our way of dealing with) contiguous-block structure
        self.assertEqual(len(font.glyphs), 1919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Daisy-Dot

    def test_import_daisy2(self):
        """Test importing daisy-dot II file."""
        font, *_ = monobit.load(
            self.font_path / 'daisy' / 'times.nlq',
        )
        self.assertEqual(len(font.glyphs), 91)

    def test_import_daisy3(self):
        """Test importing daisy-dot III file."""
        font, *_ = monobit.load(
            self.font_path / 'daisy' / 'swiss.nlq',
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

    # COM loaders

    def test_import_frapt(self):
        """Test importing Fontraptor files."""
        font, *_ = monobit.load(self.font_path / '8X16-FRA.COM')
        self.assertEqual(len(font.glyphs), 256)

    def test_import_frapt_tsr(self):
        """Test importing Fontraptor TSR files."""
        font, *_ = monobit.load(self.font_path / '8X16-TSR.COM')
        self.assertEqual(len(font.glyphs), 256)

    def test_import_mania(self):
        """Test importing Font Mania files."""
        font, *_ = monobit.load(self.font_path / '8X16-REX.COM')
        self.assertEqual(len(font.glyphs), 256)

    def test_import_frapt(self):
        """Test importing FONTEDIT files."""
        font, *_ = monobit.load(self.font_path / '8X16-FE.COM')
        self.assertEqual(len(font.glyphs), 256)

    def test_import_psfcom(self):
        """Test importing PSF2AMS files."""
        font, *_ = monobit.load(self.font_path / '4x6-ams.com')
        self.assertEqual(len(font.glyphs), 512)

    # TeX PKFONT

    def test_import_pkfont(self):
        """Test importing PKFONT files."""
        font, *_ = monobit.load(self.font_path / 'cmbx10.120pk')
        self.assertEqual(len(font.glyphs), 128)

    # sfnt

    def test_import_fonttosfnt(self):
        """Test importing sfnt bitmap files produced by fonttosfnt."""
        font, *_ = monobit.load(self.font_path / '4x6.ttf')
        self.assertEqual(len(font.glyphs), 919)

    def test_import_fontforge(self):
        """Test importing sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.otb')
        self.assertEqual(len(font.glyphs), 922)

    def test_import_fontforge_fakems(self):
        """Test importing 'fake MS' sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.ffms.ttf')
        self.assertEqual(len(font.glyphs), 922)

    def test_import_fontforge_dfont(self):
        """Test importing dfont-wrapped sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.sfnt.dfont')
        self.assertEqual(len(font.glyphs), 922)

    # geos

    def test_import_geos(self):
        """Test importing GEOS fonts."""
        font, *_ = monobit.load(self.font_path / 'SHILLING.cvt.gz')
        self.assertEqual(len(font.glyphs), 95)

    # palm

    def test_import_palm(self):
        """Test importing Palm OS fonts."""
        font, *_ = monobit.load(self.font_path / 'Alpha-2B.pdb')
        self.assertEqual(len(font.glyphs), 230)

    # OS/2

    def test_import_os2_lx(self):
        """Test importing OS/2 fonts (LX container)."""
        font, *_ = monobit.load(self.font_path / 'WARPSANS.FON')
        self.assertEqual(len(font.glyphs), 950)

    # stroke formats

    def test_import_hershey(self):
        """Test importing Hershey font in Jim Hurt's format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey-az.jhf')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)

    def test_import_svg(self):
        """Test importing Hershey font in SVG format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.svg')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)

    def test_import_vector_fon(self):
        """Test importing Hershey font in Windows vector format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.fon')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)

    def test_import_vector_yaff(self):
        """Test importing Hershey font in yaff format."""
        font, *_ = monobit.load(self.font_path / 'hershey' / 'hershey.yaff')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)

    def test_export_svg(self):
        """Test exporting Hershey font in SVG format."""
        monobit.save(self.hershey, self.temp_path / 'hershey.svg')
        font, *_ = monobit.load(self.temp_path / 'hershey.svg')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)

    def test_export_vector_fon(self):
        """Test exporting Hershey font in Windows vector format."""
        monobit.save(self.hershey, self.temp_path / 'hershey.fon', vector=True)
        font, *_ = monobit.load(self.temp_path / 'hershey.fon')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)

    def test_export_vector_yaff(self):
        """Test exporting Hershey font in yaff format."""
        monobit.save(self.hershey, self.temp_path / 'hershey.yaff')
        font, *_ = monobit.load(self.temp_path / 'hershey.yaff')
        self.assertEqual(len(font.glyphs), 26)
        self.assertEqual(font.glyphs[0].path, self.hershey_A_path)


if __name__ == '__main__':
    unittest.main()
