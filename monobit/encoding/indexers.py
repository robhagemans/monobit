"""
monobit.encoding.indexers - codepoint indexers

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import Encoder
from ..core.labels import to_labels


class Indexer(Encoder):
    """Convert from index to ordinals."""

    def __init__(self, code_range='0-'):
        """Index converter."""
        super().__init__('index')
        # generator
        self._code_range = to_labels(code_range)

    @staticmethod
    def char(*labels):
        """Convert codepoint to character, return empty string if missing."""
        raise TypeError('Can only use Indexer to set codepoints, not character labels.')

    def codepoint(self, *labels):
        """Convert character to codepoint."""
        try:
            return next(self._code_range)
        except StopIteration:
            return b''

    def __repr__(self):
        """Representation."""
        return type(self).__name__ + '()'

    @classmethod
    def load(cls, tbl_file):
        """Load indexer from FONTCONV .tbl file"""
        with open(tbl_file) as f:
            tbl = f.read()
        rangestr = '0x' + ',0x'.join(('-0x'.join(tbl.split('-'))).split())
        return cls(code_range=rangestr)
