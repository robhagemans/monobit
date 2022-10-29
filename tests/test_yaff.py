"""
monobit test suite
yaff format tests
"""

import os
import io
import unittest

import monobit
from monobit import Glyph, Tag, Codepoint, Char
from .base import BaseTester

def get_stringio(string):
    """Workaround as our streams require a buffer to be available."""
    return io.TextIOWrapper(
        io.BufferedReader(io.BytesIO(string.encode()))
    )


class TestYaff(BaseTester):
    """Test the yaff format."""


    empty = """
empty:
    -
"""

    def test_empty_glyph(self):
        file = get_stringio(self.empty)
        f,  *_ = monobit.load(file)
        assert len(f.glyphs) == 1, repr(f.glyphs)
        assert f.raster_size == (0, 0), f.raster_size

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


if __name__ == '__main__':
    unittest.main()
