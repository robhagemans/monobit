"""
monobit.raw - read and write raw binary font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

def load(
        infile, cell=(8, 8), n_chars=None,
        offset=0, padding=0, clip=0, mirror=False,
        invert=False, first=0,
    ):
    """Load font from raw binary."""
    width, height = cell
    # read the necessary bytes
    # we don't assume infile is seekable - it may be sys.stdin
    infile.read(offset)
    full_height = height + padding
    if n_chars is None:
        rombytes = infile.read()
    else:
        rombytes = infile.read(full_height * n_chars)
    # extract binary representation
    rows = [u'{:08b}'.format(_c) for _c in bytearray(rombytes)]
    drawn = [
        [(_c == '1') != invert for _c in _row]
        for _row in rows
    ]
    # get number of chars in extract
    n_chars = (len(rows) + padding) // full_height
    width_bytes = (width+7) // 8
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
