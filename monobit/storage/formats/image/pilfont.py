"""
monobit.storage.formats.pilfont - PILfont format

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph
from monobit.base.struct import big_endian as be
from monobit.render import GlyphMap


@loaders.register(
    name='pilfont',
    patterns=('*.pil',),
    magic=(b'PILfont\n',),
)
def load_pilfont(instream):
    """Load font from PILfont file."""
    # return Font(glyphs, **vars(props))


_PIL_METRICS = be.Struct(
    dwx='int16',
    dwy='int16',
    dst_x0='int16',
    dst_y0='int16',
    dst_x1='int16',
    dst_y1='int16',
    src_x0='int16',
    src_y0='int16',
    src_x1='int16',
    src_y1='int16',
)

@savers.register(linked=load_pilfont)
def save_pilfont(fonts, outstream, *, max_width:int=800):
    """
    Save font to PILfont file.

    max_width: maximum width of spritesheet
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to PILfont file.')
    font, = fonts
    outstream.write(b'PILfont\n')
    # I wonder if the other fields in this header were ever defined
    outstream.write(b';;;;;;%d;\n' % font.raster_size.y)
    outstream.write(b'DATA\n')
    x, y = 0, 0
    glyph_map = GlyphMap()
    for cp in range(256):
        try:
            glyph = font.get_glyph(codepoint=cp, missing='raise')
        except KeyError:
            metrics = _PIL_METRICS()
        else:
            x0, y0 = x, y
            x += glyph.width
            if x > max_width:
                x, y = 0, y + font.raster_size.y
                x0, y0 = x, y
                x = glyph.width
            glyph_map.append_glyph(glyph, x0, y0)
            metrics = _PIL_METRICS(
                dwx=glyph.advance_width,
                dwy=0,
                dst_x0=glyph.left_bearing,
                dst_y0=-glyph.shift_up - glyph.height,
                dst_x1=glyph.advance_width,
                dst_y1=-glyph.shift_up,
                src_x0=x0,
                src_y0=y0,
                src_x1=x0 + glyph.width,
                src_y1=y0 + glyph.height,
            )
        # write mapping file
        outstream.write(bytes(metrics))
    # write image
    image_name = Path(outstream.name).stem + '.pbm'
    with outstream.where.open(image_name, 'w') as image_file:
        image = glyph_map.as_image(ink=1, paper=0, border=0)
        image.save(image_file, format='png')
