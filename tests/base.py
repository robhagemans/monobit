"""
monobit test suite
testing utilities
"""

import tempfile
import unittest
import logging
import io
from pathlib import Path
from urllib.request import urlretrieve

import monobit
from monobit.storage import get_stringio



def ensure_asset(urlbase, name):
    """Download non-redistributable testing assets."""
    dir = Path('tests/fonts/downloads')
    target = dir / name
    if not target.exists():
        dir.mkdir(parents=True, exist_ok=True)
        urlretrieve(urlbase + name, filename=target)
    return target


def assert_text_eq(text, model):
    assert text == model, f'"""\\\n{text}"""\n != \n"""\\\n{model}"""'


class BaseTester(unittest.TestCase):
    """Base class for testers."""

    logging.basicConfig(level=logging.WARNING)

    font_path = Path('tests/fonts/')

    # fonts are immutable so no problem in loading only once
    fixed4x6, *_ = monobit.load(font_path / '4x6.yaff')
    fixed4x6 = fixed4x6.label(codepoint_from='unicode')
    fixed8x16, *_ = monobit.load(font_path / '8x16.hex')
    hershey, *_ = monobit.load(font_path / 'hershey' / 'hershey-az.jhf')

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

    fixed6x13_A = """\
..@..
.@.@.
@...@
@...@
@...@
@@@@@
@...@
@...@
@...@
"""

    hershey_A_path = '\n'.join((
        'm 5 9', 'm 0 5', 'l -4 -9', 'm 4 9', 'l 4 -9', 'm -6 3', 'l 4 0'
    ))


    def setUp(self):
        """Setup ahead of each test."""
        bar = '-' * 20
        logging.debug('%s %s %s', bar, self.id(), bar)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()
