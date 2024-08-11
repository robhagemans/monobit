"""
monobit test suite
import tests
"""

import os
import unittest

import monobit
from .base import BaseTester, ensure_asset, assert_text_eq


class TestImport(BaseTester):
    """Test monobit export/import."""

    # no import test:
    # dashen
    # 64c
    # +3DOS
    # GRASP / PCPaint old format


    # BDF

    def test_import_bdf(self):
        """Test importing bdf files."""
        font, *_ = monobit.load(self.font_path / '4x6.bdf')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Windows

    def test_import_fon(self):
        """Test importing fon files."""
        font, *_ = monobit.load(self.font_path / '6x13.fon')
        # there will be fewer chars if we drop blanks as undefined
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_fnt(self):
        """Test importing fnt files."""
        font, *_ = monobit.load(self.font_path / '6x13.fnt')
        # there will be fewer chars if we drop blanks as undefined
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

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
            # but this way we exercise the PE code
            font, *_ = monobit.load(file)

    def test_import_pe_64(self):
        """Test 64-bit PE executables."""
        file = ensure_asset(
            self.pelib + '64_pe/',
            '64_pe_data_dir_resources_dir_entries_rt_font.dat'
        )
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 224)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
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
""")

    # ChiWriter

    horstmann = 'https://horstmann.com/ChiWriter/'

    def test_import_chiwriter_v4(self):
        """Test importing ChiWriter v4 files."""
        file = ensure_asset(self.horstmann, 'cw4.zip')
        font, *_ = monobit.load(file / 'CW4/BOLD.CFT')
        self.assertEqual(len(font.glyphs), 159)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
..@@@..
.@@@@@.
.@@@@@.
@@@.@@@
@@@.@@@
@@@@@@@
@@@.@@@
""")

    def test_import_chiwriter_v3(self):
        """Test importing ChiWriter v3 files."""
        file = ensure_asset(self.horstmann, 'cw4.zip')
        font, *_ = monobit.load(file / 'CW4/GREEK.CFT')
        self.assertEqual(len(font.glyphs), 59)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
...@...
..@@@..
..@@@..
.@@.@@.
.@@.@@.
@@@@@@@
@@...@@
""")

    # Signum

    sigfonts = 'http://cd.textfiles.com/atarilibrary/atari_cd11/GRAFIK/SIGFONTS/'

    def test_import_signum_p9(self):
        """Test importing Signum P9 files."""
        file = ensure_asset(self.sigfonts + '9NADEL/', 'FONT_001.P9')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
..................@@@........
................@@..@........
................@...@........
...............@@...@........
...............@..@.@........
..............@..@@.@........
@@@@@@@@@.....@...@@@........
@.@@.@.@@@@...@..@..@........
@@.@..@@..@...@.@@@.@........
@@@@.@@@@.@@..@.@...@........
@.@@..@@@@.@@.@..@@@.........
...@......@.@.@@@............
....@.....@@@@...............
....@@......@@@@@@@@@@@@.....
......@....@.@@@@.......@....
.......@@@@@@@@@....@...@@...
.........@@......@@.@.@@..@..
........@........@@...@....@.
........@.........@..@@.....@
......@@........@@@@@...@@..@
......@............@@.@.....@
......@...........@.@.@@@...@
......@...........@@@.@@@...@
......@.................@...@
......@..............@......@
......@.....................@
......@.....................@
......@.....................@
......@.....................@
......@.....................@
......@....................@.
......@@@...............@@@..
........@...............@.@..
........@@@.............@@...
..........@@@@.......@@@@....
..............@@@@@@@........
""")

    def test_import_signum_e24(self):
        """Test importing Signum E24 files."""
        file = ensure_asset(self.sigfonts + '9NADEL/', 'FONT_001.E24')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
........@@...
.......@.@...
......@..@...
......@.@....
.@@@..@.@....
@...@..@.....
.@...@@......
..@@@..@@....
.....@..@@...
....@.....@..
...@....@..@.
..@....@.@..@
..@.....@.@.@
..@....@.@..@
..@.........@
..@.........@
...@.......@.
....@.....@..
.....@@@@@...
""")

    def test_import_signum_p24(self):
        """Test importing Signum P24 files."""
        file = ensure_asset(self.sigfonts + '24NADEL/', 'FONT_001.P24')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
............................@@@.............
...........................@..@.............
..........................@...@.............
.........................@....@.............
........................@.....@.............
........................@......@............
.......................@.......@............
.......................@....@..@............
.......................@....@..@............
......................@...@.@.@@............
...@@@@@@@@...........@....@@@.@............
.@@@.@....@@@@........@....@...@............
@...@@.......@@.......@...@....@............
@..@.@..@..@..@@.....@....@....@............
@.@..@...@.@...@@....@..@.@@...@............
@.@..@..@.@..@..@@...@...@....@.............
@@..@......@.@...@...@........@.............
.@..@.....@@@@...@...@......@@..............
.@...@.......@@..@@..@....@@................
.....@.........@...@.@@@@@..................
......@........@@@@@@.......................
......@.............@.......................
.......@...........@@@@@@.@@@@@@@...........
........@.........@@@....@@......@@@........
.........@@......@..@.@@@...........@.......
...........@@@@@@...@@@@.............@......
.................@@@@.........@.......@.....
...............@@...........@..@.@.....@....
..............@...........@...@...@@....@...
.............@............@.@....@.......@..
............@..............@....@.........@.
............@.....................@.......@.
...........@.............@..@@.@......@...@.
..........@@............@.@@........@.@...@.
..........@..................@.@.@........@.
..........@......................@..@@....@.
.........@..................@.@....@.......@
.........@.................@.@.@...@.@.....@
.........@.......................@...@.....@
.........@..........................@......@
.........@......................@..........@
.........@.................................@
.........@.................................@
.........@.................................@
.........@.................................@
.........@.................................@
.........@................................@@
.........@................................@.
.........@................................@.
.........@................................@.
.........@@..............................@..
..........@..............................@..
..........@@............................@...
...........@@........................@@@@...
............@@......................@@.@....
.............@@.....................@.@.....
..............@@....................@@......
...............@@@..................@@......
.................@@@@...........@@@@........
.....................@@@@@@@@@@@............
""")

    def test_import_signum_l30(self):
        """Test importing Signum L30 files."""
        file = ensure_asset(self.sigfonts + 'LASER/', 'FONT_001.L30')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 68)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
.......................@@@...........
.......................@.@...........
......................@..@...........
....................@@...@...........
....................@.....@..........
...................@......@..........
...................@...@..@..........
...................@...@..@..........
...@@@@@@.........@...@@@@@..........
.@@@@...@@@@......@....@..@..........
@..@@......@@.....@...@...@..........
@..@@..@.@..@@....@...@...@..........
@.@.@...@@...@....@.@.@@..@..........
@@@@@..@@@.@.@@...@..@...@...........
.@.@....@@@@..@...@....@@............
.@..@......@@.@@..@...@@.............
....@........@..@.@@@@...............
.....@.......@@@@@...................
.....@@.........@@@@@.@@@@@@.........
.......@.......@@@...@@.....@@.......
........@.....@..@@@@.........@......
.........@@@@@...@@@...........@.....
..............@@@@.......@......@....
............@@........@@.@@.@@...@...
...........@..........@@....@.....@..
..........@............@...@.......@.
..........@.................@......@.
.........@...........@.@@.@.....@..@.
........@@..........@.@@@.@.@.@.@..@.
........@...................@.@@...@.
........@..............@.@...@......@
........@..............@@.@..@.@....@
........@...................@..@....@
........@..................@..@.....@
........@...........................@
........@...........................@
........@...........................@
........@...........................@
........@..........................@@
........@..........................@.
........@..........................@.
........@..........................@.
........@.........................@..
........@@.......................@@..
.........@@....................@@@...
..........@@..................@@.@...
...........@@.................@.@....
............@@................@@.....
.............@@@@@.........@@@@@.....
..................@@@@@@@@@..........
""")

    # Unifont

    def test_import_hex(self):
        """Test importing hex files."""
        font, *_ = monobit.load(self.font_path / '8x16.hex')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_draw(self):
        """Test importing draw files."""
        font, *_ = monobit.load(self.font_path / '8x16.draw')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    # other text formats

    def test_import_psf2txt(self):
        """Test importing psf2txt files."""
        font, *_ = monobit.load(self.font_path / '4x6.txt', format='psf2txt')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_clt(self):
        """Test importing consoleet files."""
        font, *_ = monobit.load(self.font_path / '4x6.clt', format='consoleet')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_mkwinfont(self):
        """Test importing mkwinfont .fd files."""
        font, *_ = monobit.load(self.font_path / '6x13.fd', format='mkwinfont')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    # PSF

    def test_import_psf(self):
        """Test importing psf files."""
        font, *_ = monobit.load(self.font_path / '4x6.psf')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # FZX

    def test_import_fzx(self):
        """Test importing fzx files."""
        font, *_ = monobit.load(self.font_path / '4x6.fzx')
        self.assertEqual(len(font.glyphs), 191)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # DEC DRCS

    def test_import_dec_drcs(self):
        """Test importing dec-drcs files."""
        font, *_ = monobit.load(self.font_path / '6x13.dec')
        self.assertEqual(len(font.glyphs), 94)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    # yaff

    def test_import_yaff(self):
        """Test importing yaff files"""
        font, *_ = monobit.load(self.font_path / '4x6.yaff')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Raw binary

    def test_import_raw(self):
        """Test importing raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6.raw', cell=(4, 6), first_codepoint=0x1f)
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_raw_bitaligned(self):
        """Test importing bit-aligned raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6-bitaligned.raw', cell=(4, 6), align='bit', first_codepoint=0x1f)
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_raw_inverted(self):
        """Test importing inverted raw binary files."""
        font, *_ = monobit.load(self.font_path / '4x6-inverted.raw', cell=(4, 6), ink=0, first_codepoint=0x1f)
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_raw_msb_right(self):
        """Test importing raw binary files with most significant bit right."""
        font, *_ = monobit.load(self.font_path / '4x6-bitaligned.raw', cell=(4, 6), align='bit', first_codepoint=0x1f)
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # BMFont

    def test_import_bmf_text(self):
        """Test importing bmfont files with text descriptor."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-text.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_bmf_xml(self):
        """Test importing bmfont files with XML descriptor."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-xml.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_bmf_json(self):
        """Test importing bmfont files with JSON descriptor."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-json.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_bmf_binary(self):
        """Test importing bmfont files with binary descriptor."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-binary.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_bmf_8bit(self):
        """Test importing bmfont files with 8-bit image."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-8bit.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_bmf_packed(self):
        """Test importing bmfont files with packed 32-bit image."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-32bit-packed.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    def test_import_bmf_nonpacked(self):
        """Test importing bmfont files with non-packed 32-bit image."""
        font, *_ = monobit.load(self.font_path / '6x13.bmf' / '6x13-32bit-nonpacked.fnt', format='bmfont')
        self.assertEqual(len(font.glyphs), 189)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed6x13_A)

    # Image

    def test_import_png(self):
        """Test importing image files."""
        font, *_ = monobit.load(self.font_path / '4x6.png', cell=(4, 6), count=919, padding=(0,0), first_codepoint=0x1f)
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_imageset(self):
        """Test importing imageset directories."""
        font, *_ = monobit.load(self.font_path / '4x6.imageset', format='imageset')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_pilfont(self):
        """Test importing PILfont files."""
        font, *_ = monobit.load(self.font_path / '4x6.pil')
        self.assertEqual(len(font.glyphs), 192)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # CPI

    def test_import_cpi_font(self):
        """Test importing CPI (FONT) files."""
        fnt_file = self.font_path / '8x16-font.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_cpi_fontnt(self):
        """Test importing CPI (FONT.NT) files"""
        fnt_file = self.font_path / '8x16-fontnt.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_cpi_drfont(self):
        """Test importing CPI (DRFONT) files"""
        fnt_file = self.font_path / '8x16-drfont.cpi'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    def test_import_cp(self):
        """Test importing kbd CP files"""
        fnt_file = self.font_path / '8x16.cp'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed8x16_A)

    # Figlet

    def test_import_flf(self):
        """Test importing flf files."""
        font, *_ = monobit.load(self.font_path / '4x6.flf')
        self.assertEqual(len(font.glyphs), 919)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # Apple

    def test_import_dfont(self):
        """Test importing dfont files."""
        font, *_ = monobit.load(self.font_path / '4x6.dfont')
        # only 195 glyphs in the font as it's in mac-roman encoding now
        self.assertEqual(len(font.glyphs), 195)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_iigs(self):
        """Test importing Apple IIgs font files."""
        font, *_ = monobit.load(self.font_path / '4x6.iigs', format='iigs')
        # only 220 glyphs in the font as it's in mac-roman encoding now
        self.assertEqual(len(font.glyphs), 220)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_mgtk(self):
        """Testing importing Apple II MouseGraphics ToolKit font files."""
        font, *_ = monobit.load(self.font_path / '4x6.mgtk', format='mgtk')
        self.assertEqual(len(font.glyphs), 128)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # Bare NFNT
    lisafonts = 'https://github.com/azumanga/apple-lisa/raw/main/LISA_OS/FONTS/'

    def test_import_bare_nfnt(self):
        """Test importing bare NFNT files."""
        file = ensure_asset(self.lisafonts, 'TILE7R20S.F')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 193)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
.@@.
@..@
@..@
@@@@
@..@
@..@
""")

    # Amiga

    def test_import_amiga(self):
        """Test importing amiga font files."""
        font, *_ = monobit.load(self.font_path / 'wbfont.amiga' / 'wbfont_prop.font')
        self.assertEqual(len(font.glyphs), 225)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
.....................@......................
.....................@......................
....................@@@.....................
....................@@@.....................
...................@@@@@....................
...................@@@@@....................
...................@@@@@....................
..................@@@@@@@...................
..................@@@@@@@...................
.................@@@@@@@@@..................
.................@@@@@@@@@..................
................@@@.@@@@@@..................
................@@@.@@@@@@@.................
................@@@..@@@@@@.................
...............@@@...@@@@@@@................
...............@@@....@@@@@@................
..............@@@@....@@@@@@................
..............@@@......@@@@@@...............
..............@@@@@@@@@@@@@@@...............
.............@@@@@@@@@@@@@@@@@..............
.............@@@@@@@@@@@@@@@@@..............
............@@@@........@@@@@@..............
............@@@..........@@@@@@.............
...........@@@@..........@@@@@@.............
...........@@@............@@@@@.............
...........@@@............@@@@@@............
..........@@@..............@@@@@............
..........@@@..............@@@@@@...........
.........@@@@..............@@@@@@...........
.........@@@................@@@@@...........
.........@@@................@@@@@@..........
........@@@..................@@@@@..........
........@@@..................@@@@@@.........
.......@@@@...................@@@@@.........
.......@@@....................@@@@@.........
......@@@@....................@@@@@@........
......@@@......................@@@@@........
......@@@......................@@@@@@.......
.....@@@........................@@@@@.......
.....@@@........................@@@@@@@.....
....@@@@.........................@@@@@@@....
@@@@@@@@@@@@.................@@@@@@@@@@@@@@@
@@@@@@@@@@@@.................@@@@@@@@@@@@@@@
@@@@@@@@@@@@.................@@@@@@@@@@@@@@@
""")

    def test_import_gdos_compressed(self):
        """Test importing compressed, chained gdos font file."""
        font, *_ = monobit.load(
            self.font_path / 'gdos' / 'AI360GVP.VGA', format='gdos'
        )
        self.assertEqual(len(font.glyphs), 194)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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

    # pcl

    def test_import_hppcl(self):
        """Test importing PCL files."""
        fnt_file = self.font_path / '4x6.sfp'
        font, *_ = monobit.load(fnt_file)
        self.assertEqual(len(font.glyphs), 192)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # vfont

    def test_import_vfont_le(self):
        """Test importing little-endian vfont file."""
        font, *_ = monobit.load(
            self.font_path / '4x6.vfontle',
            first_codepoint=0x1f
        )
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    def test_import_vfont_be(self):
        """Test importing big-endian vfont file."""
        font, *_ = monobit.load(
            self.font_path / '4x6.vfontbe',
            first_codepoint=0x1f
        )
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # fontx

    def test_import_fontx_sbcs(self):
        """Test importing single-page fontx file."""
        font, *_ = monobit.load(
            self.font_path / '8x16-fontx-sbcs.fnt',
        )
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_fontx_dbcs(self):
        """Test importing multi-page fontx file."""
        font, *_ = monobit.load(
            self.font_path / '8x16-fontx.fnt',
        )
        # including 1000 blanks due to (our way of dealing with) contiguous-block structure
        self.assertEqual(len(font.glyphs), 1919)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    # Daisy-Dot

    def test_import_daisy2(self):
        """Test importing daisy-dot II file."""
        font, *_ = monobit.load(
            self.font_path / 'daisy' / 'times.nlq',
        )
        self.assertEqual(len(font.glyphs), 91)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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
        # first 4 glyphs form a picture

    # BBC

    def test_import_bbc(self):
        """Test importing bbc files."""
        font, *_ = monobit.load(self.font_path / '8x8.bbc')
        self.assertEqual(len(font.glyphs), 224)
        # note that 8x8.bbc is incorrectly labelled with A at 0x22
        assert_text_eq(font.get_glyph(0x22).reduce().as_text(), self.fixed4x6_A)

    # HBF

    def test_import_hbf(self):
        """Test importing HBF files."""
        font, *_ = monobit.load(self.font_path / '8x16.hbf')
        self.assertEqual(len(font.glyphs), 727)
        # hbf doesn't store 1-byte codepoints
        assert_text_eq(font.get_glyph('Ā').reduce().as_text(), """\
@@@@@@
@@@@@@
..@@..
..@@..
@@..@@
@@..@@
@@@@@@
@@@@@@
@@..@@
@@..@@
"""
)

    # XBIN

    def test_import_xbin(self):
        """Test importing XBIN files."""
        font, *_ = monobit.load(self.font_path / '8X16.XB')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    # Optiks PCR

    telparia = 'https://telparia.com/fileFormatSamples/font/pcrFont/'

    def test_import_optiks(self):
        """Test importing Optiks PCR files."""
        file = ensure_asset(self.telparia, 'FONT1.PCR')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
...@...
..@.@..
.@...@.
@.....@
@.....@
@@@@@@@
@.....@
@.....@
@.....@
""")

    # Write On!

    def test_import_writeon(self):
        """Test importing Write On! files."""
        font, *_ = monobit.load(self.font_path / '4x6.wof')
        self.assertEqual(len(font.glyphs), 919)
        # incorrectly labelled
        assert_text_eq(font.get_glyph(0x22).reduce().as_text(), self.fixed4x6_A)

    # Wyse

    def test_import_wyse(self):
        """Test importing Wyse-60 files."""
        font, *_ = monobit.load(self.font_path / '4x6.wyse', format='wyse')
        # only encoding codepoints < 0x0400 (4 banks)
        self.assertEqual(len(font.glyphs), 512)
        # incorrectly labelled
        assert_text_eq(font.get_glyph(0x22).reduce().as_text(), self.fixed4x6_A)

    # adafruit gfxfont

    def test_import_gfxfont(self):
        """Test importing gfxfont header files."""
        font, *_ = monobit.load(self.font_path / 'FreeSans9pt7b.h', format='gfxfont')
        self.assertEqual(len(font.glyphs), 95)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
.....@@.....
....@@@@....
....@@@@....
....@..@....
...@@..@@...
...@@..@@...
...@....@...
..@@....@@..
..@@@@@@@@..
..@......@..
.@@......@@.
.@@......@@.
@@........@@
""")


    # wsfont

    def test_import_wsfont(self):
        """Test importing wsfont files."""
        font, *_ = monobit.load(self.font_path / 'ter-i12n.wsf')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
.@@@.
@...@
@...@
@...@
@@@@@
@...@
@...@
@...@
""")

    def test_import_netbsd(self):
        """Test importing wsfont header files."""
        font, *_ = monobit.load(self.font_path / 'spleen5x8.h', format='netbsd')
        self.assertEqual(len(font.glyphs), 96)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
.@@.
@..@
@..@
@@@@
@..@
@..@
""")

    # freebsd vtfont

    def test_import_vtfont(self):
        """Test importing freebsd vtfont files."""
        font, boldfont = monobit.load(self.font_path / 'ter-u28.fnt')
        self.assertEqual(len(font.glyphs), 1185)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
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
        self.assertEqual(boldfont.get_glyph('A').reduce().as_text(), """\
..@@@@@@@..
.@@@@@@@@@.
@@@.....@@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@@@@@@@@@@
@@@@@@@@@@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
@@.......@@
""")

    # COM loaders

    def test_import_frapt(self):
        """Test importing Fontraptor files."""
        font, *_ = monobit.load(self.font_path / '8X16-FRA.COM')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_frapt_tsr(self):
        """Test importing Fontraptor TSR files."""
        font, *_ = monobit.load(self.font_path / '8X16-TSR.COM')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_mania(self):
        """Test importing Font Mania files."""
        font, *_ = monobit.load(self.font_path / '8X16-REX.COM')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_fontedit(self):
        """Test importing FONTEDIT files."""
        font, *_ = monobit.load(self.font_path / '8X16-FE.COM')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed8x16_A)

    def test_import_psfcom(self):
        """Test importing PSF2AMS files."""
        font, *_ = monobit.load(
            self.font_path / '4x6-ams.com',
            first_codepoint=0x1f
        )
        self.assertEqual(len(font.glyphs), 512)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    udg = 'https://www.seasip.info/Unix/PSF/Amstrad/UDG/'

    def test_import_udgcom(self):
        """Test importing UDG .COM files."""
        file = ensure_asset(self.udg, 'udg.zip')
        font, *_ = monobit.load(file / 'charset1.com')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
...@...
..@@@..
..@@@..
.@.@@@.
.@@@@@.
@@..@@@
@@..@@@
""")

    def test_import_letafont(self):
        """Test importing LETAFONT .COM files."""
        font, *_ = monobit.load(self.font_path / '8x8-letafont.com')
        self.assertEqual(len(font.glyphs), 256)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
..@@..
@@..@@
@@@@@@
@@..@@
@@..@@
""")

    # TeX PKFONT

    def test_import_pkfont(self):
        """Test importing PKFONT files."""
        font, *_ = monobit.load(self.font_path / 'cmbx10.120pk')
        self.assertEqual(len(font.glyphs), 128)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fontforge(self):
        """Test importing sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.otb')
        self.assertEqual(len(font.glyphs), 922)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fontforge_fakems(self):
        """Test importing 'fake MS' sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.ffms.ttf')
        self.assertEqual(len(font.glyphs), 922)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    def test_import_fontforge_dfont(self):
        """Test importing dfont-wrapped sfnt bitmap files produced by fontforge."""
        font, *_ = monobit.load(self.font_path / '4x6.sfnt.dfont')
        self.assertEqual(len(font.glyphs), 922)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # geos

    def test_import_geos(self):
        """Test importing GEOS fonts."""
        font, *_ = monobit.load(self.font_path / 'SHILLING.cvt.gz', extract_del=True)
        self.assertEqual(len(font.glyphs), 96)
        assert_text_eq(font.get_glyph(b'\x2a').reduce().as_text(), """\
.@@@.
.@@@.
.@@@.
.@@@.
.@@@.
@@@@@
.@@@.
..@..
""")

    # pc/geos


    bison_fnt = 'https://github.com/bluewaysw/pcgeos/raw/master/FontData/'

    def test_import_pcgeos(self):
        """Test importing PC/GEOS files."""
        file = ensure_asset(self.bison_fnt, 'Bison.fnt')
        fonts = monobit.load(file)
        self.assertEqual(len(fonts), 4)
        self.assertEqual(len(fonts[0].glyphs), 251)
        assert_text_eq(fonts[0].get_glyph(b'A').reduce().as_text(), """\
.@@@.
@...@
@...@
@@@@@
@...@
@...@
@...@
""")


    # palm

    def test_import_palm(self):
        """Test importing Palm OS fonts."""
        font, *_ = monobit.load(self.font_path / 'Alpha-2B.pdb')
        self.assertEqual(len(font.glyphs), 230)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
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
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
...@@...
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
@@....@@
""")

    # The Print Shop

    printshop = 'https://archive.org/download/msdos_broderbund_print_shop/printshop.zip/'

    def test_import_printshop(self):
        """Test importing The Print Shop for DOS files."""
        file = ensure_asset(self.printshop, 'FONT8.PSF')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 95)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), """\
..@@@..
..@@@..
.@..@@.
.@..@@.
@@@@@@@
@....@@
@....@@
""")

    # DosStart

    dosstart = 'https://archive.org/download/dosstart-19b/dosstart.zip/'

    def test_import_dosstart_bitmap(self):
        """Test importing DosStart bitmap files."""
        file = ensure_asset(self.dosstart, 'COUR.DSF')
        font, *_ = monobit.load(file)
        self.assertEqual(len(font.glyphs), 95)
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
..@@...
...@...
...@...
..@.@..
..@.@..
.@...@.
.@@@@@.
.@...@.
@@@.@@@
""")

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
        # all glyphs appear to be huge geometric patterns, this one is smallest
        assert_text_eq(font.get_glyph(0x27).reduce().as_text(), """\
@@@@
@@@@
@@@@
@@@@
""")

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
            assert_text_eq(font.get_glyph('A').reduce().as_text(), self.fixed4x6_A)

    # EDWIN

    def test_import_edwin(self):
        """Test importing EDWIN files."""
        font, *_ = monobit.load(self.font_path / '4x6.edwin.fnt', format='edwin')
        self.assertEqual(len(font.glyphs), 127)
        assert_text_eq(font.get_glyph(b'A').reduce().as_text(), self.fixed4x6_A)

    # RiscOS old format

    riscold = 'https://www.lewisgilbert.co.uk/archiology/archives/riscos2/'

    def test_import_riscos_old(self):
        """Test importing RiscOs x90y45 files."""
        file = ensure_asset(self.riscold, 'App1.zip')
        font, *_ = monobit.load(file / '!Fonts/Trinity/Medium/x90y45', format='riscos-xy')
        self.assertEqual(len(font.glyphs), 224)
        # all glyphs appear to be huge geometric patterns, this one is smallest
        assert_text_eq(font.get_glyph('A').reduce().as_text(), """\
....141...
...16c71..
..1533c5..
.156447d4.
1571..2883
""")


if __name__ == '__main__':
    unittest.main()
