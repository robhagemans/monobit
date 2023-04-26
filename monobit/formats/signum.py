"""
monobit.formats.signum - Signum! 2 editor and printer font formats

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..struct import big_endian as be
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from ..magic import FileFormatError
from ..binary import ceildiv, bytes_to_bits


# editor font
_E24_MAGIC = b'eset0001'
# printer fonts
_L30_MAGIC = b'ls300001'
_P24_MAGIC = b'ps240001'
_P9_MAGIC = b'ps090001'

_SIGNUM_RANGE = range(127)

_PARAMS = {
    _E24_MAGIC: dict(
        fixed_byte_width=2,
        # guess based on file contents
        baseline=18,
        line_height=24,
        # just use standard here?
        dpi=None,
    ),
    # below settings taken from
    # https://github.com/Xiphoseer/sdo-tool/blob/main/crates/signum/src/chsets/printer.rs
    _L30_MAGIC: dict(
        fixed_byte_width=None,
        baseline=48,
        line_height=52,
        dpi=(300, 300),
    ),
    _P24_MAGIC: dict(
        fixed_byte_width=None,
        baseline=58,
        line_height=64,
        dpi=(300, 300),
    ),
    _P9_MAGIC: dict(
        fixed_byte_width=None,
        baseline=36,
        line_height=48,
        dpi=(300, 300),
    ),
}


@loaders.register(
    name='signum',
    magic=(_E24_MAGIC, _L30_MAGIC, _P9_MAGIC, _P24_MAGIC),
    patterns=('*.e24', '*.l30', '*.p9', '*.p24'),
)
def load_signum(instream):
    """Load font from signum file."""
    magic = instream.peek(8)[:8]
    try:
        params = _PARAMS[magic]
    except KeyError:
        raise FileFormatError(
            'Not a Signum file: signature {magic} does not match'
        )
    return _read_signum(instream, **params)


################################################################################
# signum binary formats

# file format reverse-engineered and documented by Xiphoseer
# https://sdo.dseiler.eu/formats/eset

_HEADER = be.Struct(
    magic='8s',
    # font type, or number of chars? should be 128
    font_type='uint32',
    # mysterious 128 bytes.
    # usually the first 64 are fairly dense and more or less random
    # but sometimes they are text or null
    # followed by 6 bytes that are almost always 0x2710 (10000), 0x000d, 0x23bc
    # followed by 58 nulls
    something='128s',
    buffer_size='uint32',
    # offset table, which we'll ignore
    offsets=(be.uint32 * 127)
)

_GLYPH_HEADER = be.Struct(
    top='uint8',
    height='uint8',
    width='uint8',
    reserved='uint8',
)

def _read_signum(instream, fixed_byte_width, baseline, line_height, dpi):
    """Read Signum! printer binary file and return glyphs."""
    data = instream.read()
    header = _HEADER.from_bytes(data)
    ofs = _HEADER.size
    glyphs = []
    for cp in _SIGNUM_RANGE:
        glyph_header = _GLYPH_HEADER.from_bytes(data, ofs)
        ofs += _GLYPH_HEADER.size
        # printer fonts provide byte width in width field
        # whereas editor files provide advance width
        if fixed_byte_width:
            bytewidth = fixed_byte_width
            advance = glyph_header.width
        else:
            bytewidth = glyph_header.width
            # we'll adjust this later based on actual padding
            advance = bytewidth * 8
        bytesize = glyph_header.height * bytewidth
        glyph_bytes = data[ofs:ofs+bytesize]
        ofs += bytesize
        notes = ''
        if glyph_header.reserved:
            notes = f'header_padding=0x{glyph_header.reserved:02x}'
        if (bytesize % 2):
            pad = data[ofs]
            logging.debug(f'glyph {cp:02x} padding byte {pad:02x}')
            ofs += 1
            if pad:
                notes += (' ' if notes else '') + f'padding=0x{pad:02x}'
        if not glyph_bytes:
            if not notes:
                continue
            glyph = Glyph(
                codepoint=cp,
                signum=notes if notes else None,
            )
        else:
            glyph = Glyph.from_bytes(
                glyph_bytes,
                width=8*bytewidth,
                codepoint=cp,
                shift_up=baseline-glyph_header.top-glyph_header.height,
                right_bearing=advance-8*bytewidth,
                signum=notes if notes else None,
            )
            # as the width in printer fonts is given in bytes, not pixels,
            # these seem to have no information about advance width.
            # from actual files it looks reasonable to preserve only left bearing
            # it is unclear how the advance width of whitespace is determined
            # perhaps this is encoded in the unknown parts of the file header
            # pylint: disable=no-member
            glyph = glyph.crop(
                right=glyph.padding.right,
                adjust_metrics=bool(fixed_byte_width)
            )
        glyphs.append(glyph)
    return Font(glyphs, line_height=line_height, dpi=dpi)
