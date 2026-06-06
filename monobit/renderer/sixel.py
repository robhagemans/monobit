"""
monobit.renderer.sixel - output pixels to terminal through sixel escape codes

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import zip_longest

from .blocks import bit_block_rows


def bits_to_sixel(bits):
    """Convert six bits to sixel character."""
    bits = ''.join(str(int(_b)) for _b in bits)
    byte = int(bits[::-1], base=2)
    return chr(ord('?') + byte)


def matrix_to_sixel(matrix, *, inklevels, border):
    """Convert bit matrix to sixel/characters."""
    bitblockrows = bit_block_rows(matrix, nrows=6, ncols=1)
    sixel_matrices = {}
    border = border or inklevels[0]
    for level, (r, g, b) in enumerate((border, *inklevels), -1):
        sixel_matrices[r, g, b] = [
            ''.join(
                bits_to_sixel(_b == level for _b in _bitblock)
                for _bitblock in _row
            )
            for _row in bitblockrows
        ]
    seq = [
        f'#{level};2;{(r*100)//255};{(g*100)//255};{(b*100)//255};'
        for level, (r, g, b) in enumerate(sixel_matrices.keys())
    ]
    for sixel_rows in zip(*sixel_matrices.values()):
        seq.append(
            '$'.join(
                f'#{_level}'
                + ''.join(_row) for _level, _row in enumerate(sixel_rows)
            )
            + '-'
        )
    return '\x1bPq' + ''.join(seq) + '\x1b\\'
