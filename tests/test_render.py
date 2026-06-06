"""
monobit test suite
rendering tests
"""

import os
import io
import unittest

import monobit
from .base import BaseTester, get_stringio, assert_text_eq



class TestRender(BaseTester):
    """Test renderer."""

    # all directions

    def test_render_ltr_ttb(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='l t f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.@......
@@@.....
.@......
.@......
..@.....
........
.@...@..
@@..@.@.
.@....@.
.@...@..
@@@.@@@.
........
""")

    def test_render_ltr_btt(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='l b f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.@...@..
@@..@.@.
.@....@.
.@...@..
@@@.@@@.
........
.@......
@@@.....
.@......
.@......
..@.....
........
""")

    def test_render_rtl_ttb(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='r t f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.....@..
....@@@.
.....@..
.....@..
......@.
........
.@...@..
@.@.@@..
..@..@..
.@...@..
@@@.@@@.
........
""")

    def test_render_rtl_btt(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='r b f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.@...@..
@.@.@@..
..@..@..
.@...@..
@@@.@@@.
........
.....@..
....@@@.
.....@..
.....@..
......@.
........
""")


    def test_render_ttb_rtl(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='t r f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.@...@..
@@..@@@.
.@...@..
.@...@..
@@@...@.
........
.@......
@.@.....
..@.....
.@......
@@@.....
........
""")


    def test_render_ttb_ltr(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='t l f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.@...@..
@@@.@@..
.@...@..
.@...@..
..@.@@@.
........
.....@..
....@.@.
......@.
.....@..
....@@@.
........
""")


    def test_render_btt_rtl(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='b r f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.@......
@.@.....
..@.....
.@......
@@@.....
........
.@...@..
@@..@@@.
.@...@..
.@...@..
@@@...@.
........
""")

    def test_render_btt_ltr(self):
        text = monobit.render_text(self.fixed4x6, 't\n12', direction='b l f').as_text(inklevels='.@')
        assert_text_eq(text, """\
.....@..
....@.@.
......@.
.....@..
....@@@.
........
.@...@..
@@@.@@..
.@...@..
.@...@..
..@.@@@.
........
""")


    # composition

    # tiny sample from unscii-8.hex at https://github.com/viznut/unscii
    # "Licensing: You can consider it Public Domain (or CC-0)" for unscii-8
    unscii8_sample = """
00020:0000000000000000
00075:0000666666663E00
00305:FF00000000000000
00327:0000000000000818
"""

    composed = """\
@@@@@@@@........@@@@@@@@@@@@@@@@........
........................................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
.@@..@@..@@..@@.........................
..@@@@@...@@@@@.....@...............@...
...@@..............@@..............@@...
"""

    def test_compose(self):
        file = get_stringio(self.unscii8_sample)
        f,  *_ = monobit.load(file, format='unifont')
        text = monobit.render_text(
            f, 'u\u0305\u0327u \u0305\u0327 \u0305 \u0327'
        ).as_text(inklevels='.@')
        assert_text_eq(text, self.composed)

    # rendering output formats

    def test_render_text(self):
        """Render text format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_text(inklevels='-X', border='.')
        assert_text_eq(text, """\
-X-.
XX-.
-X-.
-X-.
XXX.
....
""")

    def test_render_blocks_1x1(self):
        """Render 1x1 blocks format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_blocks((1, 1))
        assert_text_eq(text, (
            ' █  \n'
            '██  \n'
            ' █  \n'
            ' █  \n'
            '███ \n'
            '    \n'
        ).replace(' ', '\xa0'))

    def test_render_blocks_2x2(self):
        """Render 2x2 blocks format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_blocks((2, 2))
        assert_text_eq(text, (
            '▟ \n'
            '▐ \n'
            '▀▘\n'
        ).replace(' ', '\xa0'))

    def test_render_blocks_2x3(self):
        """Render 2x3 blocks format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_blocks((2, 3))
        assert_text_eq(text, (
            '🬫 \n'
            '🬍🬃\n'
        ).replace(' ', '\xa0'))

    def test_render_blocks_2x4(self):
        """Render 2x4 blocks format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_blocks((2, 4))
        assert_text_eq(text, (
            '⢺⠀\n'
            '⠉⠁\n'
        ).replace(' ', '\xa0'))

    def test_render_blocks_1x2(self):
        """Render 1x2 blocks format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_blocks((1, 2))
        assert_text_eq(text, (
            '▄█  \n'
            ' █  \n'
            '▀▀▀ \n'
        ).replace(' ', '\xa0'))

    def test_render_blocks_1x3(self):
        """Render 1x3 blocks format, 2 ink levels"""
        text = monobit.render_text(self.fixed4x6, '1').as_blocks((1, 3))
        assert_text_eq(text, (
            '🬋█  \n'
            '🬋🬎🬋 \n'
        ).replace(' ', '\xa0'))

    shades_4 = """\n
levels: 4

'-':
    .12@
"""

    def test_render_4shades(self):
        """Render 1x1 shaded blocks format, 4 ink levels"""
        font, *_ = monobit.load(get_stringio(self.shades_4))
        text = monobit.render_text(font, '-').as_shades(border=(0,0,0))
        assert_text_eq(text,
            '\x1b[38;2;0;0;0m\u2588\x1b[0m'
            '\x1b[38;2;85;85;85m\u2588\x1b[0m'
            '\x1b[38;2;170;170;170m\u2588\x1b[0m'
            '\x1b[38;2;255;255;255m\u2588\x1b[0m\n'
        )

    shades_16 = """\n
levels: 16

'-':
    .123456789ABCDE@
"""

    def test_render_16shades(self):
        """Render 1x1 shaded blocks format, 16 ink levels"""
        font, *_ = monobit.load(get_stringio(self.shades_16))
        text = monobit.render_text(font, '-').as_shades(border=(0,0,0))
        assert_text_eq(text,
            '\x1b[38;2;0;0;0m\u2588\x1b[0m'
            '\x1b[38;2;17;17;17m\u2588\x1b[0m'
            '\x1b[38;2;34;34;34m\u2588\x1b[0m'
            '\x1b[38;2;51;51;51m\u2588\x1b[0m'
            '\x1b[38;2;68;68;68m\u2588\x1b[0m'
            '\x1b[38;2;85;85;85m\u2588\x1b[0m'
            '\x1b[38;2;102;102;102m\u2588\x1b[0m'
            '\x1b[38;2;119;119;119m\u2588\x1b[0m'
            '\x1b[38;2;136;136;136m\u2588\x1b[0m'
            '\x1b[38;2;153;153;153m\u2588\x1b[0m'
            '\x1b[38;2;170;170;170m\u2588\x1b[0m'
            '\x1b[38;2;187;187;187m\u2588\x1b[0m'
            '\x1b[38;2;204;204;204m\u2588\x1b[0m'
            '\x1b[38;2;221;221;221m\u2588\x1b[0m'
            '\x1b[38;2;238;238;238m\u2588\x1b[0m'
            '\x1b[38;2;255;255;255m\u2588\x1b[0m\n'
        )

    shades_256 = """\n
levels: 256

'-':
    ..{}@@
""".format(''.join(f'{_x:02X}' for _x in range(1, 255)))


    def test_render_256shades(self):
        """Render 1x1 shaded blocks format, 256 ink levels"""
        font, *_ = monobit.load(get_stringio(self.shades_256))
        text = monobit.render_text(font, '-').as_shades(border=(0,0,0))
        assert_text_eq(text,
            ''.join(
                f'\x1b[38;2;{_s};{_s};{_s}m\u2588\x1b[0m'
                for _s in range(256)
            ) + '\n'
        )

    # render command (render to file)

    def test_render_command_text(self):
        file = self.temp_path / 'rendered.txt'
        monobit.render(self.fixed4x6, file, text='12', format='text', inklevels='.@')
        with open(file) as output:
            text = output.read()
        assert_text_eq(text, """\
.@...@..
@@..@.@.
.@....@.
.@...@..
@@@.@@@.
........
""")

    def test_render_command_blocks(self):
        file = self.temp_path / 'rendered.blocks'
        monobit.render(self.fixed4x6, file, text='12', format='blocks', resolution='2x3')
        with open(file) as output:
            text = output.read()
        assert_text_eq(text, '🬫\xa0🬅🬓\n🬍🬃🬍🬃\n')

    def test_render_command_shades(self):
        file = self.temp_path / 'rendered.shades'
        monobit.render(self.fixed4x6, file, text='12', format='shades')
        with open(file) as output:
            text = output.read()
        assert_text_eq(text,
            '\x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[0m'
            ' \x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[0m'
            ' \n\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[0m'
            ' \x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[0m'
            ' \n\x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[0m'
            ' \x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[0m'
            ' \n\x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[0m'
            ' \x1b[38;2;0;0;0m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;0;0;0m█\x1b[0m\x1b[0m'
            ' \n\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[0m'
            ' \x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[38;2;255;255;255m█\x1b[0m\x1b[0m \n\x1b[0m'
            ' \x1b[0m \x1b[0m \x1b[0m \x1b[0m \x1b[0m \x1b[0m \x1b[0m \n'
        )

    def test_render_command_sixel(self):
        file = self.temp_path / 'rendered.sixel'
        monobit.render(self.fixed4x6, file, text='12', format='sixel')
        with open(file) as output:
            text = output.read()
        assert_text_eq(text, '\x1bPq#0;2;0;0;0;#1;2;100;100;100;#0L?N?LEH?$#1Q^O?QXU?-\x1b\\')

    def test_render_command_image(self):
        file = self.temp_path / 'rendered.png'
        monobit.render(self.fixed4x6, file, text='12', format='image')
        with open(file, 'rb') as output:
            bin = output.read()
        assert bin == (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x08\x00\x00'
            b'\x00\x06\x08\x02\x00\x00\x00qgH\xac\x00\x00\x006IDATx\x9ce'
            b'\x8dA\n\x000\x08\xc3R_\xe2\xff?\xd9\x1d:\x86\xc3\x1cJP\xaa'
            b"\x00\xb6\x81\xee\x9e^\xb1`[R&%\xe9-\xa6\x17?)\x01\xf7\xd4N\xe5\xe7"
            b"\xe6\x00'\xb5\x1f\x18\xe9Bk\x10\x00\x00\x00\x00IEND\xaeB`\x82"
        )


if __name__ == '__main__':
    unittest.main()
