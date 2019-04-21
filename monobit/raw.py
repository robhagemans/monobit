"""
monobit.raw - read and write raw binary font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

def _ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)

def load(
        infile, cell=(8, 8), n_chars=None,
        offset=0, padding=0, clip=0, mirror=False,
        invert=False, first=0, strike=False
    ):
    """Load font from raw binary."""
    width, height = cell
    # read the necessary bytes
    # we don't assume infile is seekable - it may be sys.stdin
    infile.read(offset)
    full_height = height + padding
    # width in bytes, for byte-aligned fonts
    width_bytes = _ceildiv(7, 8)
    if n_chars is None:
        rombytes = infile.read()
    elif not strike:
        rombytes = infile.read(n_chars * width_bytes * full_height)
    else:
        # assume byte-aligned at end of strike only
        strike_bytes = _ceildiv(n_chars * width, 8)
        rombytes = infile.read(strike_bytes * full_height)
    # extract binary representation
    rows = [u'{:08b}'.format(_c) for _c in bytearray(rombytes)]
    drawn = [
        [(_c == '1') != invert for _c in _row]
        for _row in rows
    ]
    if strike:
        # flatten strikes
        drawn = [[
                _bit
                for _byte in drawn[_strike*strike_bytes : (_strike+1)*strike_bytes]
                for _bit in _byte
            ]
            for _strike in range(height)
        ]
        cells = [
            [_strike[_n*width:(_n+1)*width] for _strike in drawn]
            for _n in range(n_chars)
        ]
    else:
        # get number of chars in extract
        n_chars = (len(rows) + padding) // full_height
        # cut raw cells out of bitmap
        cells = [
            drawn[_ord*width_bytes*full_height : (_ord+1)*width_bytes*full_height]
            for _ord in range(n_chars)
        ]
    # remove vertical padding
    cells = [
        _cell[:height*width_bytes] for _cell in cells
    ]
    # mirror if necessary
    if mirror:
        cells = [
            [_row[::-1] for _row in _char]
            for _char in cells
        ]
    # remove horizontal padding
    cells = [
        [_row[clip: clip+width] for _row in _char]
        for _char in cells
    ]
    glyphs = dict(enumerate(cells, first))
    return glyphs


def save(glyphs, outfile, format):
    """Save font to raw binary."""
    for ordinal in range(0, max(glyphs.keys()) + 1):
        try:
            glyph = glyphs[ordinal]
        except KeyError:
            continue
        glyph_bytes = bytes(
            int(''.join(_row), 2)
            for _row in glyph
        )
        outfile.write(glyph_bytes)
