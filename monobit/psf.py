"""
monobit.psf - read and write .psf font files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from .base import Glyph, Font, Typeface, ceildiv, friendlystruct
from .raw import load_aligned, save_aligned


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


@Typeface.loads('psf', encoding=None)
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
    elif magic + instream.read(2) == _PSF2_MAGIC:
        psf_props = _PSF2_HEADER.read_from(instream)
        charsize = psf_props.height * ceildiv(psf_props.width, 8)
        if psf_props.charsize != charsize:
            logging.warning('Ingnoring inconsistent char size in PSF header.')
            psf_props.charsize = charsize
        width, height, length = psf_props.width, psf_props.height, psf_props.length
        has_unicode_table = bool(psf_props.flags & _PSF2_HAS_UNICODE_TABLE)
        # ignore any padding after header
        padding = psf_props.headersize - (_PSF2_HEADER.size + len(_PSF2_MAGIC))
        instream.read(padding)
        separator = _PSF2_SEPARATOR
        startseq = _PSF2_STARTSEQ
        encoding = 'utf-8'
    cells = load_aligned(instream, (width, height), length)
    # set ordinals as labels
    labels = {
        _index: _index
        for _index in range(len(cells))
    }
    if has_unicode_table:
        table = _read_unicode_table(instream, separator, startseq, encoding)
        # convert unicode table to labels
        labels.update({
            _format_cluster(_seq): _index
            for _index, _seq in enumerate(table)
            if _seq
        })
    return Typeface([Font(cells, labels)])

def _format_cluster(sequence):
    return ','.join(
        'u+{:04x}'.format(ord(_uc))
        for _uc in sequence
    )

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


@Typeface.saves('psf', encoding=None)
def save(typeface, outstream):
    """Save font to PSF file."""
    if len(typeface._fonts) > 1:
        raise ValueError('Saving multiple fonts to .psf not possible')
    font = typeface._fonts[0]
    psf_props = dict(
        width=font.max_width,
        height=font.max_height,
        charsize=font.max_height * ceildiv(font.max_width, 8),
        version=0,
        flags=_PSF2_HAS_UNICODE_TABLE,
        length=font.max_ordinal + 1,
        headersize=_PSF2_HEADER.size + len(_PSF2_MAGIC)
    )
    outstream.write(_PSF2_MAGIC)
    outstream.write(bytes(_PSF2_HEADER(**psf_props)))
    save_aligned(outstream, font)
    # we need to create a dictionary of unicode keys
    # that point to the same glyphs as ordinal keys
    ordinal_for_index = {
        _v: _k
        for _k, _v in font._labels.items()
        if isinstance(_k, int)
    }
    unicode_dict = {
        ordinal_for_index[_v]: _k
        for _k, _v in font._labels.items()
        if _v in ordinal_for_index
        if isinstance(_k, str) and _k.startswith('u+')
    }
    unicode_strings = [
        unicode_dict.get(_i, '') for _i in font.ordinal_range
    ]
    unicode_seq = [
        [chr(int(_cp[2:], 16)) for _cp in _str.split(',') if _cp]
        for _str in unicode_strings
    ]
    _write_unicode_table(outstream, unicode_seq, _PSF2_SEPARATOR, _PSF2_STARTSEQ, 'utf-8')
    return typeface


def _write_unicode_table(outstream, unicode_seq, separator, startseq, encoding):
    """Write the Unicode table to a PSF2 file."""
    seq = [startseq.join(_c.encode(encoding) for _c in _seq) for _seq in unicode_seq]
    blob = separator.join(seq) + separator
    outstream.write(blob)
