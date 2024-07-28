"""
monobit.storage.formats.text.edwin - EDWIN bitmap font format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

# Edinburgh Drawing-program Which Interacts Nicely
# https://history.dcs.ed.ac.uk/archive/apps/edwin/
# for FNT files see https://gtoal.com/history.dcs.ed.ac.uk/archive/apps/edwin/edwin-apm-August87/
# discussed here https://retrocomputingforum.com/t/hershey-fonts-the-original-vector-fonts/1852/14

import logging
import string

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph, Raster
from monobit.base.binary import ceildiv

from monobit.storage.utils.limitations import ensure_single


@loaders.register(
    name='edwin',
    patterns=('*.fnt',),
    text=True,
)
def load_edwin(instream):
    """Load font from EDWIN .FNT file."""
    header = instream.text.readline().strip()
    try:
        first_cp, last_cp = (int(_v) for _v in header.split())
        rasters = []
        for line in instream.text:
            elems = line.strip().split()
            label = elems[0].rstrip(':')
            height, width, *elems = (int(_v) for _v in elems[1:])
            bytestr = b''.join(
                _i.to_bytes(ceildiv(width, 8), 'big')
                for _i in elems
            )
            rasters.append((label, Raster.from_bytes(
                bytestr, height=height, width=width, align='right',
            ).mirror()))
    except ValueError as e:
        raise FileFormatError('Not a well-formed EDWIN file.') from e
    max_height = max(_r.height for _, _r in rasters)
    glyphs = (
        Glyph(
            _raster, shift_up=max_height-_raster.height,
            codepoint=_cp, tag=_label if not _label[:1].isdigit() else None,
        )
        for _cp, (_label, _raster) in enumerate(rasters, first_cp)
    )
    return Font(glyphs)


@savers.register(linked=load_edwin)
def save_edwin(fonts, outstream):
    outstream = outstream.text
    font = ensure_single(fonts)
    # we can only store ascii range
    font = font.subset(chars=tuple(chr(_b) for _b in range(0x80)))
    min_cp, max_cp = int(min(font.get_codepoints())), int(max(font.get_codepoints()))
    # make contiguous
    font = font.resample(codepoints=range(min_cp, max_cp+1))
    font = font.equalise_horizontal()
    outstream.write(f'{min_cp} {max_cp}\n')
    for glyph in font.glyphs:
        rows = (
            str(int.from_bytes(_r, 'big'))
            for _r in glyph.mirror().as_byterows(align='right')
        )
        outstream.write(
            f'{int(glyph.codepoint)}: {glyph.height} {glyph.width} '
        )
        outstream.write(' '.join(rows))
        outstream.write('\n')
