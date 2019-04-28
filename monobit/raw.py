"""
monobit.raw - read and write raw binary font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


from .base import ensure_stream, Font, ceildiv


@Font.loads('fnt', 'bin', 'rom')
def load(
        infile, cell=(8, 8), n_chars=None,
        offset=0, padding=0, clip=0, mirror=False,
        invert=False, first=0, strike=False
    ):
    """Load font from raw binary."""
    with ensure_stream(infile, 'rb') as instream:
        width, height = cell
        # read the necessary bytes
        # we don't assume instream is seekable - it may be sys.stdin
        instream.read(offset)
        full_height = height + padding
        # width in bytes, for byte-aligned fonts
        width_bytes = ceildiv(width, 8)
        if n_chars is None:
            rombytes = instream.read()
        elif not strike:
            rombytes = instream.read(n_chars * width_bytes * full_height)
        else:
            # assume byte-aligned at end of strike only
            strike_bytes = ceildiv(n_chars * width, 8)
            rombytes = instream.read(strike_bytes * full_height)
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
            n_chars = (len(rows) + padding) // (width_bytes*full_height)
            # cut raw cells out of bitmap
            cells = [
                drawn[_ord*width_bytes*full_height : (_ord+1)*width_bytes*full_height]
                for _ord in range(n_chars)
            ]
            # concatenate rows
            cells = [
                [
                    [_bit for _byte in _cell[_row*width_bytes:(_row+1)*width_bytes] for _bit in _byte]
                    for _row in range(height)
                ]
                for _cell in cells
            ]
        # remove vertical padding
        cells = [
            _cell[:height] for _cell in cells
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
        return Font(glyphs)


@Font.saves('fnt', 'bin', 'rom')
def save(font, outfile, format):
    """Save font to raw binary."""
    glyphs = font._glyphs
    with ensure_stream(outfile, 'w') as outstream:
        for ordinal in range(0, max(glyphs.keys()) + 1):
            try:
                glyph = glyphs[ordinal]
            except KeyError:
                continue
            glyph_bytes = bytes(
                int(''.join(_row), 2)
                for _row in glyph
            )
            outstream.write(glyph_bytes)
