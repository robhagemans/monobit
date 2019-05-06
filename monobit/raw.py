"""
monobit.raw - read and write raw binary font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


from .base import ensure_stream, Glyph, Font, Typeface, ceildiv


@Typeface.loads('dos', 'bin', 'rom', encoding=None)
def load(infile, cell=(8, 8), n_chars=None, offset=0, strike=False):
    """Load font from raw binary."""
    with ensure_stream(infile, 'rb') as instream:
        width, height = cell
        # read the necessary bytes
        # we don't assume instream is seekable - it may be sys.stdin
        instream.read(offset)
        full_height = height
        # width in bytes, for byte-aligned fonts
        width_bytes = ceildiv(width, 8)
        if n_chars is None:
            rombytes = instream.read()
        elif not strike:
            rombytes = instream.read(n_chars * width_bytes * full_height)
        else:
            # n_chars must be given for strikes
            # assume byte-aligned at end of strike only
            strike_bytes = ceildiv(n_chars * width, 8)
            rombytes = instream.read(strike_bytes * full_height)
        if strike:
            # flatten strikes
            rows = [
                rows[_strike*strike_bytes : (_strike+1)*strike_bytes]
                for _strike in range(height)
            ]
            # convert to bits
            drawn = [bytes_to_bits(_row) for _row in _rows]
            # clip out glyphs
            cells = [
                [_strike[_n*width:(_n+1)*width] for _strike in drawn]
                for _n in range(n_chars)
            ]
        else:
            bytesize = width_bytes * full_height
            # get number of chars in extract
            n_chars = ceildiv(len(rows), bytesize)
            # get chunks
            glyphbytes = [
                bytelist[_ord*bytesize : (_ord+1)*bytesize]
                for _ord in range(n_chars)
            ]
            # concatenate rows
            cells = [
                Glyph.from_bytes(_bytes)
                for _bytes in glyphbytes
            ]
        glyphs = dict(enumerate(cells))
        return Typeface([Font(glyphs)])


@Typeface.saves('fnt', 'bin', 'rom')
def save(typeface, outfile):
    """Save font to raw binary."""
    if len(typeface._fonts) > 1:
        raise ValueError("Saving multiple fonts to raw binary not implemented")
    font = typeface._fonts[0]
    glyphs = font._glyphs
    with ensure_stream(outfile, 'w') as outstream:
        for ordinal in range(0, max(glyphs.keys()) + 1):
            try:
                glyph = glyphs[ordinal]
            except KeyError:
                continue
            glyph_bytes = bytes(
                int(''.join(_row), 2)
                for _row in glyph._rows
            )
            outstream.write(glyph_bytes)
    return typeface
