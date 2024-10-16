"""
monobit.render.blocks - output pixels as text using block elements

(c) 2023--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import zip_longest

from monobit.base.binary import bytes_to_bits
from monobit.base import blockstr


# block elements

BLOCKS = {
    (1, 1): {
        (0,): ' ',
        (1,): '\u2588',
    },
    (2, 2): {
        (0, 0, 0, 0): ' ',
        (0, 0, 0, 1): '\u2597',
        (0, 0, 1, 0): '\u2596',
        (0, 0, 1, 1): '\u2584',
        (0, 1, 0, 0): '\u259d',
        (0, 1, 0, 1): '\u2590',
        (0, 1, 1, 0): '\u259e',
        (0, 1, 1, 1): '\u259f',
        (1, 0, 0, 0): '\u2598',
        (1, 0, 0, 1): '\u259a',
        (1, 0, 1, 0): '\u258c',
        (1, 0, 1, 1): '\u2599',
        (1, 1, 0, 0): '\u2580',
        (1, 1, 0, 1): '\u259c',
        (1, 1, 1, 0): '\u259b',
        (1, 1, 1, 1): '\u2588',
    },
}

# sixel block elements in Unicode do not include full- and half-block elements defined elsewhere
_SIXBITS = tuple(
    tuple(1*_b for _b in bytes_to_bits((_code,))[2:])
    for _code in range(1, 2**6-1)
    if _code not in (0b010101, 0b101010)
)
BLOCKS[(2, 3)] = {
    (_0, _1, _2, _3, _4, _5): chr(0x1Fb00 + _i)
    for _i, (_5, _4, _3, _2, _1, _0) in enumerate(_SIXBITS)
} | {
    (0, 0, 0, 0, 0, 0): ' ',
    (0, 1, 0, 1, 0, 1): '\u2590',
    (1, 0, 1, 0, 1, 0): '\u258c',
    (1, 1, 1, 1, 1, 1): '\u2588',
}

_EIGHTBITS = tuple(
    tuple(1*_b for _b in bytes_to_bits((_code,)))
    for _code in range(2**8)
)
BLOCKS[(2, 4)] = {
    (_0, _3, _1, _4, _2, _5, _6, _7): chr(0x2800 + _i)
    for _i, (_7, _6, _5, _4, _3, _2, _1, _0) in enumerate(_EIGHTBITS)
}

BLOCKS[(2, 1)] = {
    (_0, _1): BLOCKS[(2, 2)][(_0, _1, _0, _1)]
    for _0 in range(2)
    for _1 in range(2)
}

BLOCKS[(1, 2)] = {
    (_0, _1): BLOCKS[(2, 2)][(_0, _0, _1, _1)]
    for _0 in range(2)
    for _1 in range(2)
}

BLOCKS[(1, 3)] = {
    (_0, _1, _2): BLOCKS[(2, 3)][(_0, _0, _1, _1, _2, _2)]
    for _0 in range(2)
    for _1 in range(2)
    for _2 in range(2)
}

BLOCKS[(1, 4)] = {
    (_0, _1, _2, _3): BLOCKS[(2, 4)][(_0, _0, _1, _1, _2, _2, _3, _3)]
    for _0 in range(2)
    for _1 in range(2)
    for _2 in range(2)
    for _3 in range(2)
}


def matrix_to_blocks(matrix, ncols, nrows):
    """Convert bit matrix to a matrix of block characters."""
    try:
        blockdict = BLOCKS[(ncols, nrows)]
    except KeyError:
        raise ValueError(f'Unsupported block resolution: {ncols}x{nrows}')
    bitblockrows = tuple(
        tuple(
            _bitblock
            for _bitblock in zip_longest(
                *(
                    _bitrows[_row][_col::ncols]
                    for _row in range(nrows)
                    for _col in range(ncols)
                ),
                fillvalue=0
            )
        )
        for _bitrows in zip_longest(
            *(matrix[_ofs::nrows] for _ofs in range(nrows)), fillvalue=()
        )
    )
    block_matrix = [
        [blockdict[_bitblock] for _bitblock in _row]
        for _row in bitblockrows
    ]
    return block_matrix


def matrix_to_shades(matrix, *, inklevels, border):
    """Convert bit matrix to a mutable matrix of block characters."""
    return [
        [
            _get_shaded_block(_bitblock, inklevels, border)
            for _bitblock in _row
        ]
        for _row in matrix
    ]


def _get_shaded_block(value, inklevels, border):
    """Get block with given shade."""
    shade = inklevels[value] if value >= 0 else border
    if shade is None:
        return f'\x1b[0m '
    r, g, b = shade
    # Get ansi-escape code for RGB colour
    return f'\x1b[38;2;{r};{g};{b}m\u2588\x1b[0m'
