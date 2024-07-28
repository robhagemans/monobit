"""
monobit test suite
export tests
"""

import os
import unittest

import monobit
from .base import BaseTester, ensure_asset, assert_text_eq


class TestExport(BaseTester):
    """Test monobit export."""

    # BDF

    def test_export_bdf(self):
        """Test exporting bdf files."""
        file = self.temp_path / '4x6.bdf'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Windows

    def test_export_fon(self):
        """Test exporting fon files."""
        fon_file = self.temp_path / '4x6.fon'
        monobit.save(self.fixed4x6, fon_file, format='mzfon')
        # read back
        font, *_ = monobit.load(fon_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

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

    # Unifont

    def test_export_hex(self):
        """Test exporting hex files."""
        hex_file = self.temp_path / '8x16.hex'
        monobit.save(self.fixed8x16, hex_file)
        font, *_ = monobit.load(hex_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

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

    def test_export_psf2txt(self):
        """Test exporting psf2txt files."""
        draw_file = self.temp_path / '4x6.txt'
        monobit.save(self.fixed4x6, draw_file, format='psf2txt')
        font, *_ = monobit.load(draw_file, format='psf2txt')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_clt(self):
        """Test exporting consolet files."""
        draw_loc = self.temp_path / '4x6'
        monobit.save(self.fixed4x6, draw_loc, format='consoleet')
        font, *_ = monobit.load(draw_loc, format='consoleet')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_mkwinfont(self):
        """Test exporting mkwinfont .fd files."""
        draw_file = self.temp_path / '4x6.fd'
        monobit.save(self.fixed4x6, draw_file, format='mkwinfont')
        font, *_ = monobit.load(draw_file, format='mkwinfont')
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # PSF

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

    def test_export_fzx(self):
        """Test exporting fzx files."""
        fzx_file = self.temp_path / '4x6.fzx'
        monobit.save(self.fixed4x6, fzx_file)
        # read back
        font, *_ = monobit.load(fzx_file)
        self.assertEqual(len(font.glyphs), 191)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # DEC DRCS

    def test_export_dec_drcs(self):
        """Test exporting dec-drcs files."""
        dec_file = self.temp_path / '8x16.dec'
        monobit.save(self.fixed8x16, dec_file, format='dec')
        font, *_ = monobit.load(dec_file)
        self.assertEqual(len(font.glyphs), 94)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    # yaff

    def test_export_yaff(self):
        """Test exporting yaff files"""
        yaff_file = self.temp_path / '4x6.yaff'
        monobit.save(self.fixed4x6, yaff_file)
        font, *_ = monobit.load(yaff_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Raw binary

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

    def test_export_raw_bitaligned(self):
        """Test exporting raw binary files with wiide strike."""
        fnt_file = self.temp_path / '4x6-bit.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw', align='bit')
        font, *_ = monobit.load(
            fnt_file, format='raw', cell=(4, 6), first_codepoint=31, align='bit'
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_raw_inverted(self):
        """Test exporting raw binary files with wiide strike."""
        fnt_file = self.temp_path / '4x6-inv.raw'
        monobit.save(self.fixed4x6, fnt_file, format='raw', ink=0)
        font, *_ = monobit.load(
            fnt_file, format='raw', cell=(4, 6), first_codepoint=31, ink=0
        )
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

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

    def test_export_png(self):
        """Test exporting image files."""
        file = self.temp_path / '4x6.png'
        monobit.save(self.fixed4x6, file, codepoint_range=range(256))
        font, *_ = monobit.load(file, cell=(4, 6))
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_export_imageset(self):
        """Test exporting imageset directories."""
        dir = self.temp_path / '4x6'
        monobit.save(self.fixed4x6, dir, format='imageset')
        font, *_ = monobit.load(dir, format='imageset')
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

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

    def test_export_cpi_font(self):
        """Test exporting CPI (FONT) files"""
        fnt_file = self.temp_path / '8x16.cpi'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, version='FONT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_export_cpi_fontnt(self):
        """Test exporting CPI (FONT.NT) files"""
        fnt_file = self.temp_path / '8x16.cpi'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, version='FONT.NT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_export_cpi_drfont(self):
        """Test exporting CPI (DRFONT) files"""
        fnt_file = self.temp_path / '8x16.cpi'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, fnt_file, version='DRFONT')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

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

    def test_export_flf(self):
        """Test exporting flf files."""
        file = self.temp_path / '4x6.flf'
        monobit.save(self.fixed4x6, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Apple

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

    # Bare NFNT

    def test_export_bare_nfnt(self):
        """Test exporting bare NFNT files."""
        file = self.temp_path / '4x6.nfnt'
        monobit.save(self.fixed4x6, file, format='nfnt')
        font, *_ = monobit.load(file, format='nfnt')
        self.assertEqual(len(font.glyphs), 220)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # GDOS

    def test_export_gdos(self):
        """Test exporting uncompressed gdos files."""
        file = self.temp_path / '4x6.gft'
        monobit.save(self.fixed4x6, file, format='gdos')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # pcl

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

    def test_export_vfont(self):
        """Test exporting vfont files."""
        file = self.temp_path / '4x6.vfont'
        monobit.save(self.fixed4x6, file, format='vfont')
        font, *_ = monobit.load(file)
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # fontx

    def test_export_fontx(self):
        """Test exporting fontx files."""
        file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, file, format='fontx')
        font, *_ = monobit.load(file)
        # including 1032 blanks due to (our way of dealing with) contiguous-block structure
        # note 4x6 has a glyph at 0x0
        self.assertEqual(len(font.glyphs), 1951)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # BBC

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

    def test_export_xbin(self):
        """Test exporting XBIN files."""
        fnt_file = self.temp_path / '8x16.xb'
        monobit.save(self.fixed8x16, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    # Optiks PCR

    def test_export_optiks(self):
        """Test exporting Optiks PCR files."""
        file = self.temp_path / '4x6.pcr'
        font = self.fixed4x6.expand(right=4, bottom=2, adjust_metrics=False)
        monobit.save(font, file)
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Write On!

    def test_export_writeon(self):
        """Test exporting Write On! files."""
        fnt_file = self.temp_path / '8x16.wof'
        monobit.save(self.fixed4x6, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 128)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Wyse

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

    # adafruit gfxfont

    def test_export_gfxfont(self):
        """Test exporting gfxfont header files."""
        fnt_file = self.temp_path / '4x6.h'
        monobit.save(self.fixed4x6.subset(codepoints=range(256)), fnt_file, format='gfxfont')
        font, *_ = monobit.load(fnt_file, format='gfxfont')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


    # wsfont

    def test_export_wsfont(self):
        """Test exporting wsfont files."""
        fnt_file = self.temp_path / '4x6.wsf'
        monobit.save(self.fixed4x6, fnt_file)
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_export_netbsd(self):
        """Test exporting netbsd files."""
        fnt_file = self.temp_path / '4x6.h'
        monobit.save(self.fixed4x6, fnt_file, format='netbsd')
        font, *_ = monobit.load(fnt_file, format='netbsd')
        self.assertEqual(len(font.glyphs), 256)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # freebsd vtfont

    def test_export_vtfont(self):
        """Test exporting freebsd vt font files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='vtfont')
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 919)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # sfnt

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

    def test_export_pcgeos(self):
        """Test exporting PC/GEOS files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='pcgeos')
        font, *_ = monobit.load(fnt_file, format='pcgeos')
        self.assertEqual(len(font.glyphs), 192)
        self.assertEqual(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # DosStart

    def test_export_dosstart_bitmap(self):
        """Test exporting DosStart bitmap files."""
        fnt_file = self.temp_path / '4x6.dsf'
        monobit.save(self.fixed4x6, fnt_file, format='dosstart')
        font, *_ = monobit.load(fnt_file, format='dosstart')
        self.assertEqual(len(font.glyphs), 96)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # pcf

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

    def test_export_edwin(self):
        """Test exporting EDWIN files."""
        fnt_file = self.temp_path / '4x6.fnt'
        monobit.save(self.fixed4x6, fnt_file, format='edwin')
        font, *_ = monobit.load(fnt_file, format='edwin')
        self.assertEqual(len(font.glyphs), 127)
        self.assertEqual(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)


if __name__ == '__main__':
    unittest.main()
