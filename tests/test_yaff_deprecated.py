"""
monobit test suite
yaff format tests: deprecated features
"""

import os
import io
import unittest

import monobit
from monobit import Glyph, Tag, Codepoint, Char
from monobit.core.raster import Raster, get_inklevels
from .base import BaseTester, get_stringio, assert_text_eq


class TestYaffDeprecated(BaseTester):
    """Test deprecated features of the yaff format."""

    # labels

    labels = """
# unquoted tags
tag:
    .

tag.with.dots:
    .....

tag_with_underscores:
    ......

t0:
    -

# unquoted chars
b:
    ....

é:
    ...

ते:
    ..
"""

    def test_deprecated_labels(self):
        file = get_stringio(self.labels)
        f,  *_ = monobit.load(file)
        assert f.get_glyph(Tag('tag')).width == 1
        assert f.get_glyph(Tag('tag.with.dots')).width == 5
        assert f.get_glyph(Tag('tag_with_underscores')).width == 6
        assert f.get_glyph(Tag('t0')).width == 0
        assert f.get_glyph(Char('b')).width == 4
        assert f.get_glyph(Char('é')).width == 3
        assert f.get_glyph(Char('ते')).width == 2

    weird_labels = """
':
    ....
":
    .....
"""

    def test_weird_deprecated_labels(self):
        file = get_stringio(self.weird_labels)
        f,  *_ = monobit.load(file)
        assert f.get_glyph(Char("'")).width == 4
        assert f.get_glyph(Char('"')).width == 5

    multiple_labels = """
0x02:
0x03:
    ..
b:
c:
u+0020:
    ...

tag1:
tag2:
tag3:
    ....
"""

    def test_multiple_labels(self):
        file = get_stringio(self.multiple_labels)
        f,  *_ = monobit.load(file)
        assert f.glyphs[0].get_labels() == (
            Codepoint(2), Codepoint(3)
        )
        assert f.glyphs[1].get_labels() == (
            Char('b'), Char('c'), Char(' ')
        )
        assert f.glyphs[2].get_labels() == (
            Tag('tag1'), Tag('tag2'), Tag('tag3')
        )

    # properties

    props = """
average-advance: 4
max-advance: 6
cap-advance: 5
"""

    def test_properties(self):
        file = get_stringio(self.props)
        f,  *_ = monobit.load(file, allow_empty=True)
        assert f.average_width == 4
        assert f.max_width == 6
        assert f.cap_width == 5

    weird_props = """
not-a-glyph:
    ".@"
glyph:
    .@
"""

    def test_weird_properties(self):
        file = get_stringio(self.weird_props)
        f,  *_ = monobit.load(file)
        assert f.not_a_glyph == '.@'
        assert f.get_glyph('glyph').width == 2

    # glyph props

    glyphprops = """
a:
    .....
    ..@..
    .@.@.
    .@@@.
    .@.@.
    .@.@.

    offset: 1 2

b:
    .....
    .@@..
    .@.@.
    .@@..
    .@.@.
    .@@..

    tracking: 1
    kern-to:
        A 1
"""
    def test_glyph_properties(self):
        file = get_stringio(self.glyphprops)
        f,  *_ = monobit.load(file)
        a = f.get_glyph('a')
        assert a.left_bearing == 1
        assert a.shift_up == 2
        b = f.get_glyph('b')
        assert b.right_bearing == 1
        assert b.right_kerning == {Char('A'): 1}



    order = """
prop-before-glyph: before

a:
    .....
    ..@..
    .@.@.
    .@@@.
    .@.@.
    .@.@.

prop-after-glyph: after
"""

    def test_order(self):
        file = get_stringio(self.order)
        f,  *_ = monobit.load(file)
        assert f.prop_before_glyph == "before"
        assert f.prop_after_glyph == "after"
        a = f.get_glyph('a')
        assert a.height == 6


if __name__ == '__main__':
    unittest.main()
