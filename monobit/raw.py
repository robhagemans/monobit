"""
monobit.raw - read and write raw binary font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import ensure_stream, Glyph, Font, Typeface, ceildiv


@Typeface.loads('dos', 'bin', 'rom', 'raw', encoding=None)
def load(infile, cell=(8, 8), n_chars=None, offset=0, strike=False):
    """Load font from raw binary."""
    with ensure_stream(infile, 'rb') as instream:
        # get through the offset
        # we don't assume instream is seekable - it may be sys.stdin
        instream.read(offset)
        if strike:
            cells = _load_strike(instream, cell, n_chars)
        else:
            cells = _load_aligned(instream, cell, n_chars)
    glyphs = dict(enumerate(cells))
    return Typeface([Font(glyphs)])


@Typeface.saves('dos', 'bin', 'rom', 'raw', encoding=None)
def save(typeface, outfile):
    """Save font to raw byte-aligned binary (DOS font)."""
    if len(typeface._fonts) > 1:
        raise ValueError('Saving multiple fonts to raw binary not implemented')
    font = typeface._fonts[0]
    glyphs = font._glyphs
    # check if font is fixed-width and fixed-height
    sizes = set((_glyph.width, _glyph.height) for _glyph in glyphs.values())
    if len(sizes) > 1:
        raise ValueError('Saving proportional or variable-height font to binary not implemented')
    size = list(sizes)[0]
    # can only save numeric glyphs
    keys = [_key for _key in glyphs if isinstance(_key, int)]
    default_key = font._properties.get('default-char', None)
    non_numeric = [_key for _key in glyphs if not isinstance(_key, int) and _key != default_key]
    if non_numeric and non_numeric != []:
        logging.warning('Named glyphs not saved: {}'.format(' '.join(non_numeric)))
    try:
        default = glyphs[default_key]
    except KeyError:
        default = Glyph.empty(*size)
    with ensure_stream(outfile, 'wb') as outstream:
        for ordinal in range(0, max(keys) + 1):
            glyph = glyphs.get(ordinal, default)
            outstream.write(glyph.as_bytes())
    return typeface


def _load_strike(instream, cell, n_chars):
    """Load fixed-width font from bitmap strike."""
    width, height = cell
    # n_chars must be given for strikes
    # assume byte-aligned at end of strike only
    strike_bytes = ceildiv(n_chars * width, 8)
    rombytes = instream.read(strike_bytes * height)
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
    return cells

def _load_aligned(instream, cell, n_chars):
    """Load fixed-width font from byte-aligned bitmap."""
    width, height = cell
    width_bytes = ceildiv(width, 8)
    if n_chars is None:
        rombytes = instream.read()
    else:
        rombytes = instream.read(n_chars * width_bytes * height)
    bytesize = width_bytes * height
    # get number of chars in extract
    n_chars = ceildiv(len(rombytes), bytesize)
    # get chunks
    glyphbytes = [
        rombytes[_ord*bytesize : (_ord+1)*bytesize]
        for _ord in range(n_chars)
    ]
    # concatenate rows
    cells = [
        Glyph.from_bytes(_bytes, width)
        for _bytes in glyphbytes
    ]
    return cells
