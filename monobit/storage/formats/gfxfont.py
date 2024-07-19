"""
monobit.storage.formats.gfxfont - Adafruit GFX font headers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Glyph, Font
from monobit.base import Props, reverse_dict
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv
from monobit.encoding import EncodingName

from monobit.storage.utils.source import CCodeReader, CCodeWriter
from monobit.storage.utils.limitations import ensure_single, make_contiguous, ensure_charcell

from .raw import load_bitmap, save_bitmap


_GLYPH_FIELDS = (
    'bitmapOffset', 'width', 'height', 'xAdvance', 'xOffset', 'yOffset',
)
_FONT_FIELDS = (
    'bitmap', 'glyph', 'first', 'last', 'yAdvance'
)

@loaders.register(
    name='gfxfont',
    # patterns=('*.h', '*.c'),
)
def load_gfxfont(
        instream,
        glyph_type:str='GFXglyph',
        font_type:str='GFXfont',
        bitmap_type:str='uint8_t'
    ):
    """
    Load font from Adafruit GFX font header.

    glyph_type: type identifier for glyph metrics (default: 'GFXglyph')
    font_type: type identifier for font metrics (default: 'GFXfont')
    bitmap_type: type identifier for bitmap data (default: 'uint8_t')
    """
    instream = instream.text
    identifier = ''
    data = {}
    glyph_metrics = {}
    font_metrics = {}
    for line in instream:
        line = CCodeReader.strip_line_comments(line, instream)
        if CCodeReader.assign in line:
            identifier, _, _ = line.partition(CCodeReader.assign)
            logging.debug('Found assignment to `%s`', identifier)
            if CCodeReader.delimiters[0] in line:
                identifier = CCodeReader.clean_identifier(identifier.strip().removesuffix(' PROGMEM'))
                coded_data = CCodeReader.read_array(instream, line)
                if bitmap_type in line:
                    data[identifier] = CCodeReader.decode_array(coded_data)
                elif glyph_type in line:
                    glyph_metrics[identifier] = CCodeReader.decode_struct_array(
                        coded_data, _GLYPH_FIELDS
                    )
                elif font_type in line:
                    font_metrics[identifier] = CCodeReader.decode_struct(
                        coded_data, _FONT_FIELDS
                    )
    fonts = []
    for name, metrics in font_metrics.items():
        glyphs = []
        # clip off cast
        _, _, bitmap_name = metrics.bitmap.partition(')')
        _, _, glyph_name = metrics.glyph.partition(')')
        first = CCodeReader.decode_int(metrics.first)
        try:
            glyph_table = glyph_metrics[glyph_name.strip()]
            bitmap = data[bitmap_name.strip()]
        except KeyError:
            logging.debug('Data for identifiers `%s` `%s` not found', glyph_name, bitmap_name)
            continue
        for cp, glyph_metric in enumerate(glyph_table, first):
            offset = CCodeReader.decode_int(glyph_metric.bitmapOffset)
            width = CCodeReader.decode_int(glyph_metric.width)
            height = CCodeReader.decode_int(glyph_metric.height)
            length = ceildiv(width * height, 8)
            x_advance = CCodeReader.decode_int(glyph_metric.xAdvance)
            x_offset = CCodeReader.decode_int(glyph_metric.xOffset)
            y_offset = CCodeReader.decode_int(glyph_metric.yOffset)
            glyphdata = bitmap[offset:offset+length]
            glyphs.append(Glyph.from_bytes(
                glyphdata, width=width, height=height, align='bit',
                left_bearing=x_offset,
                right_bearing=x_advance-x_offset-width,
                shift_up=-y_offset-height,
                codepoint=cp,
            ))
        fonts.append(Font(
            glyphs, line_height=CCodeReader.decode_int(metrics.yAdvance),
            name=CCodeReader.clean_identifier(name),
        ))
    return fonts
