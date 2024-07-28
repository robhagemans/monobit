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

    def _export_4x6(self, *, format, label='A', count=919, save_kwargs=(), load_kwargs=()):
        """Test exporting 4x6 font files."""
        file = self.temp_path / f'4x6.{format}'
        monobit.save(self.fixed4x6, file, format=format, **(save_kwargs or {}))
        font, *_ = monobit.load(file, format=format, **(load_kwargs or {}))
        self.assertEqual(len(font.glyphs), count)
        assert_text_eq(font.get_glyph(label).reduce().as_text(), self.fixed4x6_A)

    def _export_8x16(self, *, format, label='A', count=919, save_kwargs=(), load_kwargs=()):
        """Test exporting 8x16 files."""
        file = self.temp_path / f'8x16.{format}'
        monobit.save(self.fixed8x16, file, format=format, **(save_kwargs or {}))
        font, *_ = monobit.load(file, format=format, **(load_kwargs or {}))
        self.assertEqual(len(font.glyphs), count)
        assert_text_eq(font.get_glyph(label).reduce().as_text(), self.fixed8x16_A)

    def _export_8x16_cp437(self, *, format, save_kwargs=(), load_kwargs=()):
        """Test exporting 8x16 files with codepage 437."""
        file = self.temp_path / f'8x16.{format}'
        font = self.fixed8x16.modify(encoding='cp437')
        monobit.save(font, file, format=format, **(save_kwargs or {}))
        font, *_ = monobit.load(file, format=format, **(load_kwargs or {}))
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def _export_8x8(self, *, format, label='A', count=919, save_kwargs=(), load_kwargs=()):
        """Test exporting 8x8 files."""
        file = self.temp_path / f'8x8.{format}'
        font = self.fixed4x6.expand(right=4, bottom=2, adjust_metrics=False)
        monobit.save(font, file, format=format, **(save_kwargs or {}))
        font, *_ = monobit.load(file, format=format, **(load_kwargs or {}))
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self.assertEqual(len(font.glyphs), count)
        self.assertEqual(font.get_glyph(label).reduce().as_text(), self.fixed4x6_A)

    # BDF

    def test_export_bdf(self):
        """Test exporting bdf files."""
        self._export_4x6(format='bdf')

    # Windows

    def test_export_fon(self):
        """Test exporting fon files."""
        self._export_4x6(format='mzfon', count=256, label=b'A')

    def test_export_fnt_v1(self):
        """Test exporting v1 fnt files."""
        self._export_4x6(format='win', save_kwargs=dict(version=1), count=256, label=b'A')

    def test_export_fnt_v2(self):
        """Test exporting fnt files."""
        self._export_4x6(format='win', save_kwargs=dict(version=2), count=256, label=b'A')

    def test_export_fnt_v3(self):
        """Test exporting fnt files."""
        self._export_4x6(format='win', save_kwargs=dict(version=3), count=256, label=b'A')

    # Unifont

    def test_export_hex(self):
        """Test exporting hex files."""
        self._export_8x16(format='unifont')

    # other text formats

    def test_export_draw(self):
        """Test exporting non-8x16 draw files with comments."""
        self._export_4x6(format='hexdraw')

    def test_export_psf2txt(self):
        """Test exporting psf2txt files."""
        self._export_4x6(format='psf2txt')

    def test_export_clt(self):
        """Test exporting consolet files."""
        self._export_4x6(format='consoleet', label=b'A')

    def test_export_mkwinfont(self):
        """Test exporting mkwinfont .fd files."""
        self._export_4x6(format='mkwinfont', label=b'A', count=192)

    # PSF

    def test_export_psf(self):
        """Test exporting psf files."""
        self._export_4x6(format='psf')

    def test_export_psf1(self):
        """Test exporting psf version 1 files."""
        self._export_8x16(format='psf', count=256, save_kwargs=dict(version=1, count=256))

    # FZX

    def test_export_fzx(self):
        """Test exporting fzx files."""
        self._export_4x6(format='fzx', label=b'A', count=191)

    # DEC DRCS

    def test_export_dec_drcs(self):
        """Test exporting dec-drcs files."""
        self._export_8x16(format='dec', count=94, label=b'A')

    # yaff

    def test_export_yaff(self):
        """Test exporting yaff files"""
        self._export_4x6(format='yaff')

    # Raw binary

    def test_export_raw(self):
        """Test exporting raw binary files."""
        self._export_4x6(
            format='raw', label=b'A',
            load_kwargs=dict(cell=(4, 6), first_codepoint=31),
        )

    def test_export_raw_wide(self):
        """Test exporting raw binary files with wide strike."""
        self._export_4x6(
            format='raw', label=b'A',
            save_kwargs=dict(strike_count=256),
            load_kwargs=dict(cell=(4, 6), first_codepoint=31, strike_count=256, count=919),
        )

    def test_export_raw_bitaligned(self):
        """Test exporting raw binary files with wiide strike."""
        self._export_4x6(
            format='raw', label=b'A',
            save_kwargs=dict(align='bit'),
            load_kwargs=dict(cell=(4, 6), first_codepoint=31, align='bit'),
        )

    def test_export_raw_inverted(self):
        """Test exporting raw binary files with wiide strike."""
        self._export_4x6(
            format='raw', label=b'A',
            save_kwargs=dict(ink=0),
            load_kwargs=dict(cell=(4, 6), first_codepoint=31, ink=0),
        )

    def test_export_raw_msb_right(self):
        """Test exporting raw binary files with most significant bit right."""
        self._export_4x6(
            format='raw', label=b'A',
            save_kwargs=dict(msb='r'),
            load_kwargs=dict(cell=(4, 6), first_codepoint=31, msb='r'),
        )

    # BMFont

    def test_export_bmf_text(self):
        """Test exporting bmfont files with text descriptor."""
        self._export_4x6(format='bmfont')

    def test_export_bmf_json(self):
        """Test exporting bmfont files with json descriptor."""
        self._export_4x6(format='bmfont', save_kwargs=dict(descriptor='json'))

    def test_export_bmf_xml(self):
        """Test exporting bmfont files with xml descriptor."""
        self._export_4x6(format='bmfont', save_kwargs=dict(descriptor='xml'))

    def test_export_bmf_binary(self):
        """Test exporting bmfont files with binary descriptor."""
        self._export_4x6(format='bmfont', save_kwargs=dict(descriptor='binary'))

    # Image

    def test_export_png(self):
        """Test exporting image files."""
        self._export_4x6(
            format='image', count=192, label=b'A',
            save_kwargs=dict(codepoint_range=range(256)),
            load_kwargs=dict(cell=(4, 6)),
        )

    def test_export_imageset(self):
        """Test exporting imageset directories."""
        self._export_4x6(format='imageset', label=b'A')

    def test_export_pilfont(self):
        """Test exporting PILfont files."""
        self._export_4x6(format='pilfont', count=192, label=b'A')

    def test_export_sfont(self):
        """Test exporting SFont files."""
        self._export_4x6(format='sfont', count=93, label=b'A')

    # CPI

    def test_export_cpi_font(self):
        """Test exporting CPI (FONT) files"""
        self._export_8x16_cp437(format='cpi', save_kwargs=dict(version='FONT'))

    def test_export_cpi_fontnt(self):
        """Test exporting CPI (FONT.NT) files"""
        self._export_8x16_cp437(format='cpi', save_kwargs=dict(version='FONT.NT'))

    def test_export_cpi_drfont(self):
        """Test exporting CPI (DRFONT) files"""
        self._export_8x16_cp437(format='cpi', save_kwargs=dict(version='DRFONT'))

    def test_export_cp(self):
        """Test exporting kbd CP files"""
        self._export_8x16_cp437(format='kbd', save_kwargs=dict(version='FONT'))

    def test_export_cp_nt(self):
        """Test exporting bare FONT.NT codepage."""
        self._export_8x16_cp437(format='kbd', save_kwargs=dict(version='FONT.NT'))

    def test_export_cp_drfont(self):
        """Test exporting bare DRFONT codepage."""
        self._export_8x16_cp437(format='kbd', save_kwargs=dict(version='DRFONT'))

    # Figlet

    def test_export_flf(self):
        """Test exporting flf files."""
        self._export_4x6(format='figlet')

    # Apple

    def test_export_dfont(self):
        """Test exporting dfont files with NFNT resource."""
        # count=220: mac-roman only, plus missing glyph
        self._export_4x6(format='mac', count=220, save_kwargs=dict(resource_type='NFNT'))

    def test_export_sbit(self):
        """Test exporting dfont files with bitmap sfnt resource."""
        # 920 as missing glyph is added
        self._export_4x6(format='mac', count=920, save_kwargs=dict(resource_type='sfnt'))

    def test_export_iigs(self):
        """Test exporting Apple IIgs font files."""
        self._export_4x6(format='iigs', count=220)

    def test_export_iigs_v15(self):
        """Test exporting Apple IIgs v1.5 font files."""
        self._export_4x6(format='iigs', count=220, save_kwargs=dict(version=0x105))

    def test_export_bare_nfnt(self):
        """Test exporting bare NFNT files."""
        self._export_4x6(format='nfnt', count=220, label=b'A')

    # GDOS

    def test_export_gdos(self):
        """Test exporting uncompressed gdos files."""
        self._export_4x6(format='gdos', count=256, label=b'A')

    # pcl

    def test_export_hppcl(self):
        """Test exporting PCL files."""
        self._export_4x6(format='hppcl', count=192, label=b'A')

    def test_export_hppcl_landscape(self):
        """Test exporting PCL files in landscape orientation."""
        self._export_4x6(
            format='hppcl', count=192, label=b'A',
            save_kwargs=dict(orientation='landscape')
        )

    # vfont

    def test_export_vfont(self):
        """Test exporting vfont files."""
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self._export_4x6(format='vfont', count=192, label=b'A')

    # fontx

    def test_export_fontx(self):
        """Test exporting fontx files."""
        self._export_4x6(format='vfont', count=192, label=b'A')

    # BBC

    def test_export_bbc(self):
        """Test exporting bbc files."""
        # only 8-bit codepoints; input font excludes [0, 0x20) and [0x80, 0xa0)
        self._export_8x8(format='bbc', count=191, label=b'A')

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
        self._export_8x16(format='xbin', count=256, label=b'A')

    # Optiks PCR

    def test_export_optiks(self):
        """Test exporting Optiks PCR files."""
        self._export_8x8(format='pcr', count=256, label=b'A')

    # Write On!

    def test_export_writeon(self):
        """Test exporting Write On! files."""
        self._export_4x6(format='writeon', count=128)

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
        # labelling is not correct
        self._export_8x8(format='64c', label=0x22)

    # +3DOS

    def test_export_plus3dos(self):
        """Test exporting plus3dos files."""
        self._export_8x8(format='plus3dos', count=96, label=b'A')

    # GRASP / PCPaint old format

    def test_export_grasp(self):
        """Test exporting GRASP files."""
        self._export_4x6(format='grasp', count=255, label=b'A')

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
        self._export_4x6(format='wsfont', count=256)

    def test_export_netbsd(self):
        """Test exporting netbsd files."""
        self._export_4x6(format='netbsd', count=256)

    # freebsd vtfont

    def test_export_vtfont(self):
        """Test exporting freebsd vt font files."""
        self._export_4x6(format='vtfont')

    # sfnt

    def test_export_sfnt_otb(self):
        """Test exporting otb files."""
        # 920 as .notdef is added
        self._export_4x6(format='sfnt', count=920)

    def test_export_sfnt_apple_sbit(self):
        """Test exporting apple-style sbit files (bare, not in dfont container)."""
        # 920 as .notdef is added
        self._export_4x6(format='sfnt', count=920, save_kwargs=dict(version='apple'))

    def test_export_sfnt_ttc(self):
        """Test exporting ttc files."""
        # 920 as .notdef is added
        self._export_4x6(format='ttcf', count=920)

    # geos

    def test_export_vlir(self):
        """Test exporting GEOS VLIR resources."""
        self._export_4x6(format='vlir', count=96, load_kwargs=dict(extract_del=True))

    def test_export_geos(self):
        """Test exporting GEOS convert files."""
        self._export_4x6(format='geos', count=96, load_kwargs=dict(extract_del=True))

    def test_export_geos_mega(self):
        """Test exporting GEOS convert files in mega format."""
        self._export_4x6(format='geos', count=96, save_kwargs=dict(mega=True), load_kwargs=dict(extract_del=True))

    # pc/geos

    def test_export_pcgeos(self):
        """Test exporting PC/GEOS files."""
        self._export_4x6(format='pcgeos', count=192)

    # DosStart

    def test_export_dosstart_bitmap(self):
        """Test exporting DosStart bitmap files."""
        self._export_4x6(format='dosstart', count=96, label=b'A')

    # pcf

    def test_export_pcf(self):
        """Test exporting PCF files"""
        for byte_order in ('big', 'little'):
            for bit_order in ('big', 'little'):
                for scan_unit in (1, 2, 4, 8):
                    for padding_bytes in (1, 2, 4, 8):
                        # file = self.temp_path / f'4x6_{byte_order[0].upper()}{bit_order[0]}u{scan_unit}p{padding_bytes}.pcf'
                        self._export_4x6(format='pcf', save_kwargs=dict(
                            byte_order=byte_order, bit_order=bit_order,
                            scan_unit=scan_unit, padding_bytes=padding_bytes,
                            overwrite=True
                        ))

    # EDWIN

    def test_export_edwin(self):
        """Test exporting EDWIN files."""
        self._export_4x6(format='edwin', count=127, label=b'A')


if __name__ == '__main__':
    unittest.main()
