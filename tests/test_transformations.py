"""
monobit test suite
glyph transformation tests
"""

import os
import io
import unittest

import monobit
from monobit import Glyph
from .base import BaseTester, get_stringio


test = """
# testing glyph
"1":
  ........
  ........
  ...@@...
  ..@@@...
  .@@@@...
  ...@@...
  ...@@...
  ...@@...
  ...@@...
  ...@@...
  ...@@...
  ...@@...
  .@@@@@@.
  ........
  ........
  ........

  shift-up: -3
  shift-left: 1
  left-bearing: 1
  top-bearing: -1
  bottom-bearing: -2
  test: 5
"""

class TestGlyphTrafo(BaseTester):
    """Test glyph transformations."""

    def test_mirror(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.mirror()
        assert m.as_text() == '\n'.join((
            '........',
            '........',
            '...@@...',
            '...@@@..',
            '...@@@@.',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '.@@@@@@.',
            '........',
            '........',
            '........\n',
        )), m
        # metrics
        # changed
        assert m.shift_left == -one.shift_left
        assert m.right_bearing == one.left_bearing
        assert m.left_bearing == one.right_bearing
        # unchanged
        assert m.shift_up == one.shift_up
        assert m.top_bearing == one.top_bearing
        assert m.bottom_bearing == one.bottom_bearing
        # non-metrics preserved
        assert m.test == one.test
        assert m.comment == one.comment


    def test_flip(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.flip()
        assert m.as_text() == '\n'.join((
              '........',
              '........',
              '........',
              '.@@@@@@.',
              '...@@...',
              '...@@...',
              '...@@...',
              '...@@...',
              '...@@...',
              '...@@...',
              '...@@...',
              '.@@@@...',
              '..@@@...',
              '...@@...',
              '........',
              '........\n',
        )), m
        # metrics
        # unchanged
        assert m.shift_left == one.shift_left
        assert m.right_bearing == one.right_bearing
        assert m.left_bearing == one.left_bearing
        # changed
        assert m.shift_up == -one.height-one.shift_up
        assert m.top_bearing == one.bottom_bearing
        assert m.bottom_bearing == one.top_bearing
        # non-metrics preserved
        assert m.test == one.test
        assert m.comment == one.comment

    def test_turn(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.turn()
        assert m.as_text() == '\n'.join((
            '................',
            '...@.......@....',
            '...@.......@@...',
            '...@@@@@@@@@@@..',
            '...@@@@@@@@@@@..',
            '...@............',
            '...@............',
            '................\n',
        )), m
        # metrics
        assert m.right_bearing == one.top_bearing
        assert m.left_bearing == one.bottom_bearing
        assert m.top_bearing == one.left_bearing
        assert m.bottom_bearing == one.right_bearing
        assert m.shift_left == -one.height//2 - one.shift_up
        assert m.shift_up == -one.width//2 + one.shift_left
        # non-metrics preserved
        assert m.test == one.test
        assert m.comment == one.comment

    def test_turn2(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.turn(2)
        assert m.as_text() == '\n'.join((
            '........',
            '........',
            '........',
            '.@@@@@@.',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@@@.',
            '...@@@..',
            '...@@...',
            '........',
            '........\n'
        )), m
        # metrics
        assert m.right_bearing == one.left_bearing
        assert m.left_bearing == one.right_bearing
        assert m.top_bearing == one.bottom_bearing
        assert m.bottom_bearing == one.top_bearing
        # TODO: is this also correct for odd size glyphs?
        assert m.shift_left == -one.shift_left
        assert m.shift_up == -one.height - one.shift_up
        # non-metrics preserved
        assert m.test == one.test
        assert m.comment == one.comment

    def test_turn3(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.turn(3)
        assert m.as_text() == '\n'.join((
            '................',
            '............@...',
            '............@...',
            '..@@@@@@@@@@@...',
            '..@@@@@@@@@@@...',
            '...@@.......@...',
            '....@.......@...',
            '................\n',
        )), m
        # metrics
        assert m.right_bearing == one.bottom_bearing
        assert m.left_bearing == one.top_bearing
        assert m.top_bearing == one.right_bearing
        assert m.bottom_bearing == one.left_bearing
        assert m.shift_left == one.height//2 + one.shift_up
        assert m.shift_up == -one.width//2 - one.shift_left
        # non-metrics preserved
        assert m.test == one.test
        assert m.comment == one.comment

    def test_turn_equalities(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        assert one.turn(4) == one
        assert one.turn(1).turn(-1) == one
        assert one.turn(2).turn(-2) == one
        assert one.turn(3).turn(-3) == one
        assert one.turn().turn().turn().turn() == one
        assert one.turn(2) == one.turn().turn()
        assert one.turn(3) == one.turn().turn().turn()

    def test_reduce(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.reduce()
        assert m.as_text() == '\n'.join((
            '..@@..',
            '.@@@..',
            '@@@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up + one.padding.bottom

    def test_expand(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.expand(1, 1, 1, 1)
        assert m.as_text() == '\n'.join((
            '..........',
            '..........',
            '..........',
            '....@@....',
            '...@@@....',
            '..@@@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '..@@@@@@..',
            '..........',
            '..........',
            '..........',
            '..........\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up - 1

    def test_stretch(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.stretch(2, 1)
        assert m.as_text() == '\n'.join((
            '................',
            '................',
            '......@@@@......',
            '....@@@@@@......',
            '..@@@@@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '..@@@@@@@@@@@@..',
            '................',
            '................',
            '................\n',
        )), m
        assert m.advance_width == one.advance_width * 2
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up

    def test_shrink(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.shrink(2, 2)
        assert m.as_text() == '\n'.join((
            '....',
            '..@.',
            '.@@.',
            '..@.',
            '..@.',
            '..@.',
            '.@@@',
            '....\n',
        )), m
        assert m.advance_width == one.advance_width // 2
        assert m.advance_height == one.advance_height // 2
        assert m.shift_up == one.shift_up // 2

    def test_inflate(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.inflate()
        assert m.as_text() == '\n'.join((
            '.........',
            '.........',
            '....@@...',
            '...@@@...',
            '..@@@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '..@@@@@@.',
            '.........',
            '.........',
            '.........\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up
        # shift_left is unaffected here as 9//2 == 8//2

    def test_outline(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.reduce().outline()
        assert m.as_text() == '\n'.join((
            '..@@@@..',
            '.@@..@..',
            '@@...@..',
            '@....@..',
            '@@@..@..',
            '..@..@..',
            '..@..@..',
            '..@..@..',
            '..@..@..',
            '..@..@..',
            '@@@..@@@',
            '@......@',
            '@@@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == -1
        assert m.shift_left == 1

    def test_overlay(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.overlay(one.mirror().reduce())
        # note that glyph is not positioned in middle of advance
        assert m.as_text() == '\n'.join((
            '........',
            '........',
            '..@@@...',
            '..@@@...',
            '.@@@@@..',
            '..@@@...',
            '..@@@...',
            '..@@@...',
            '..@@@...',
            '..@@@...',
            '..@@@...',
            '..@@@...',
            '@@@@@@@.',
            '........',
            '........',
            '........\n',
        )), m
        # symmetric version
        one = one.modify(right_bearing=1)
        m = one.overlay(one.mirror().reduce())
        assert m.as_text() == '\n'.join((
            '........',
            '........',
            '...@@...',
            '..@@@@..',
            '.@@@@@@.',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '.@@@@@@.',
            '........',
            '........',
            '........\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up
        assert m.shift_left == one.shift_left

    def test_shear(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.shear(pitch=(2, 5)).reduce()
        # if metrics are correct, prior reduce should make no difference
        assert m == one.reduce().shear(pitch=(2, 5)).reduce()
        assert m.as_text() == '\n'.join((
            '......@@',
            '....@@@.',
            '...@@@@.',
            '....@@..',
            '....@@..',
            '....@@..',
            '...@@...',
            '...@@...',
            '..@@....',
            '..@@....',
            '@@@@@@..\n',
        )), m

    def test_shear_left(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.shear(pitch=(2, 5), direction='l').reduce()
        # if metrics are correct, prior reduce should make no difference
        assert m == one.reduce().shear(pitch=(2, 5), direction='l').reduce()
        assert m.as_text() == '\n'.join((
            '.@@......',
            '.@@@.....',
            '@@@@.....',
            '...@@....',
            '...@@....',
            '...@@....',
            '....@@...',
            '....@@...',
            '.....@@..',
            '.....@@..',
            '...@@@@@@\n',
        )), m

    def test_shear_unreduced(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.shear(pitch=(1, 2))
        assert m.as_text() == '\n'.join((
            '...............',
            '...............',
            '..........@@...',
            '........@@@....',
            '.......@@@@....',
            '........@@.....',
            '........@@.....',
            '.......@@......',
            '.......@@......',
            '......@@.......',
            '......@@.......',
            '.....@@........',
            '...@@@@@@......',
            '...............',
            '...............',
            '...............\n',
        )), m

    def test_underline(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.underline(descent=2)
        assert m.as_text() == '\n'.join((
            '........',
            '........',
            '...@@...',
            '..@@@...',
            '.@@@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '.@@@@@@.',
            '........',
            '@@@@@@@@',
            '........\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up
        assert m.shift_left == one.shift_left


    def test_underline_thickness(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.underline(descent=4, thickness=2)
        assert m.as_text() == '\n'.join((
            '........',
            '........',
            '...@@...',
            '..@@@...',
            '.@@@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '.@@@@@@.',
            '........',
            '........',
            '........',
            '@@@@@@@@',
            '@@@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up-2
        assert m.shift_left == one.shift_left


    def test_smear(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        m = one.reduce().smear()
        assert m.as_text() == '\n'.join((
            '..@@@..',
            '.@@@@..',
            '@@@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '@@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up + one.padding.bottom


class TestFontTrafo:
    """Test applying the transformation to the whole font."""

    def test_font_smear(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.smear()
        m = f.glyphs[0].reduce()
        assert m.as_text() == '\n'.join((
            '..@@@..',
            '.@@@@..',
            '@@@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '..@@@..',
            '@@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up + one.padding.bottom

    def test_font_shear(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.shear(pitch=(2, 5))
        m = f.glyphs[0].reduce()
        # if metrics are correct, prior reduce should make no difference
        assert m == one.reduce().shear(pitch=(2, 5)).reduce()
        assert m.as_text() == '\n'.join((
            '......@@',
            '....@@@.',
            '...@@@@.',
            '....@@..',
            '....@@..',
            '....@@..',
            '...@@...',
            '...@@...',
            '..@@....',
            '..@@....',
            '@@@@@@..\n',
        )), m

    def test_font_underline(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.underline(descent=2)
        m = f.glyphs[0].reduce()
        assert m.as_text() == '\n'.join((
            '...@@...',
            '..@@@...',
            '.@@@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '...@@...',
            '.@@@@@@.',
            '........',
            '@@@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up
        assert m.shift_left == one.shift_left


    def test_reduce(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.reduce()
        m = f.glyphs[0]
        assert m.as_text() == '\n'.join((
            '..@@..',
            '.@@@..',
            '@@@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '..@@..',
            '@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up + one.padding.bottom

    def test_expand(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.expand(1, 1, 1, 1)
        m = f.glyphs[0]
        assert m.as_text() == '\n'.join((
            '..........',
            '..........',
            '..........',
            '....@@....',
            '...@@@....',
            '..@@@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '....@@....',
            '..@@@@@@..',
            '..........',
            '..........',
            '..........',
            '..........\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up - 1

    def test_stretch(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.stretch(2, 1)
        m = f.glyphs[0]
        assert m.as_text() == '\n'.join((
            '................',
            '................',
            '......@@@@......',
            '....@@@@@@......',
            '..@@@@@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '......@@@@......',
            '..@@@@@@@@@@@@..',
            '................',
            '................',
            '................\n',
        )), m
        assert m.advance_width == one.advance_width * 2
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up

    def test_shrink(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.shrink(2, 2)
        m = f.glyphs[0]
        assert m.as_text() == '\n'.join((
            '....',
            '..@.',
            '.@@.',
            '..@.',
            '..@.',
            '..@.',
            '.@@@',
            '....\n',
        )), m
        assert m.advance_width == one.advance_width // 2
        assert m.advance_height == one.advance_height // 2
        assert m.shift_up == one.shift_up // 2

    def test_inflate(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.inflate()
        m = f.glyphs[0]
        assert m.as_text() == '\n'.join((
            '.........',
            '.........',
            '....@@...',
            '...@@@...',
            '..@@@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '....@@...',
            '..@@@@@@.',
            '.........',
            '.........',
            '.........\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up
        # shift_left is unaffected here as 9//2 == 8//2

    def test_outline(self):
        file = get_stringio(test)
        f,  *_ = monobit.load(file)
        one = f.glyphs[0]
        f = f.outline()
        m = f.glyphs[0].reduce()
        assert m.as_text() == '\n'.join((
            '..@@@@..',
            '.@@..@..',
            '@@...@..',
            '@....@..',
            '@@@..@..',
            '..@..@..',
            '..@..@..',
            '..@..@..',
            '..@..@..',
            '..@..@..',
            '@@@..@@@',
            '@......@',
            '@@@@@@@@\n',
        )), m
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == -1
        assert m.shift_left == 1


if __name__ == '__main__':
    unittest.main()
