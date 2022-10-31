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

testfont = """

a:
     ...@.
     .....
     ...@.
     .....
     @@@@@
     .....
     ...@.

     shift-up: -2
     left-bearing: 1
     top-bearing: 2
     shift-left: 1

b:
     @@..@@
     @@...@
     ....@.
     ......
     ....@.
     ......
     @@@@@@
     ......
     @...@@

     shift-up: -2
     shift-left: 1
"""

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

class TestYaff(BaseTester):
    """Test the yaff format."""

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
        ))
        assert m.advance_width == one.advance_width
        assert m.advance_height == one.advance_height
        assert m.shift_up == one.shift_up + one.padding.bottom


if __name__ == '__main__':
    unittest.main()
