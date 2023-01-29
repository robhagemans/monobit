"""
monobit test suite
testing utilities
"""

import tempfile
import unittest
import logging
import io
from pathlib import Path

import monobit


def get_stringio(string):
    """Workaround as our streams objetcs require a buffer."""
    return io.TextIOWrapper(get_bytesio(string.encode()))

def get_bytesio(bytestring):
    """Workaround as our streams objects require a buffer."""
    return io.BufferedReader(io.BytesIO(bytestring))


class BaseTester(unittest.TestCase):
    """Base class for testers."""

    logging.basicConfig(level=logging.WARNING)

    font_path = Path('tests/fonts/')

    # fonts are immutable so no problem in loading only once
    fixed4x6, *_ = monobit.load(font_path / '4x6.yaff')
    fixed4x6 = fixed4x6.label(codepoint_from='unicode')
    fixed8x16, *_ = monobit.load(font_path / '8x16.hex')

    fixed4x6_A = """\
.@.
@.@
@@@
@.@
@.@
"""

    fixed8x16_A = """\
..@@..
..@@..
@@..@@
@@..@@
@@@@@@
@@@@@@
@@..@@
@@..@@
@@..@@
@@..@@
"""

    def setUp(self):
        """Setup ahead of each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()
