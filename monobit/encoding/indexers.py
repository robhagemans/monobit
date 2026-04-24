"""
monobit.encoding.indexers - codepoint indexers

(c) 2022--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""
import logging

from .base import Encoder
from ..core.labels import to_labels


class Indexer(Encoder):
    """Convert from index to ordinals."""

    def __init__(self, code_range='0-'):
        """Index converter."""
        super().__init__('index')
        # generator
        self._code_range = to_labels(code_range)
        self._name = ''
        if isinstance(code_range, str):
            self._name = code_range

    def codepoint(self, *labels):
        """Convert character to codepoint."""
        try:
            return next(self._code_range)
        except StopIteration:
            return b''

    def __repr__(self):
        """Representation."""
        return f'{type(self).__name__}("{self._name}")'

    @classmethod
    def load(cls, tbl_file):
        """Load indexer from FONTCONV .tbl file"""
        with open(tbl_file) as f:
            tbl = f.read()
        rangestr = '0x' + ',0x'.join(('-0x'.join(tbl.split('-'))).split())
        return cls(code_range=rangestr)


def find_ranges(cps, indexgen=None):
    """Find code range subject to indexer."""
    cur_start = int(cps[0])
    cur_end = cur_start
    if not indexgen:
        indexgen = iter(range(cur_start, int(cps[-1])+1))
    index = next(indexgen)
    ranges = []
    try:
        for cp in cps[1:]:
            cp = int(cp)
            if cp <= index:
                continue
            # cp > index, get next index which is higher than previous.
            # so now cp can be less, equal or higher
            index = next(indexgen)
            if cp == index:
                cur_end = cp
            else:
                ranges.append(range(cur_start, cur_end + 1))
                cur_start, cur_end = cp, cp
                while cp > index:
                    index = next(indexgen)
    except StopIteration:
        logging.debug('Indexer was exhausted')
    ranges.append(range(cur_start, cur_end + 1))
    return ranges
