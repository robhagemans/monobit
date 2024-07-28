"""
monobit.storage.formats.gfxfont - Adafruit GFX font headers

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO
from itertools import accumulate

from monobit.storage import loaders, savers, FileFormatError
from monobit.core import Glyph, Font
from monobit.base import Props, reverse_dict
from monobit.base.struct import little_endian as le
from monobit.base.binary import ceildiv
from monobit.encoding import EncodingName

from monobit.storage.utils.source import CCodeReader, CCodeWriter
from monobit.storage.utils.limitations import ensure_single, make_contiguous, ensure_charcell


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
    Load fonts from Adafruit GFX font header.

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
                if font_type in line:
                    font_metrics[identifier] = CCodeReader.decode_struct(
                        coded_data, _FONT_FIELDS
                    )
                elif glyph_type in line:
                    glyph_metrics[identifier] = CCodeReader.decode_struct_array(
                        coded_data, _GLYPH_FIELDS
                    )
                elif bitmap_type in line:
                    data[identifier] = CCodeReader.decode_array(coded_data)
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


@savers.register(linked=load_gfxfont)
def save_gfxfont(fonts, outstream):
    """
    Save fonts to Adafruit GFX font header.
    """
    for font in fonts:
        font = make_contiguous(font, missing='space')
        codepoints = font.get_codepoints()
        if not codepoints:
            raise ValueError('No storable codepoints found in font.')
        font = font.subset(codepoints=codepoints)
        font = font.reduce()
        glyph_data = tuple(_g.as_bytes(align='bit') for _g in font.glyphs)
        offsets = accumulate((len(_d) for _d in glyph_data), initial=0)
        glyph_props = tuple(
            Props(
                bitmapOffset=str(_offset),
                width=str(_g.width),
                height=str(_g.height),
                xAdvance=str(_g.advance_width),
                xOffset=str(_g.left_bearing),
                yOffset=str(-_g.shift_up-_g.height),
            )
            for _g, _offset in zip(font.glyphs, offsets)
        )
        basename = CCodeWriter.to_identifier(font.name)
        bitmap_name = f'{basename}_bitmaps'
        glyph_name = f'{basename}_glyphs'
        font_props = Props(
            bitmap='(uint8_t *) ' + bitmap_name,
            glyph='(GFXGlyph *) ' + glyph_name,
            first=CCodeWriter.encode_int(int(min(codepoints))),
            last=CCodeWriter.encode_int(int(max(codepoints))),
            YAdvance=str(font.line_height),
        )
        outstream = outstream.text
        if font.get_comment():
            outstream.write(f'/*\n{font.get_comment()}\n*/\n\n')
        outstream.write(f'const uint8_t {bitmap_name}[] PROGMEM = ')
        outstream.write(
            CCodeWriter.encode_array(b''.join(glyph_data), bytes_per_line=8)
        )
        outstream.write(';\n\n')
        outstream.write(f'const GFXglyph {glyph_name}[] PROGMEM = ' '{\n')
        for i, props in enumerate(glyph_props):
            if i:
                outstream.write(',\n')
            outstream.write(CCodeWriter.indent)
            outstream.write(
                CCodeWriter.encode_struct(props, show_names=False, compact=True)
            )
        outstream.write('\n};\n\n')
        outstream.write(f'const GFXfont {basename} PROGMEM = ')
        outstream.write(CCodeWriter.encode_struct(font_props, show_names=False))
        outstream.write(';\n\n')
