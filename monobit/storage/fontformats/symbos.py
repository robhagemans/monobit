"""
monobit.storage.fontformats.symbos - SymbOS FNT font format

(c) 2025 Michael Steil
licence: https://opensource.org/licenses/MIT
"""

# Format specification:
# - 2-byte header
#   - Byte 0: Font height in pixels (typically 6-13)
#   - Byte 1: Starting character code (0x20 = ASCII space as per specification)
# - 96 glyphs × 16 bytes each
#   - Byte 0: Glyph width in pixels (1-8)
#   - Bytes 1-15: Pixel data for 15 rows (one byte per row, 8 bits per row)
#
# Implementation notes:
# - We allow any start code and any number of glyphs when reading (permissive)
# - We always write 0x20 and exactly 96 glyphs when saving (strict, as per specification)
#
# Used by SymbOS operating system for Amstrad CPC and other Z80 machines.

import logging

from monobit.storage import loaders, savers
from monobit.storage.utils.limitations import ensure_single, ensure_levels
from monobit.core import Glyph, Font, Codepoint
from monobit.base.struct import little_endian as le
from monobit.base import FileFormatError, UnsupportedError


_SYMBOS_HEADER = le.Struct(
    height='uint8',
    start_code='uint8',
)

_GLYPH_SIZE = 16
_DEFAULT_NUM_GLYPHS = 96
_DEFAULT_START_CODE = 0x20
_MAX_ROWS = 15
_MAX_WIDTH = 8


@loaders.register(
    name='symbos',
    patterns=('*.fnt',),
)
def load_symbos(instream):
    """Load a SymbOS FNT font file."""
    header = _SYMBOS_HEADER.read_from(instream)

    logging.info(f'SymbOS FNT: height={header.height}, start_code=0x{header.start_code:02x}')

    first_codepoint = header.start_code

    if header.height < 1 or header.height > _MAX_ROWS:
        raise FileFormatError(
            f'Invalid font height: {header.height} (expected 1-{_MAX_ROWS})'
        )

    # Read glyphs until end of file (permissive: accept any count, not just 96)
    glyphs = []
    glyph_idx = 0
    while True:
        codepoint = first_codepoint + glyph_idx
        glyph_data = instream.read(_GLYPH_SIZE)

        if len(glyph_data) == 0:
            break

        if len(glyph_data) < _GLYPH_SIZE:
            raise FileFormatError(
                f'Incomplete glyph data at glyph {glyph_idx} (codepoint {codepoint}): '
                f'got {len(glyph_data)} bytes, expected {_GLYPH_SIZE}'
            )

        width = glyph_data[0]
        pixel_bytes = glyph_data[1:]

        if width > _MAX_WIDTH:
            logging.warning(
                f'Glyph {glyph_idx} (U+{codepoint:04X}): width {width} exceeds maximum {_MAX_WIDTH}'
            )
            width = _MAX_WIDTH

        # FNT format stores 15 rows but only 'height' rows are used
        used_bytes = pixel_bytes[:header.height]
        if len(used_bytes) < header.height:
            used_bytes = used_bytes + b'\x00' * (header.height - len(used_bytes))

        glyph = Glyph.from_bytes(
            used_bytes,
            width=width,
            codepoint=codepoint,
        )

        glyphs.append(glyph)
        glyph_idx += 1

    logging.info(f'Loaded {len(glyphs)} glyphs (codepoints 0x{first_codepoint:02x}-0x{first_codepoint + len(glyphs) - 1:02x})')

    extra = instream.read()
    if extra:
        logging.warning(f'Ignoring {len(extra)} extra bytes at end of file')

    font = Font(glyphs)
    font = font.modify(
        source_format='SymbOS FNT',
        spacing='proportional',
        encoding='unicode',
    )
    font = font.label(char_from='unicode')

    return font


@savers.register(linked=load_symbos)
def save_symbos(fonts, outstream, height:int=None):
    """
    Save a font to SymbOS FNT format.

    Strict output: always writes start_code 0x20 and exactly 96 glyphs (ASCII 32-127).
    """
    font = ensure_single(fonts)
    font = ensure_levels(font, 2)

    if height is None:
        height = max(glyph.height for glyph in font.glyphs if glyph.height > 0)

    if height > _MAX_ROWS:
        raise UnsupportedError(
            f'Font height {height} exceeds SymbOS FNT maximum of {_MAX_ROWS} pixels'
        )

    if height < 1:
        raise UnsupportedError('Font height must be at least 1 pixel')

    logging.info(f'Saving SymbOS FNT: height={height}, start_code=0x{_DEFAULT_START_CODE:02x}, count={_DEFAULT_NUM_GLYPHS}')

    header = _SYMBOS_HEADER(height=height, start_code=_DEFAULT_START_CODE)
    outstream.write(bytes(header))

    glyph_map = {glyph.codepoint: glyph for glyph in font.glyphs if glyph.codepoint}

    for glyph_idx in range(_DEFAULT_NUM_GLYPHS):
        codepoint_int = _DEFAULT_START_CODE + glyph_idx
        codepoint = Codepoint(codepoint_int)

        if codepoint in glyph_map:
            glyph = glyph_map[codepoint]
        else:
            logging.debug(f'Creating blank glyph for codepoint {codepoint_int}')
            glyph = Glyph.blank(width=1, height=height, codepoint=codepoint)

        if glyph.width > _MAX_WIDTH:
            logging.warning(
                f'Glyph U+{codepoint:04X}: width {glyph.width} exceeds maximum {_MAX_WIDTH}, truncating'
            )
            glyph_width = _MAX_WIDTH
        else:
            glyph_width = glyph.width

        outstream.write(bytes([glyph_width]))

        glyph_bytes = glyph.as_bytes()

        if len(glyph_bytes) < _MAX_ROWS:
            glyph_bytes = glyph_bytes + b'\x00' * (_MAX_ROWS - len(glyph_bytes))
        elif len(glyph_bytes) > _MAX_ROWS:
            logging.warning(
                f'Glyph U+{codepoint:04X}: truncating from {len(glyph_bytes)} to {_MAX_ROWS} rows'
            )
            glyph_bytes = glyph_bytes[:_MAX_ROWS]

        outstream.write(glyph_bytes)

    logging.info(f'Successfully saved {_DEFAULT_NUM_GLYPHS} glyphs')
