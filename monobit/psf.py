"""
monobit.psf - PC Screen Font format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .binary import ceildiv, friendlystruct
from .raw import load_aligned
from .formats import Loaders, Savers
from .font import Font
from .glyph import Glyph


# PSF formats:
# https://www.win.tue.nl/~aeb/linux/kbd/font-formats-1.html

# PSF1 header
_PSF1_MAGIC = b'\x36\x04'
_PSF1_HEADER = friendlystruct(
    'le',
    mode='uint8',
    charsize='uint8',
)

# mode field
_PSF1_MODE512 = 0x01
_PSF1_MODEHASTAB = 0x02
#_PSF1_MODEHASSEQ = 0x04
#_PSF1_MAXMODE = 0x05

_PSF1_SEPARATOR = b'\xFF\xFF'
_PSF1_STARTSEQ =  b'\xFF\xFE'

# PSF2 header
_PSF2_MAGIC = b'\x72\xb5\x4a\x86'
_PSF2_HEADER = friendlystruct(
    'le',
    version='uint32',
    headersize='uint32',
    flags='uint32',
    length='uint32',
    charsize='uint32',
    height='uint32',
    width='uint32',
)

# flags field
_PSF2_HAS_UNICODE_TABLE = 0x01

# max version recognized so far
#_PSF2_MAXVERSION = 0

#/* UTF8 separators */
_PSF2_SEPARATOR = b'\xFF'
_PSF2_STARTSEQ = b'\xFE'


@Loaders.register(
    'psf', 'psfu',
    magic=(_PSF1_MAGIC, _PSF2_MAGIC),
    name='PSF', binary=True, multi=False
)
def load(instream):
    """Load font from psf file."""
    magic = instream.read(2)
    if magic == _PSF1_MAGIC:
        psf_props = _PSF1_HEADER.read_from(instream)
        width, height = 8, psf_props.charsize
        length = 512 if (psf_props.mode & _PSF1_MODE512) else 256
        has_unicode_table = bool(psf_props.mode & _PSF1_MODEHASTAB)
        separator = _PSF1_SEPARATOR
        startseq = _PSF1_STARTSEQ
        encoding = 'utf-16le'
        properties = {'source-format': 'PSF v1'}
    elif magic + instream.read(2) == _PSF2_MAGIC:
        psf_props = _PSF2_HEADER.read_from(instream)
        charsize = psf_props.height * ceildiv(psf_props.width, 8)
        if psf_props.charsize != charsize:
            logging.warning('Ignoring inconsistent char size in PSF header.')
            psf_props.charsize = charsize
        width, height, length = psf_props.width, psf_props.height, psf_props.length
        has_unicode_table = bool(psf_props.flags & _PSF2_HAS_UNICODE_TABLE)
        # ignore any padding after header
        padding = psf_props.headersize - (_PSF2_HEADER.size + len(_PSF2_MAGIC))
        instream.read(padding)
        separator = _PSF2_SEPARATOR
        startseq = _PSF2_STARTSEQ
        encoding = 'utf-8'
        properties = {'source-format': 'PSF v2'}
    else:
        raise ValueError('Not a PSF file.')
    cells = load_aligned(instream, (width, height), length)
    if has_unicode_table:
        table = _read_unicode_table(instream, separator, startseq, encoding)
        # convert unicode table to labels
        cells = [
            _glyph.set_annotations(char=''.join(table[_index]))
            for _index, _glyph in enumerate(cells)
        ]
    return Font(cells, properties=properties)

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


@Savers.register('psf', 'psfu', name=load.name, binary=True, multi=False)
def save(font, outstream):
    """Save font to PSF2 file."""
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise ValueError(
            'This format only supports character-cell fonts.'
        )
    glyphs = font.glyphs
    psf_props = dict(
        width=font.bounding_box.x,
        height=font.bounding_box.y,
        charsize=font.bounding_box.y * ceildiv(font.bounding_box.x, 8),
        version=0,
        flags=_PSF2_HAS_UNICODE_TABLE,
        length=len(glyphs),
        headersize=_PSF2_HEADER.size + len(_PSF2_MAGIC)
    )
    outstream.write(_PSF2_MAGIC)
    outstream.write(bytes(_PSF2_HEADER(**psf_props)))
    # save_aligned
    for glyph in glyphs:
        outstream.write(glyph.as_bytes())
    unicode_seq = [_glyph.char for _glyph in glyphs]
    _write_unicode_table(outstream, unicode_seq, _PSF2_SEPARATOR, _PSF2_STARTSEQ, 'utf-8')
    return font


def _write_unicode_table(outstream, unicode_seq, separator, startseq, encoding):
    """Write the Unicode table to a PSF2 file."""
    seq = [startseq.join(_c.encode(encoding) for _c in _seq) for _seq in unicode_seq]
    blob = separator.join(seq) + separator
    outstream.write(blob)
