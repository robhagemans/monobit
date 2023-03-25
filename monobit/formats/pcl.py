"""
monobit.formats.pcl - HP PCL soft fonts

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO

from ..storage import loaders, savers
from ..magic import FileFormatError, Magic
from ..struct import big_endian as be, bitfield
from ..glyph import Glyph
from ..raster import Raster
from ..font import Font
from ..properties import Props, reverse_dict
from ..encoding import charmaps


@loaders.register(
    name='hppcl',
    magic=(
        b'\x1b)s' + Magic.offset(2) + b'W',
        b'\x1b)s' + Magic.offset(3) + b'W',
        b'\x1b)s' + Magic.offset(4) + b'W',
    ),
    patterns=('*.sft', '*.sfl', '*.sfp'),
)
def load_hppcl(instream):
    """Load a HP PCL soft font."""
    fontdef, copyright = _read_hppcl_header(instream)
    logging.debug(fontdef)
    if fontdef.descriptor_format not in (
            _HEADER_FMT_BITMAP, 5, 6, 7, 9, 12, 16, _HEADER_FMT_RES_BITMAP
        ):
        raise FileFormatError('PCL soft font is not a bitmap font.')
    glyphdefs = _read_hppcl_glyphs(instream)
    props = _convert_hppcl_props(fontdef, copyright)
    glyphs = _convert_hppcl_glyphs(glyphdefs)
    return Font(glyphs, **props).label()


@savers.register(linked=load_hppcl)
def save_hppcl(fonts, outstream, orientation:str='portrait'):
    """
    Save to a HP PCL soft font.

    orientation: 'portrait' or 'landscape'
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to HP PCL file.')
    font = fonts[0]
    if orientation.lower().startswith('p'):
        orientation = 0
    elif orientation.lower().startswith('l'):
        orientation = 1
    else:
        raise ValueError(f"orientation must be one of 'portrait' or 'landscape', not {orientation}")
    # get storable glyphs (8-bit bound)
    font = font.label(codepoint_from=font.encoding)
    font = font.subset(codepoints=range(256))
    # convert
    fontdef, copyright = _convert_to_hppcl_props(font, orientation)
    glyphdefs = (
        _convert_to_hppcl_glyph(glyph, orientation)
        for glyph in font.glyphs
    )
    # write
    size = _BITMAP_FONT_DEF.size + len(copyright)
    outstream.write(b'\x1b)s%dW' % (size,))
    outstream.write(bytes(fontdef))
    outstream.write(copyright)
    for code, chardef, glyphbytes in glyphdefs:
        outstream.write(b'\x1b*c%dE' % (code,))
        common = _LASERJET_CHAR_COMMON(format=_CHAR_FMT_LASERJET, continuation=0)
        size = _LASERJET_CHAR_COMMON.size + _LASERJET_CHAR_DEF.size + len(glyphbytes)
        outstream.write(b'\x1b(s%dW' % (size,))
        outstream.write(bytes(common))
        outstream.write(bytes(chardef))
        outstream.write(glyphbytes)
    return font


###############################################################################
# PCL soft font format

# font definition structures
# https://developers.hp.com/system/files/attachments/PCL%20Implementors%20Guide-10-downloading%20fonts.pdf

_HEADER_FMT_BITMAP = 0
_HEADER_FMT_RES_BITMAP = 20


_BITMAP_FONT_HEAD = be.Struct(
    font_descriptor_size='uint16',
    descriptor_format='uint8',
)
_BITMAP_FONT_DEF = be.Struct(
    # Font Descriptor Size (UINT): The number of bytes in the font descriptor
    font_descriptor_size='uint16',
    # Descriptor Format (UBYTE)
    # 0 Standard Bitmap
    # 5 DeskJet Bitmap
    # 6 PaintJet Bitmap
    # 7 PaintJet XL Bitmap
    # 9 DeskJet Plus Bitmap
    # 10 Bound Intellifont Scalable
    # 11 Unbound Intellifont Scalable
    # 12 DeskJet 500 Bitmap
    # 15 TrueType Scalable
    # 16 Universal
    # 20 Resolution-Specified Bitmap
    descriptor_format='uint8',
    # Symbol Set Type (UBYTE)
    # 0 Bound font, 7-bit (96 characters) ⎯ Character codes 32-127 [decimal] are printable.*
    # 1 Bound, 8-bit (192 characters) ⎯ Character codes 32-127 and160-255 printable.*
    # 2 Bound, 8-bit (256 characters) ⎯ All codes are printable except 0, 7-15, and 27.*
    # 3 Bound, 16-bit (65535 characters) ⎯ All are printable except 0, 7-15, 27, 65279, 65534, 65535
    # 10 Unbound ⎯ Character codes correspond to MSL numbers (Intellifont).
    # 11 Unbound ⎯ Character codes correspond to Unicode numbers (TrueType).
    symbol_set_type='uint8',
    # Style MSB (UINT16): The style MSB combines with the style LSB to make the style word
    style_msb='uint8',
    reserved='uint8',
    # Baseline Position (UINT16): Bitmap Font - Specifies the distance from the baseline
    # (an imaginary dot row on which the characters stand) to the top of the cell.
    baseline_position='uint16',
    # Cell Width (UINT16): Specifies the width from the leftmost extent of any
    # character in the font to the rightmost extent of any character in the font.
    # Bitmap Font - Specified in PCL coordinate system dots.
    cell_width='uint16',
    # Cell Height (UINT16): Specifies the distance from the lowest descent of any
    # character in the font to the highest ascent of any character in the font.
    # Bitmap Font - Specified in PCL coordinate system dots.
    cell_height='uint16',
    # Orientation (UBYTE): Specifies font orientation. All font characters must have
    # the same orientation as those specified in the font descriptor; otherwise they
    # are discarded as they are downloaded.
    # 0 = portrait (0 degrees)
    # 1 = landscape (90 degrees counterclockwise)
    # 2 = reverse portrait (180 degrees counterclockwise)
    # 3 = reverse landscape (270 degrees counterclockwise)
    orientation='uint8',
    # Spacing (UBYTE):
    # 0 Fixed
    # 1 Proportional
    # 2 Dual-fixed
    spacing='uint8',
    # Symbol Set (UINT16): Specifies the symbol set characteristic of the font
    symbol_set='uint16',
    # Pitch (UINT16): Bitmap Font - Specifies the pitch of the font in quarter-dot units
    # For example, at 300 dpi (1200 quarter-dots/inch), a 17 cpi font has a pitch field of 70 and a non-zero pitch
    # extended field. (1inch / 17char) x (300 dots / inch) x (4 radix dots / dot) = 70.588 radix dots/char
    pitch='uint16',
    # Height (UINT16): Bitmap Font - Specifies font height in quarter-dots. The value,
    # converted to points (1/72 inch), is the font's height characteristic
    height='uint16',
    # xHeight (UINT16): Bitmap Font - Specifies the height of the lower case "x" in quarter dots.
    x_height='uint16',
    # Width Type (SBYTE): Specifies the proportionate width of characters in the font
    # see _SETWIDTH_MAP
    width_type='uint8',
    # Style LSB (UBYTE): The least significant byte of the Style word.
    style_lsb='uint8',
    # Stroke Weight (SBYTE): Specifies the thickness of the font characters.
    stroke_weight='int8',
    # Typeface [LSB/MSB] (UBYTE individually, UINT16 together)
    typeface_lsb='uint8',
    typeface_msb='uint8',
    # Serif Style (UBYTE)
    serif_style='uint8',
    # Quality (UBYTE): Specifies the quality or density of the font.
    # 0 Data Processing (Draft)
    # 1 Near Letter Quality
    # 2 Letter Quality
    quality='uint8',
    # Placement (SBYTE): Specifies the position of character patterns relative to the baseline.
    # Bitmap Font - The placement values for bitmap fonts are listed below.
    # 1 Superior (superscript)
    # 0 Normal
    # -1 Inferior (subscript)
    placement='int8',
    # Underline Position (SBYTE): Bitmap Font - Specifies the distance from the
    # baseline to the top dot row of the underline in dots. Zero
    # specifies an underline position at the baseline.
    underline_position='int8',
    # Underline Thickness (UBYTE): Specifies the thickness of the underline in dots for a bitmap font
    underline_thickness='uint8',
    # Text Height (UINT16): Specifies the font's optimum inter-line spacing.
    # This value is typically 120% of the height of the font.
    # Bitmap Font - Specified in quarter-dot units (radix dots)
    text_height='uint16',
    # Text Width (UINT16): Specifies the font's average lowercase character width
    # (which can be weighted on the basis of relative frequency).
    # Bitmap Font - Specified in quarter-dots (radix dots).
    text_width='uint16',
    # First Code (UINT16): Specifies the character code of the first printable character in the font.
    first_code='uint16',
    # Last Code / Number of Characters (UINT16): Specifies the last downloadable character code in the font.
    last_code='uint16',
    # Pitch Extended (UBYTE): Bitmap Font - This is an addition to the Pitch field
    # which extends pitch an extra eight bits to allow 10 bits of fractional dots.
    pitch_extended='uint8',
    # Height Extended (UBYTE): Bitmap Font - This is an addition to the Height field
    # which extends the height an extra eight bits to allow 10 bits of fractional dots.
    height_extended='uint8',
    # Cap Height (UINT): Cap height is a percentage of the Em of a font and is used
    # to calculate the distance from the capline (top of an unaccented, upper-case
    # letter, e.g., "H") to the baseline.
    # For nonzero values the Cap Height percentage is calculated as follows:
    # % = (Cap Height Data / 65535) x 100
    cap_height='uint16',
    # Font Number (UINT32): Bitmap font - should be ignored and set to 0
    font_number='uint32',
    # Font Name (ASC16)
    font_name='16s',
    # followed by optional copyright notice
)

# resolution-specified bitmap font definition
_RESOLUTION_EXT = be.Struct(
    x_resolution='uint16',
    y_resolution='uint16',
)
# omitted: universal font definition
# additional fields have no info for bitmaps and can be safely ignored


_SETWIDTH_MAP = {
    -5: 'ultra-compressed',
    -4: 'ultra-condensed', # extra compressed
    -3: 'extra-condensed', # compressed
    -2: 'condensed',
    -1: 'semi-condensed',
    0: 'medium',
    1: 'semi-expanded',
    2: 'expanded',
    3: 'extra-expanded',
}

_WEIGHT_MAP = {
    -7: 'ultra-thin',
    -6: 'extra-thin',
    -5: 'thin',
    -4: 'extra-light',
    -3: 'light',
    -2: 'demi-light',
    -1: 'semi-light',
    0: 'regular', #Medium, Book, or Text
    1: 'semi-bold',
    2: 'demi-bold',
    3: 'bold',
    4: 'extra-bold',
    5: 'heavy', # Black
    6: 'extra-heavy', # Extra Black
    7: 'ultra-heavy', # Ultra Black
}

# character definition structures
# https://developers.hp.com/system/files/attachments/PCL%20Implementors%20Guide-11-downloading%20characters.pdf


_CHAR_FMT_LASERJET = 4

_LASERJET_CHAR_COMMON = be.Struct(
    # Format (UBYTE): Specifies the character descriptor format.
    # 0 82906A
    # 1 82450A
    # 3 QuietJet
    # 4 LaserJet bitmap
    # 5 DeskJet
    # 6 PaintJet
    # 7 PaintJet XL
    # 8 RuggedWriter
    # 9 DeskJet Plus
    # 10 Intellifont
    # 12 DeskJet 500
    # 15 TrueType
    format='uint8',
    # Continuation (BOOL)
    # Specifies whether the subsequent data is a character descriptor block (0) or
    # a continuation (non-zero) of the data associated with the previous character descriptor.
    continuation='uint8',
    # followed by character data
)
_LASERJET_CHAR_DEF = be.Struct(
    #format='uint8',
    #continuation='uint8',
    # Descriptor Size (UBYTE): Specifies character descriptor size in bytes
    # 8 DeskJet 5xx except 540 (Format 5 or 9 character descriptor)
    # 8 DeskJet 5xx except 540 (Format 12 character descriptor)
    # 2 Intellifont
    # 2+ TrueType (additional descriptor information can be added)
    # 14 LaserJet bitmap
    descriptor_size='uint8',
    # Class (UBYTE): Specifies the format of the character data.
    # 1 Bitmap
    # 2 Compressed bitmap
    # 3 Intellifont
    # 4 Compound Intellifont
    # 15 TrueType
    class_='uint8',
    # Orientation (UBYTE): Bitmap fonts only. Specifies the orientation of the character.
    # Character orientation must match the orientation in the font descriptor,
    orientation='uint8',
    reserved='uint8',
    # Left Offset (SINT16): Bitmap fonts only. Specifies the distance in dots from the reference point to the left side of the
    # character pattern on the physical page coordinate system (i.e.. this value is orientation dependent).
    left_offset='int16',
    # Top Offset (SINT16): Bitmap fonts only. Specifies the distance in dots from the reference point to the top of the
    # character pattern on the physical page coordinate system (i.e., this value is orientation dependent).
    top_offset='int16',
    # Character Width (UINT16): Bitmap fonts only. Specifies the width of the character in dots on the physical coordinate system
    # (i.e., this value is orientation dependent). Generally, this width is from the farthest left black dot
    # to the farthest right black dot.
    character_width='uint16',
    # Character Height (UINT16): Bitmap fonts only. Specifies the height of the character in dots on the physical coordinate system
    # (i.e., this value is orientation dependent).
    character_height='uint16',
    # Delta X (SINT16): Bitmap fonts only. Specifies the number of quarter-dot units (radix dots) by which the horizontal
    # position within the PCL logical page coordinate system is incremented after printing the
    # character. If the value field is negative, the value is set to 0. This value is used by the printer only
    # when the font is proportionally spaced.
    delta_x='int16',
    # followed by character data
)


# Style Word = Posture + (4 x Width) + (32 x Structure)
_STYLE_WORD = be.Struct(
    x=bitfield('uint16', 1),
    reserved=bitfield('uint16', 5),
    structure=bitfield('uint16', 5),
    width=bitfield('uint16', 3),
    posture=bitfield('uint16', 2),
)

# Posture (style word partial sum)
_STYLE_POSTURE_MAP = {
    # 0 - Upright
    0: 'roman',
    # 1 - Italic
    1: 'italic',
    # 2 - Alternate Italic
    2: 'oblique',
    # 3 - Reserved
    3: ''
}

# = Width (style word partial sum multiplied by 4)
_STYLE_WIDTH_MAP = {
    # 0 - Normal
    0: 'medium',
    # 1 - Condensed
    1: 'condensed',
    # 2 - Compressed or extra condensed
    2: 'extra-condensed',
    # 3 - Extra compressed
    3: 'ultra-condensed',
    # 4 - Ultra compressed
    4: 'ultra-compressed',
    # 5 - Reserved
    5: '',
    # 6 - Extended or expanded
    6: 'expanded',
    # 7 - Extra extended or extra expanded
    7: 'extra-expanded',
}

# upper two bits of serif style field
# can't be both set (192 is reserved)
_SERIF_MAP = {
    64: 'sans serif',
    128: 'serif',
}

_STYLE_STRUCTURE_MAP = {}
# = Structure (style word partial sum multiplied by 32)
# 0 - Solid
# 1 - Outline
# 2 - Inline
# 3 - Contour, Edge effects
# 4 - Solid with shadow
# 5 - Outline with shadow
# 6 - Inline with shadow
# 7 - Contour with shadow
# 8-11 - Patterned (complex patterns, subjective to typeface)
# 12-15 - Patterned with shadow
# 16 - Inverse
# 17 - Inverse in open border
# 18-30 - Reserved
# 31 - Unknown structure

# Typeface Family Number = Typeface Base Value + (Vendor Value x 4096)
_TYPEFACE_WORD = be.Struct(
    vendor=bitfield('uint16', 4),
    typeface_family=bitfield('uint16', 12),
)

_VENDOR_MAP = {
    # 0 Reserved
    1: 'Agfa Division, Miles Inc.',
    2: 'Bitstream Inc.',
    3: 'Linotype Company',
    4: 'The Monotype Corporation plc',
    5: 'Adobe Systems, Inc'
    # 6-15 Reserved
}

# symbol sets
# https://developers.hp.com/system/files/attachments/PCL%20Implementors%20Guide-09-font%20selection.pdf
# https://www.pclviewer.com/resources/pcl_symbolset.html
_SYMBOL_SETS = {
    '0@': '',
    #
    # iso 646
    '0U': 'ascii',
    #'0D': 'iso646-no', # iso-ir-60
    #'1D': 'iso646-no2', # -61
    '1E': 'iso646-gb', # -4
    '1F': 'iso646-fr', # -69
    '0F': 'iso-ir-25', # fr (1973)
    '1G': 'iso646-de', # -21
    '0I': 'iso646-it', # -15
    '0K': 'iso646-jp', # -14
    '1K': 'iso-ir-13', # katakana
    '2K': 'iso646-cn', # -57
    #'0S': 'iso-ir-11' # swedish
    '2S': 'iso646-es', # -17
    #'3S': 'iso-ir-10' # swedish
    #'4S': 'iso-ir-16', # portuguese
    #'5S': 'iso-ir-84', # portuguese
    '6S': 'iso646-es2', # -85
    # '2U': 'iso-ir-2', # 1973 international reference version
    #
    # PCL commonly used
    '8U': 'hp-roman8',
    # win 3.0 latin-1
    '9U': 'windows-1252',
    # win 3.1 latin-1
    '19U': 'windows-1252',
    '10U': 'cp437', # pcl pc-8
    '12G': 'cp437', #'pcl-pc-8', same as 10U?
    # '9T': # pcl pc-8 tk code page 437T
    # '11U': # pcl pc-8 d/n code page 437N
    '13J': 'pcl-ventura',
    '9E': 'windows-1250', #windows 3.1 latin-2
    # '0G': 'pcl-german',
    # '1S': 'pcl-spanish',
    '8G': 'pcl-greek8',
    '10G': 'cp851',
    '15h': 'cp862',
    '0T': 'tis-620',
    '1T': 'windows-874',
    '5T': 'windows-1254', # pcl windows-3.1 latin 5
    '8T': 'cp857',
    '16U': 'cp857',
    # '6J': 'pcl-ms-publishing',
    # '7J': 'pcl-desktop',
    '9J': 'ibm-1004',
    # '10J': 'pcl-ps-text',
    '12J': 'mac-roman', #'pcl-macintosh',
    # '14J': 'pcl-ventura-us',
    # '1U': 'pcl-legal',
    '12U': 'cp850',
    '13U': 'cp858',
    '17U': 'cp852',
    '20U': 'cp860',
    '21U': 'cp861',
    '23U': 'cp863',
    '25U': 'cp865',
    '26U': 'cp775',
    '8V': 'cp864', # PCL Code Page 864 Latin/Arabic 8V
    #'10V': # PCL Code Page 864 Latin/Arabic 10V 342
    #
    # iso-8859
    '0N': 'latin-1',
    '2N': 'latin-2',
    '3N': 'latin-3',
    '4N': 'latin-4',
    '5N': 'latin-5',
    '6N': 'latin-6',
    '9N': 'latin-9',
    '10N': 'iso8859-5',
    '11N': 'iso8859-6',
    '12N': 'iso8859-7',
    '7H': 'iso8859-8',
    #
    # line draw, symbols
    '8L': 'ms-linedraw',
    # '0B': 'pcl-linedraw-7', # == pcl-linedraw-71
    # '0L': 'pcl-linedraw-7',
    # '14L': # pcl itc zapf dingbats
    # '5M': # pcl ps math symbol set
    # '19M': # pcl math symbol set
}
_REV_SYMBOL_SETS = {
    charmaps.normalise(_k): _v
    for _k, _v in reverse_dict(_SYMBOL_SETS).items()
}


###############################################################################
# converter

def _convert_hppcl_props(fontdef, copyright):
    """Convert from PCL to monobit properties."""
    style_word = _STYLE_WORD.from_bytes(bytes((
        fontdef.style_msb, fontdef.style_lsb
    )))
    typeface_word = _TYPEFACE_WORD.from_bytes(bytes((
        fontdef.typeface_msb, fontdef.typeface_lsb
    )))
    props = dict(
        # metadata
        name=fontdef.font_name.strip().decode('ascii', 'replace'),
        foundry=_VENDOR_MAP.get(typeface_word.vendor, None),
        #family_id=typeface_word.typeface_family,
        notice=copyright.decode('ascii', 'replace'),
        # descriptive properties
        slant=_STYLE_POSTURE_MAP.get(style_word.posture, None),
        setwidth=_SETWIDTH_MAP.get(fontdef.width_type, ''),
        weight=_WEIGHT_MAP.get(fontdef.stroke_weight, ''),
        style=_SERIF_MAP.get(fontdef.serif_style & 192, ''),
        # encoding
        encoding=_encoding_from_symbol_set(fontdef.symbol_set) or None,
        # metrics
        descent=fontdef.baseline_position//4,
        ascent=(fontdef.height-fontdef.baseline_position)//4,
        line_height=fontdef.text_height//4 or None,
        # decoration metrics
        underline_descent=-fontdef.underline_position or None,
        underline_thickness=fontdef.underline_thickness or None,
        # characteristics
        x_height=fontdef.x_height//4,
        cap_height=(fontdef.cap_height * fontdef.height / 65536) // 4 or None,
        average_width=fontdef.pitch / 4 or None,
        # debugging
        #fontdef=Props(**vars(fontdef)),
        # ignoring height_extended, pitch_extended
        # ignoring fractional dot sizes
    )
    props['hppcl.family-id'] = typeface_word.typeface_family
    if fontdef.descriptor_format == _HEADER_FMT_RES_BITMAP:
        props['dpi'] = (fontdef.x_resolution, fontdef.y_resolution)
    return props


def _encoding_from_symbol_set(symbol_set):
    """Convert symbol set code to encoding name."""
    num, lett = divmod(symbol_set, 32)
    pcl_symbol_set_id = f'{num}{chr(lett+64)}'
    return _SYMBOL_SETS.get(pcl_symbol_set_id, f'pcl-{pcl_symbol_set_id}')


def _convert_hppcl_glyph(code, chardef, glyphbytes):
    """Convert from PCL to monobit glyph."""
    props = {}
    raster = ()
    if chardef.class_ not in (1, 2):
        logging.error('Unsupported character data format.')
    elif chardef.class_ == 2:
        # decompress RLE data
        reader = BytesIO(glyphbytes)
        outbits = []
        outrow = []
        while True:
            repeats = reader.read(1)
            if not repeats:
                break
            length = 0
            bit = False
            while length < chardef.character_width:
                n = reader.read(1)
                if not n:
                    break
                outrow.extend([bit] * ord(n))
                bit = not bit
            outbits.extend(outrow * ord(repeats))
        raster = Raster(outbits, _0=False, _1=True)
    else:
        raster = Raster.from_bytes(
            glyphbytes, width=chardef.character_width,
        ).turn(clockwise=chardef.orientation)
    if chardef.orientation == 0:
        props = dict(
            left_bearing=chardef.left_offset,
            shift_up=chardef.top_offset-chardef.character_height+1,
            right_bearing=chardef.delta_x//4 - chardef.character_width - chardef.left_offset,
        )
    elif chardef.orientation == 1:
        props = dict(
            left_bearing=chardef.top_offset-chardef.character_height+1,
            shift_up=-chardef.left_offset-chardef.character_width+1,
            right_bearing=chardef.delta_x//4 - chardef.top_offset - 1,
        )
    else:
        raise FileFormatError('Unsupported orientation')
    props.update(dict(
        codepoint=code,
        #chardef=Props(**vars(chardef)),
    ))
    return Glyph(raster, **props)


def _convert_hppcl_glyphs(glyphdefs):
    """Convert from PCL to monobit glyphs."""
    glyphs = tuple(
        _convert_hppcl_glyph(*_gd)
        for _gd in glyphdefs
    )
    return glyphs


###############################################################################
# reader

def _read_hppcl_header(instream):
    """Read the PCL font definition header."""
    while True:
        pre, esc_cmd = read_until(instream, b'\x1b', 3)
        if pre:
            logging.debug(pre)
        if not esc_cmd:
            break
        if esc_cmd != b'\x1b)s':
            logging.warning(f'Expected font header; ignoring unexpected PCL command {esc_cmd}')
        else:
            break
    sizestr, _ = read_until(instream, b'W', 1)
    size = bytestr_to_int(sizestr)
    logging.debug('header size %d', size)
    headerbytes = instream.read(_BITMAP_FONT_HEAD.size)
    fontdef = _BITMAP_FONT_HEAD.from_bytes(headerbytes)
    header_length = min(fontdef.font_descriptor_size, size)
    headerbytes += instream.read(header_length - _BITMAP_FONT_HEAD.size)
    # if the header is shorter than 64 bytes, set everything beyond that to 0
    # by the spec, underline_position should be 5; we're ignoring that
    if len(headerbytes) < _BITMAP_FONT_DEF.size:
        logging.debug(
            'Truncated bitmap font header (descriptor size %d, header size %d)',
            fontdef.font_descriptor_size, size
        )
        headerbytes += bytes(_BITMAP_FONT_DEF.size - len(headerbytes))
    fontdef = _BITMAP_FONT_DEF.from_bytes(headerbytes[:_BITMAP_FONT_DEF.size])
    fontdef = Props(**vars(fontdef))
    if fontdef.descriptor_format == _HEADER_FMT_RES_BITMAP:
        extra = _RESOLUTION_EXT.from_bytes(headerbytes[_BITMAP_FONT_DEF.size:][:_RESOLUTION_EXT.size])
        fontdef |= Props(**vars(extra))
    else:
        logging.debug('skipped: %s', headerbytes[_BITMAP_FONT_DEF.size:])
    copyright = instream.read(size - header_length)
    read_until(instream, b'\x1b\x1a\0', 0)
    return fontdef, copyright


def _read_hppcl_glyphs(instream):
    """Read PCL character definitions."""
    glyphdefs = []
    while True:
        skipped, esc_cmd = read_until(instream, b'\x1b', 3)
        if skipped:
            logging.debug('Skipped bytes: %s', skipped)
        if not esc_cmd:
            break
        if esc_cmd != b'\x1b(s':
            if esc_cmd != b'\x1b*c':
                logging.warning(f'Expected character code; ignoring unexpected PCL command {esc_cmd}')
                continue
            codestr, _ = read_until(instream, b'Ee', 1)
            code = bytestr_to_int(codestr)
            skipped, esc_cmd = read_until(instream, b'\x1b', 3)
            if skipped:
                logging.debug('Skipped bytes: %s', skipped)
            if esc_cmd != b'\x1b(s':
                logging.warning(f'Expected glyph definition; ignoring unexpected PCL command {esc_cmd}')
                continue
        sizestr, _ = read_until(instream, b'W', 1)
        size = bytestr_to_int(sizestr)
        common = _LASERJET_CHAR_COMMON.read_from(instream)
        if common.format != _CHAR_FMT_LASERJET:
            raise FileFormatError(
                f'Unsupported charcter definition format ({common.format}.'
            )
        if common.continuation:
            glyphbytes = instream.read(size - _LASERJET_CHAR_COMMON.size)
            code, chardef, last_glyphbytes = glyphdefs[-1]
            glyphdefs[-1] = code, chardef, last_glyphbytes + glyphbytes
        else:
            chardef = _LASERJET_CHAR_DEF.read_from(instream)
            glyphbytes = instream.read(size - _LASERJET_CHAR_COMMON.size - _LASERJET_CHAR_DEF.size)
            glyphdefs.append((code, chardef, glyphbytes))
    return glyphdefs


###############################################################################
# reader utility functions

def read_until(instream, break_char, then_read=1):
    """Read bytes from stream until a given sentinel."""
    out = []
    c = instream.peek(1)[:1]
    while c and c not in break_char:
        out.append(instream.read(1))
        c = instream.peek(1)[:1]
    sep = instream.read(then_read)
    return b''.join(out), sep


def bytestr_to_int(bytestr):
    """Convert a bytes string representation to integer."""
    return int(bytestr.decode('ascii', 'replace'), 10)


###############################################################################
# writer

def _convert_to_hppcl_props(font, orientation):
    """Convert from monobit to PCL properties."""
    # Style Word = Posture + (4 x Width) + (32 x Structure)
    style_msb, style_lsb = bytes(_STYLE_WORD(
        # set structure to 'solid'
        structure=0,
        width=reverse_dict(_STYLE_WIDTH_MAP).get(font.setwidth, 0),
        posture=reverse_dict(_STYLE_POSTURE_MAP).get(font.slant, 0),
    ))
    typeface_msb, typeface_lsb = bytes(_TYPEFACE_WORD(
        vendor=reverse_dict(_VENDOR_MAP).get(font.foundry, 0),
        typeface_family=int(font.get_property('hppcl.family-id') or '0'),
    ))
    fontdef = _BITMAP_FONT_DEF(
        font_descriptor_size=_BITMAP_FONT_DEF.size,
        descriptor_format=_HEADER_FMT_BITMAP,
        # docs suggest (but do not say) bitmap font def only supports 7/8-bit bound
        symbol_set_type=2,
        style_msb=style_msb,
        reserved=0,
        baseline_position=4*font.descent,
        cell_width=font.bounding_box.x,
        cell_height=font.bounding_box.y,
        orientation=orientation,
        spacing=1 if font.spacing=='proportional' else 2 if font.spacing=='multi-cell' else 0,
        symbol_set=_symbol_set_from_encoding(font.encoding),
        pitch=4*int(font.average_width),
        height=4*font.point_size,
        x_height=4*font.x_height,
        width_type=reverse_dict(_SETWIDTH_MAP).get(font.setwidth, 0),
        style_lsb=style_lsb,
        stroke_weight=reverse_dict(_WEIGHT_MAP).get(font.weight, 0),
        typeface_lsb=typeface_lsb,
        typeface_msb=typeface_msb,
        serif_style=reverse_dict(_SERIF_MAP).get(font.style, 0),
        # set quality to draft
        quality=0,
        # > DEVICE NOTE: All DJ5xx fonts are treated as normal. LaserJets ignore this field.
        placement=0,
        underline_position=-font.underline_descent,
        underline_thickness=font.underline_thickness,
        text_height=4*font.line_height,
        # same as pitch?
        text_width=4*int(font.average_width),
        first_code=int(min(font.get_codepoints())),
        last_code=int(max(font.get_codepoints())),
        # ignoring the extra-precision bits
        pitch_extended=0,
        height_extended=0,
        cap_height=int(65536 * font.cap_height / font.pixel_size),
        # Bitmap Font - Should be ignored and set to 0
        font_number=0,
        font_name=font.name.encode('ascii', 'replace')[:16],
    )
    copyright = font.notice.encode('ascii', 'replace') + b'\0'
    return fontdef, copyright


def _convert_to_hppcl_glyph(glyph, orientation):
    """Convert from monobit to PCL glyph."""
    chardef = _LASERJET_CHAR_DEF(
        #format='uint8',
        #continuation='uint8',
        descriptor_size=_LASERJET_CHAR_DEF.size + _LASERJET_CHAR_COMMON.size,
        # class 1 is uncompressed bitmapp
        class_=1,
        orientation=orientation,
        reserved=0,
        delta_x=4*glyph.advance_width,
    )
    if orientation == 0:
        glyphbytes = glyph.as_bytes()
        chardef.left_offset = glyph.left_bearing
        chardef.top_offset = glyph.height+glyph.shift_up-1
        chardef.character_width=glyph.width
        chardef.character_height=glyph.height
    else:
        glyphbytes = glyph.turn(clockwise=-1).as_bytes()
        chardef.left_offset = -glyph.shift_up-glyph.height+1
        chardef.top_offset = glyph.left_bearing+glyph.width-1
        chardef.character_width = glyph.height
        chardef.character_height = glyph.width
    return int(glyph.codepoint), chardef, glyphbytes


def _symbol_set_from_encoding(encoding):
    """Convert encoding to symbol set code."""
    try:
        code = _REV_SYMBOL_SETS[charmaps.normalise(encoding)]
    except KeyError:
        if not encoding.startswith('pcl-'):
            return 0
        code = encoding.removeprefix('pcl-')
    if not len(code) == 2 or not code[0].isdigit():
        return 0
    num, lett = code
    return ord(lett)-64 + int(num)*32
