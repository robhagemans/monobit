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
        text = monobit.render(self.fixed4x6, 't\n12', direction='l t f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='l b f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='r t f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='r b f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='t r f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='t l f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='b r f').as_text()
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
        text = monobit.render(self.fixed4x6, 't\n12', direction='b l f').as_text()
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
        text = monobit.render(
            f, 'u\u0305\u0327u \u0305\u0327 \u0305 \u0327'
        ).as_text()
        assert_text_eq(text, self.composed)

    # rendering output formats

    def test_render_text(self):
        """Render text format, 2 ink levels"""
        text = monobit.render(self.fixed4x6, '1').as_text(ink='X', paper='-', border='.')
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
        text = monobit.render(self.fixed4x6, '1').as_blocks((1, 1))
        assert_text_eq(text,
            ' █  \n'
            '██  \n'
            ' █  \n'
            ' █  \n'
            '███ \n'
            '    \n'
        )

    def test_render_blocks_2x2(self):
        """Render 2x2 blocks format, 2 ink levels"""
        text = monobit.render(self.fixed4x6, '1').as_blocks((2, 2))
        assert_text_eq(text,
            '▟ \n'
            '▐ \n'
            '▀▘\n'
        )

    def test_render_blocks_2x3(self):
        """Render 2x3 blocks format, 2 ink levels"""
        text = monobit.render(self.fixed4x6, '1').as_blocks((2, 3))
        assert_text_eq(text,
            '🬫 \n'
            '🬍🬃\n'
        )

    def test_render_blocks_2x4(self):
        """Render 2x4 blocks format, 2 ink levels"""
        text = monobit.render(self.fixed4x6, '1').as_blocks((2, 4))
        assert_text_eq(text,
            '⢺⠀\n'
            '⠉⠁\n'
        )

    def test_render_blocks_1x2(self):
        """Render 1x2 blocks format, 2 ink levels"""
        text = monobit.render(self.fixed4x6, '1').as_blocks((1, 2))
        assert_text_eq(text,
            '▄█  \n'
            ' █  \n'
            '▀▀▀ \n'
        )

    def test_render_blocks_1x3(self):
        """Render 1x3 blocks format, 2 ink levels"""
        text = monobit.render(self.fixed4x6, '1').as_blocks((1, 3))
        assert_text_eq(text,
            '🬋█  \n'
            '🬋🬎🬋 \n'
        )

    shades_4 = """\n
levels: 4

'-':
    .123@
"""

    def test_render_blocks_4shades(self):
        """Render 1x1 blocks format, 4 ink levels"""
        font, *_ = monobit.load(get_stringio(self.shades_4))
        text = monobit.render(font, '-').as_blocks((1, 1))
        assert_text_eq(text,
            '\x1b[38;2;0;0;0m\u2588'
            '\x1b[38;2;7;7;7m\u2588'
            '\x1b[38;2;14;14;14m\u2588'
            '\x1b[38;2;21;21;21m\u2588'
            '\x1b[38;2;255;255;255m\u2588\n'
        )

    shades_16 = """\n
levels: 16

'-':
    .123456789abcde@
"""

    def test_render_blocks_16shades(self):
        """Render 1x1 blocks format, 16 ink levels"""
        font, *_ = monobit.load(get_stringio(self.shades_16))
        text = monobit.render(font, '-').as_blocks((1, 1))
        assert_text_eq(text,
            '\x1b[38;2;0;0;0m\u2588'
            '\x1b[38;2;17;17;17m\u2588'
            '\x1b[38;2;34;34;34m\u2588'
            '\x1b[38;2;51;51;51m\u2588'
            '\x1b[38;2;68;68;68m\u2588'
            '\x1b[38;2;85;85;85m\u2588'
            '\x1b[38;2;102;102;102m\u2588'
            '\x1b[38;2;119;119;119m\u2588'
            '\x1b[38;2;136;136;136m\u2588'
            '\x1b[38;2;153;153;153m\u2588'
            '\x1b[38;2;170;170;170m\u2588'
            '\x1b[38;2;187;187;187m\u2588'
            '\x1b[38;2;204;204;204m\u2588'
            '\x1b[38;2;221;221;221m\u2588'
            '\x1b[38;2;238;238;238m\u2588'
            '\x1b[38;2;255;255;255m\u2588\n'
        )

    shades_256 = """\n
levels: 256

'-':
    ..{}@@
""".format(''.join(f'{_x:02x}' for _x in range(1, 255)))


    def test_render_blocks_256shades(self):
        """Render 1x1 blocks format, 16 ink levels"""
        font, *_ = monobit.load(get_stringio(self.shades_256))
        text = monobit.render(font, '-').as_blocks((1, 1))
        assert_text_eq(text,
            ''.join(
                f'\x1b[38;2;{_s};{_s};{_s}m\u2588'
                for _s in range(256)
            ) + '\n'
        )



if __name__ == '__main__':
    unittest.main()
