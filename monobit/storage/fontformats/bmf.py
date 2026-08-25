"""
monobit.storage.fontformats.bmf - ByteMap Font format

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate
from collections import defaultdict

from monobit.base.binary import ceildiv
from monobit.base.struct import bitfield, little_endian as le
from monobit.base import Props, UnsupportedError
from monobit.storage import loaders, savers
from monobit.core import Font, Glyph

from monobit.storage.utils.limitations import ensure_single, ensure_levels

_BMF_MAGIC = b'\xe1\xe6\xd5\x1a'

@loaders.register(
    name='bmf',
    magic=(_BMF_MAGIC,),
    patterns=('*.bmf',),
)
def load_bmf(instream, alpha_only:bool=False):
    """
    Load font from bytemap font format file.

    alpha_only: create greyscale font using alpha channel only
    """
    bmf = _read_bmf(instream)
    font = _convert_bmf(bmf, alpha_only)
    return font


@savers.register(linked=load_bmf)
def save_bmf(fonts, outstream):
    """Save font to bytemap font format file."""
    font = ensure_single(fonts)
    bmf = _convert_to_bmf(font)
    _write_bmf(bmf, outstream)
    return font


###############################################################################
# ByteMap Font format
# http://bmf.wz.cz:8080/index.php?page=format
# https://zdoom.org/w/index.php?title=Byte_Map_Font

_BMF_HEADER = le.Struct(
    magic='4s',
    version='uint8',
    lineHeight='uint8',
    sizeOver='int8',
    sizeUnder='int8',
    addSpace='int8',
    sizeInner='int8',
    # NOTE - I don't really understand how the next 2 fields are defined
    usedColors='uint8',
    highestAttribute='uint8',
    # 1.2 only, reserved in 1.1
    # NOTE - not clear if alpha bits live on the MSB or LSB side of the byte
    alphaBits='uint8',
    # 1.2 only, reserved in 1.1
    # NOTE - not clear how extra paletes are stored / used
    extraPalettes='uint8',
    reserved0='uint16',
)

_RGB_ENTRY = le.Struct(
    r='uint8',
    g='uint8',
    b='uint8',
)

_TABLO_ENTRY = le.Struct(
    width='uint8',
    height='uint8',
    relX='int8',
    relY='int8',
    shift='uint8'
)

_KERNING_ENTRY = le.Struct(
    first='uint32',
    second='uint32',
    correction='int16',
)


###############################################################################
# BMF reader

def _read_bmf(instream):
    """Read a ByteMap Format font."""
    bmf = Props()
    bmf.header = _BMF_HEADER.read_from(instream)
    if bmf.header.magic != _BMF_MAGIC:
        raise FileFormatError(
            f'Not a BMF file: magic bytes {bmf.header.magic} != {_BMF_MAGIC}'
        )
    if bmf.header.version not in (0x11, 0x12):
        raise UnsupportedError(f'Unknown BMF version {bmf.header.version:02x}')
    palette_length = int(le.uint8.read_from(instream))
    bmf.palette = (_RGB_ENTRY * palette_length).read_from(instream)
    title_length = int(le.uint8.read_from(instream))
    bmf.title = instream.read(title_length)
    bmf.asciiChars = int(le.uint16.read_from(instream))
    bmf.glyphs = []
    for cp in range(bmf.asciiChars):
        which = int(le.uint8.read_from(instream))
        bmf.glyphs.append(read_bmf_glyph(instream, which))
    # treat 1.2 tables as optional
    if bmf.header.version >= 0x12 and len(instream.peek(4)) >= 4:
        bmf.unicodeChars = int(le.uint32.read_from(instream))
        for cp in range(bmf.unicodeChars):
            which = int(le.uint32.read_from(instream))
            bmf.glyphs.append(read_bmf_glyph(instream, which))
    else:
        bmf.unicodeChars = 0
    if bmf.header.version >= 0x12 and len(instream.peek(4)) >= 4:
        bmf.kerningPairs = int(le.uint32.read_from(instream))
        bmf.kerningTable = (_KERNING_ENTRY * bmf.kerningPairs).read_from(instream)
    else:
        bmf.kerningTable = ()
    return bmf


def read_bmf_glyph(instream, which):
    """Read tablo and bitmap for one glyph."""
    gp = Props()
    gp.which = which
    gp.tablo = _TABLO_ENTRY.read_from(instream)
    gp.bitmap = instream.read(gp.tablo.width*gp.tablo.height)
    return gp


def _convert_bmf(bmf, alpha_only):
    """Convert BMF font."""
    # -- convert kerning map
    kerning_map = defaultdict(list)
    if bmf.header.version >= 0x12:
        for kern in bmf.kerningTable:
            kerning_map[kern.first][kern.second] = kern.correction
    kerning_map = dict(kerning_map)
    # -- convert palette
    # NOTE: color 0 is defined as transparent, not black
    # TODO: update when we support alpha in palettes
    if bmf.header.extraPalettes:
        # I don't understand how multiple palettes are meant to be stored
        logging.warning('Multiple palettes not supported')
    rgb_table = ((0, 0, 0),) + tuple(
        (_p.r*255//63, _p.g*255//63, _p.b*255//63) for _p in bmf.palette
    )
    # -- mask off alpha bits in bytemap
    # glyph bytes consist of alpha bits and palette bits
    # this ASSUMES the alpha bits are the MSB side but this is not specified
    if bmf.header.alphaBits > 8:
        logging.warning('capping alphaBits == %d at 8', bmf.header.alphaBits)
        bmf.header.alphaBits = 8
    alpha_mask = ((1<<bmf.header.alphaBits) - 1) << (8-bmf.header.alphaBits)
    palette_mask = ((1<<8) - 1) - alpha_mask
    if bmf.header.alphaBits == 8 or alpha_only:
        # if all bits are alphaBits, there's no colour information.
        # drop palette and use alpha as greyscale value
        mask = alpha_mask
        rgb_table = None
        levels = 1 << bmf.header.alphaBits
    else:
        mask = palette_mask
        levels = len(rgb_table)
    for gp in bmf.glyphs:
        gp.bitmap = bytes(_b & mask for _b in gp.bitmap)
    # -- convert glyphs
    glyphs = tuple(
        Glyph.from_bytes(
            _gp.bitmap,
            bits_per_pixel=8,
            levels=levels,
            width=_gp.tablo.width,
            # ""its ASCII code 0..255"". No codepage defined
            codepoint=_gp.which,
            left_bearing=_gp.tablo.relX,
            right_bearing=(
                _gp.tablo.shift - _gp.tablo.width - _gp.tablo.relX
                + bmf.header.addSpace
            ),
            shift_up=(
                bmf.header.lineHeight - bmf.header.sizeUnder
                - _gp.tablo.relY - _gp.tablo.height
            ),
            right_kerning=kerning_map.get(_gp.which, None),
        )
        for _gp in bmf.glyphs
    )
    # -- convert font metrics and metadata
    # encoding of the title is not defined in the spec.
    # https://github.com/JoeStrout/minimicro-fonts/blob/main/bmfFonts.ms uses UTF-8
    if bmf.header.version >= 0x12:
        title = bmf.title.decode('utf-8', errors='replace')
    else:
        # assumption, consistent with the font's encoding
        title = bmf.title.decode('cp437')
    font = Font(
        glyphs, x_height=-bmf.header.sizeInner,
        ascent=-bmf.header.sizeOver, descent=bmf.header.sizeUnder,
        line_height=bmf.header.lineHeight,
        rgb_table=rgb_table,
        name=title,
        source_format=f'bmf 1.{bmf.header.version-0x10}',
    )
    if bmf.header.version >= 0x12:
        # as defined in the spec
        font = font.label(char_from='unicode')
    else:
        # not defined in the spec. CP 437 is consistent with BMF gallery web site
        font = font.label(char_from='cp437')
    return font


###############################################################################
# BMF writer

def _convert_to_bmf(font, version='1.1'):
    """Convert font to bmf structure."""
    font = font.label().label(codepoint_from=None, overwrite=True)
    if version == '1.1':
        title_encoding = 'ascii'
        font = font.label(codepoint_from='cp437')
        ascii_chars = len(font.get_codepoints())
    elif version == '1.2':
        title_encoding = 'utf-8'
        font = font.label(codepoint_from='ascii')
        ascii_chars = len(font.get_codepoints())
        unicode_chars = len(font.get_chars()) - ascii_chars
    else:
        raise ValueError(
            f"`version` must be one of ('1.1', '1.2'), not {version}"
        )
    bmf = Props()
    bmf.header = _BMF_HEADER(
        magic=_BMF_MAGIC,
        version=0x11 if version == '1.1' else 0x12,
        lineHeight=font.line_height,
        sizeOver=-font.ascent,
        sizeUnder=font.descent,
        addSpace=0, # TODO use common right bearing
        sizeInner=-font.x_height,
        # NOTE - I don't really understand how the next 2 fields are defined
        usedColors=font.levels,
        highestAttribute=font.levels-1,

        # NOTE - not clear if alpha bits live on the MSB or LSB side of the byte
        # alphaBits='uint8',
        # NOTE - not clear how extra paletes are stored / used
        # extraPalettes=0,
    )
    # TODO generate rgb table for greyscale?
    # logging.debug(_RGB_ENTRY(**vars(font.rgb_table[0])))
    bmf.palette = (_RGB_ENTRY * (len(font.rgb_table)-1))(
        *(_RGB_ENTRY(r=_rgb.r>>2, g=_rgb.g>>2, b=_rgb.b>>2)
        for _rgb in font.rgb_table[1:])
    )
    bmf.title = font.name.encode(title_encoding, 'replace')
    bmf.asciiChars = ascii_chars
    bmf.ascii_glyphs = tuple(
        _convert_to_bmf_glyph(font.get_glyph(_cp), _cp, font)
        for _cp in sorted(font.get_codepoints())
    )
    if version == '1.2':
        bmf.unicode_glyphs = tuple(
            _convert_to_bmf_glyph(font.get_glyph(_c), ord(_c), font)
            for _c in sorted(font.get_chars())
            if _c > 127
        )
        bmf.kerningTable = () # TODO _KERNING_ENTRY(...)
        bmf.kerningPairs = len(bmf.kerningTable)
    return bmf


def _convert_to_bmf_glyph(glyph, which, font):
    """Convert glyph to BMF format."""
    gp = Props()
    gp.which = int(which)
    gp.tablo = _TABLO_ENTRY(
        width=glyph.width,
        height=glyph.height,
        relX=glyph.left_bearing,
        relY=font.line_height - glyph.height - glyph.shift_up - font.descent,
        shift=glyph.advance_width,
    )
    gp.bitmap = glyph.pixels.as_bytes(bits_per_pixel=8)
    return gp


def _write_bmf(bmf, outstream):
    """Write bmf to file."""
    outstream.write(bytes(bmf.header))
    outstream.write(bytes(le.uint8(len(bmf.palette))))
    outstream.write(bytes(bmf.palette))
    outstream.write(bytes(le.uint8(len(bmf.title))))
    outstream.write(bmf.title)
    outstream.write(bytes(le.uint16(bmf.asciiChars)))
    for gp in bmf.ascii_glyphs:
        _write_bmf_glyph(gp, outstream, unicode=False)
    if bmf.header.version >= 0x12:
        outstream.write(bytes(le.uint32(bmf.unicodeChars)))
        for gp in bmf.unicode_glyphs:
            _write_bmf_glyph(gp, outstream, unicode=False)
        outstream.write(bytes(le.uint32(bmf.kerningPairs)))
        outstream.write(bytes(bmf.kerningTable))


def _write_bmf_glyph(gp, outstream, unicode=False):
    """Write glyph to BMF file."""
    if unicode:
        outstream.write(bytes(le.uint32(gp.which)))
    else:
        outstream.write(bytes([gp.which]))
    outstream.write(bytes(gp.tablo))
    outstream.write(gp.bitmap)
