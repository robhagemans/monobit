"""
monobit test suite
yaff format tests
"""

import os
import io
import unittest

import monobit
from monobit import Glyph, Tag, Codepoint, Char
from .base import BaseTester, get_stringio


class TestYaff(BaseTester):
    """Test the yaff format."""

    # glyph definitions

    empty = """
empty:
    -
"""

    def test_empty_glyph(self):
        file = get_stringio(self.empty)
        f,  *_ = monobit.load(file)
        assert len(f.glyphs) == 1, repr(f.glyphs)
        assert f.raster_size == (0, 0), f.raster_size

    glyphs = """
a:
    .....
    ..@..
    .@.@.
    .@@@.
    .@.@.
    .@.@.
b:
    .....
    .@@..
    .@.@.
    .@@..
    .@.@.
    .@@..
"""

    def test_glyphs(self):
        file = get_stringio(self.glyphs)
        f,  *_ = monobit.load(file)
        a = f.get_glyph('a')
        assert a.width == 5
        assert a.height == 6
        assert a.advance_width == 5
        assert f.spacing == 'character-cell'
        assert f.line_height == 6


    # font sections

    sections = """
---
a:
    ..
---
a:
    @@
"""

    def test_sections(self):
        file = get_stringio(self.sections)
        pack = monobit.load(file)
        assert len(pack) == 2, repr(pack)

    # labels

    labels = """
tag:
    .
0x01:
    ..
u+0001:
    ...
"a":
    ..
    ..
'a':
    .
    .
b:
    ....
"""

    def test_labels(self):
        file = get_stringio(self.labels)
        f,  *_ = monobit.load(file)
        assert f.get_glyph(Tag('tag')).width == 1
        assert f.get_glyph(Codepoint(b'\1')).width == 2
        assert f.get_glyph(Char('\1')).width == 3
        assert f.get_glyph(Char('a')).width == 1
        assert f.get_glyph(Tag('a')).width == 2
        assert f.get_glyph(Char('b')).width == 4

    composite_labels = """
0x01, 0x02:
    .
0x0103:
    ..
u+0001, u+0002:
    ...
u+0001,u+0003:
    ....
"""

    def test_composite_labels(self):
        file = get_stringio(self.composite_labels)
        f,  *_ = monobit.load(file)
        assert f.get_glyph(Codepoint(b'\1\2')).width == 1
        assert f.get_glyph(Codepoint(b'\1\3')).width == 2
        assert f.get_glyph(Char('\1\2')).width == 3
        assert f.get_glyph(Char('\1\3')).width == 4

    weird_labels = """
':':
    .
":":
    ..
',':
    ...
':
    ....
":
    .....
:
    ......
"""

    def test_weird_labels(self):
        file = get_stringio(self.weird_labels)
        f,  *_ = monobit.load(file)
        assert f.get_glyph(Char(':')).width == 1
        assert f.get_glyph(Tag(':')).width == 2
        assert f.get_glyph(Char(',')).width == 3
        assert f.get_glyph(Char("'")).width == 4
        assert f.get_glyph(Char('"')).width == 5
        assert not f.glyphs[5].get_labels()

    multiple_labels = """
0x01:
a:
tag_a:
    .
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
            Codepoint(1), Char('a'), Tag('tag_a')
        )
        assert f.glyphs[1].get_labels() == (
            Codepoint(2), Codepoint(3)
        )
        assert f.glyphs[2].get_labels() == (
            Char('b'), Char('c'), Char(' ')
        )
        assert f.glyphs[3].get_labels() == (
            Tag('tag1'), Tag('tag2'), Tag('tag3')
        )

    # properties

    props = """
unknown: 2
left-bearing: 1
tracking: 3
"""

    def test_properties(self):
        file = get_stringio(self.props)
        f,  *_ = monobit.load(file)
        # recognised property
        assert f.left_bearing == 1
        # compatibility synonym
        assert f.right_bearing == 3
        # unknown property
        assert f.unknown == '2'

    multiline = """
single-line:  single line
multi-line:
    this is a
    "  multiline  "
    property
"""

    def test_multiline_properties(self):
        file = get_stringio(self.multiline)
        f,  *_ = monobit.load(file)
        assert f.single_line == 'single line'
        assert f.multi_line == 'this is a\n  multiline  \nproperty'

    weird_props = """
has-colon: ::myprop
at-end: "myprop:"
not-a-glyph:
    ".@"
glyph:
    .@
"""

    def test_weird_properties(self):
        file = get_stringio(self.weird_props)
        f,  *_ = monobit.load(file)
        assert f.has_colon == '::myprop'
        assert f.at_end == 'myprop:'
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
    prop: value
    multiline:
        another value

b:
    .....
    .@@..
    .@.@.
    .@@..
    .@.@.
    .@@..

    other-prop: also a value
"""
    def test_glyph_properties(self):
        file = get_stringio(self.glyphprops)
        f,  *_ = monobit.load(file)
        a = f.get_glyph('a')
        assert a.prop == 'value'
        assert a.multiline == 'another value'
        assert f.get_glyph('b').other_prop == 'also a value'

    # comments

    comments = """
# this is the top comment
#
# this too

# even this

# but this is not
property: value
another_property: value
# property comment
# spanning two lines
commented-property: 1

# glyph comment
glyph:
    -
"""
    def test_comments(self):
        file = get_stringio(self.comments)
        f,  *_ = monobit.load(file)
        assert f.get_comment() == (
            'this is the top comment\n\n'
            'this too\n\n'
            'even this'
        ), repr(f.get_comment())
        assert f.get_comment('property') == 'but this is not', repr(f.get_comment('property'))
        assert f.get_comment('another-property') == ''
        assert f.get_comment('commented-property') == (
            'property comment\nspanning two lines'
        ), repr(f.get_comment('commented-property'))
        assert f.glyphs[0].comment == 'glyph comment'


if __name__ == '__main__':
    unittest.main()
