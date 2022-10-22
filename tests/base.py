"""
monobit test suite
testing utilities
"""

import tempfile
import unittest
import logging
from pathlib import Path

import monobit


class BaseTester(unittest.TestCase):
    """Base class for testers."""

    logging.basicConfig(level=logging.WARNING)

    font_path = Path('tests/fonts/')

    # fonts are immutable so no problem in loading only once
    fixed4x6, *_ = monobit.load(font_path / '4x6.yaff')
    fixed4x6 = fixed4x6.label(codepoint_from='unicode')
    fixed8x16, *_ = monobit.load(font_path / '8x16.hex')

    def setUp(self):
        """Setup ahead of each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()


