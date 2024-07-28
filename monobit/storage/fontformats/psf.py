"""
monobit.storage.formats.psf - PC Screen Font format

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.base.binary import ceildiv
from monobit.base.struct import bitfield, flag, little_endian as le
from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph

from .raw import load_bitmap
from monobit.storage.utils.limitations import ensure_single, ensure_charcell


# PSF formats:
# https://www.win.tue.nl/~aeb/linux/kbd/font-formats-1.html


# mode field
#_PSF1_MAXMODE = 0x05
_PSF1_MODE = le.Struct(
    # 0x01
    PSF1_MODE512=flag,
    # 0x02
    PSF1_MODEHASTAB=flag,
    # 0x04
    PSF1_MODEHASSEQ=flag,
    #unused=bitfield('uint8', 5),
)

# PSF1 header
_PSF1_MAGIC = b'\x36\x04'
_PSF1_HEADER = le.Struct(
    mode=_PSF1_MODE,
    charsize='uint8',
)

_PSF1_SEPARATOR = b'\xFF\xFF'
_PSF1_STARTSEQ =  b'\xFF\xFE'


# flags field
_PSF2_FLAGS = le.Struct(
    # 0x01
    PSF2_HAS_UNICODE_TABLE=bitfield('uint32', 1),
    #unused=bitfield('uint32', 31),
)


# PSF2 header
_PSF2_MAGIC = b'\x72\xb5\x4a\x86'
_PSF2_HEADER = le.Struct(
    version='uint32',
    headersize='uint32',
    flags=_PSF2_FLAGS,
    length='uint32',
    charsize='uint32',
    height='uint32',
    width='uint32',
)

# max version recognized so far
#_PSF2_MAXVERSION = 0

#/* UTF8 separators */
_PSF2_SEPARATOR = b'\xFF'
_PSF2_STARTSEQ = b'\xFE'


@loaders.register(
    name='psf',
    magic=(_PSF1_MAGIC, _PSF2_MAGIC),
    patterns=('*.psf', '*.psfu'),
)
def load_psf(instream):
    """Load character-cell font from PC Screen Font (.PSF) file."""
    magic = instream.read(2)
    properties = {}
    if magic == _PSF1_MAGIC:
        psf_props = _PSF1_HEADER.read_from(instream)
        width, height = 8, psf_props.charsize
        length = 512 if psf_props.mode.PSF1_MODE512 else 256
        has_unicode_table = bool(psf_props.mode.PSF1_MODEHASTAB)
        separator = _PSF1_SEPARATOR
        startseq = _PSF1_STARTSEQ
        encoding = 'utf-16le'
        properties['source_format'] = 'PSF v1'
    elif magic + instream.read(2) == _PSF2_MAGIC:
        psf_props = _PSF2_HEADER.read_from(instream)
        charsize = psf_props.height * ceildiv(psf_props.width, 8)
        if psf_props.charsize != charsize:
            logging.warning('Ignoring inconsistent char size in PSF header.')
            psf_props.charsize = charsize
        width, height, length = psf_props.width, psf_props.height, psf_props.length
        has_unicode_table = bool(psf_props.flags.PSF2_HAS_UNICODE_TABLE)
        # ignore any padding after header
        padding = psf_props.headersize - (_PSF2_HEADER.size + len(_PSF2_MAGIC))
        instream.read(padding)
        separator = _PSF2_SEPARATOR
        startseq = _PSF2_STARTSEQ
        encoding = 'utf-8'
        properties['source_format'] = 'PSF v2'
    else:
        raise FileFormatError(
            'Not a PSF file: '
            f'magic bytes {magic} not one of {_PSF1_MAGIC}, {_PSF2_MAGIC}'
        )
    logging.info('PSF properties:')
    for name, value in vars(psf_props).items():
        logging.info('    %s: %s', name, value)
    cells = load_bitmap(instream, width, height, length).glyphs
    if has_unicode_table:
        table = _read_unicode_table(instream, separator, startseq, encoding)
        # convert unicode table to labels
        # ordinal-based codepoint is not meaningful
        cells = tuple(
            _glyph.modify(char=''.join(table[_index]), codepoint=None)
            for _index, _glyph in enumerate(cells)
        )
        properties['encoding'] = 'unicode'
    return Font(cells, **properties)

def _read_unicode_table(instream, separator, startseq, encoding):
    """Read the Unicode table in a PSF2 file."""
    raw_table = instream.read()
    entries = raw_table.split(separator)[:-1]
    table = []
    for point, entry in enumerate(entries):
        split = entry.split(startseq)
        code_points = [_seq.decode(encoding) for _seq in split]
        # first entry is separate code points, following entries (if any) are sequences
        table.append([_c for _c in code_points[0]] + code_points[1:])
    return table


@savers.register(linked=load_psf)
def save_psf(fonts, outstream, *, version:int=2, count:int=256):
    """
    Save character-cell font to PC Screen Font (.PSF) file.

    version: psf format version, 1 or 2 (default)
    count: number of glyphs - version 1 only; 256 (default) or 512
    """
    font = ensure_single(fonts)
    font = ensure_charcell(font)
    # ensure unicode labels exist if encoding is defined
    font = font.label()
    if version == 2:
        _write_psf2(font, outstream)
    elif version == 1:
        if count not in (256, 512):
            raise ValueError(f'`count` should be 256 or 512, not {count}')
        _write_psf1(font, outstream, count)
    else:
        raise ValueError(f'`version` should be 1 or 2, not {version}')


def _write_psf2(font, outstream):
    """Write a PSF version 2 file."""
    glyphs = font.glyphs
    psf_props = dict(
        width=font.raster_size.x,
        height=font.raster_size.y,
        charsize=font.raster_size.y * ceildiv(font.raster_size.x, 8),
        version=0,
        flags=_PSF2_FLAGS(PSF2_HAS_UNICODE_TABLE=1),
        length=len(glyphs),
        headersize=_PSF2_HEADER.size + len(_PSF2_MAGIC)
    )
    outstream.write(_PSF2_MAGIC)
    outstream.write(bytes(_PSF2_HEADER(**psf_props)))
    # save_aligned
    for glyph in glyphs:
        outstream.write(glyph.as_bytes())
    unicode_seq = [_glyph.char for _glyph in glyphs]
    _write_unicode_table(
        outstream, unicode_seq, _PSF2_SEPARATOR, _PSF2_STARTSEQ, 'utf-8'
    )
    return font



# # mode field
# _PSF1_MODE = le.Struct(
#     PSF1_MODE512=flag,
#     PSF1_MODEHASTAB=flag,
#     PSF1_MODEHASSEQ=flag,
#     #unused=bitfield('uint8', 5),
# )

# PSF1 header
_PSF1_MAGIC = b'\x36\x04'
_PSF1_HEADER = le.Struct(
    mode=_PSF1_MODE,
    charsize='uint8',
)


def _write_psf1(font, outstream, count):
    """Write a PSF version 1 file."""
    if font.cell_size.x != 8:
        raise FileFormatError(
            f'This format only supports 8xN character-cell fonts.'
        )
    # we need exactly 256 or 512 glyphs
    glyphs = font.glyphs[:count]
    if len(glyphs) < count:
        # need more glyphs
        glyphs.extend([font.get_default_glyph()] * (count-len(glyphs)))
    header = _PSF1_HEADER(
        mode=_PSF1_MODE(
            PSF1_MODE512=(count==512),
            PSF1_MODEHASTAB=1,
            # not sure what this flag is
            PSF1_MODEHASSEQ=1,
        ),
        charsize=font.cell_size.y,
    )
    outstream.write(_PSF1_MAGIC)
    outstream.write(bytes(header))
    for glyph in glyphs:
        outstream.write(glyph.as_bytes())
    unicode_seq = [_glyph.char for _glyph in glyphs]
    _write_unicode_table(
        outstream, unicode_seq, _PSF1_SEPARATOR, _PSF1_STARTSEQ, 'utf-16'
    )
    return font


def _write_unicode_table(outstream, unicode_seq, separator, startseq, encoding):
    """Write the Unicode table to a PSF2 file."""
    seq = [startseq.join(_c.encode(encoding) for _c in _seq) for _seq in unicode_seq]
    blob = separator.join(seq) + separator
    outstream.write(blob)
