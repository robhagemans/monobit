"""
monobit.storage.formats.pilfont - PILfont format

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Font, Glyph
from monobit.base.struct import big_endian as be
from monobit.render import GlyphMap

from monobit.storage.utils.limitations import ensure_single


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


if Image:

    @loaders.register(
        name='pilfont',
        patterns=('*.pil',),
        magic=(b'PILfont\n',),
    )
    def load_pilfont(instream):
        """Load font from PILfont file."""
        signature = instream.readline().strip()
        metadata = instream.readline().strip().split(b';')
        sentinel = instream.readline().strip()
        if signature != b'PILfont':
            raise FileFormatError('PILfont signature not found')
        if sentinel != b'DATA':
            raise FileFormatError('PILfont data sentinel not found')
        try:
            line_height = int(metadata[6])
        except (ValueError, IndexError) as e:
            raise FileFormatError('Malformed PILfont file') from e
        metrics = (
            (_cp, _PIL_METRICS.read_from(instream))
            for _cp in range(256)
        )
        image_name = Path(instream.name).stem + '.pbm'
        with instream.where.open(image_name, 'r') as image_file:
            spritesheet = Image.open(image_file)
            glyphs = []
            for cp, metric in metrics:
                if (
                        not (metric.src_x1 - metric.src_x0)
                        or not (metric.src_y1 - metric.src_y0)
                    ):
                    continue
                crop = spritesheet.crop(
                    (metric.src_x0, metric.src_y0, metric.src_x1, metric.src_y1)
                )
                glyphs.append(
                    Glyph.from_vector(
                        tuple(crop.getdata()),
                        stride=crop.width, _0=0, _1=255,
                        codepoint=cp,
                        left_bearing=metric.dst_x0,
                        right_bearing=metric.dwx - metric.dst_x1,
                        shift_up=-metric.dst_y1,
                    )
                )
        return Font(glyphs, line_height=line_height)


    @savers.register(linked=load_pilfont)
    def save_pilfont(fonts, outstream, *, max_width:int=800):
        """
        Save font to PILfont file.

        max_width: maximum width of spritesheet
        """
        font = ensure_single(fonts)
        outstream.write(b'PILfont\n')
        # I wonder if the other fields in this header were ever defined
        outstream.write(b';;;;;;%d;\n' % font.line_height)
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
                    x, y = 0, y + font.line_height
                    x0, y0 = x, y
                    x = glyph.width
                glyph_map.append_glyph(glyph, x0, y0)
                metrics = _PIL_METRICS(
                    dwx=glyph.advance_width,
                    dwy=0,
                    dst_x0=glyph.left_bearing,
                    dst_y0=-glyph.shift_up - glyph.height,
                    dst_x1=glyph.width + glyph.left_bearing,
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
            image = glyph_map.as_image(ink=1, paper=0, border=0, invert_y=True)
            image.save(image_file, format='png')
