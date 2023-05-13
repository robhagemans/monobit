"""
monobit.formats.xlfd.pcf - X11 portable compiled format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...struct import big_endian as be, little_endian as le
from ...storage import loaders, savers
from ...magic import FileFormatError
from ...properties import Props
from ...font import Font
from ...glyph import Glyph
from ...raster import Raster
from ...labels import Tag, Codepoint
from ...binary import align

from .bdf import _parse_xlfd_properties


MAGIC = b'\1fcp'

@loaders.register(
    name='pcf',
    magic=(MAGIC,),
    patterns=('*.pcf',),
)
def load_pcf(instream):
    """Load font from X11 PCF font file."""
    pcf_data = _read_pcf(instream)
    glyphs = _convert_glyphs(pcf_data)
    props = _convert_props(pcf_data)
    return Font(glyphs, **props)


##############################################################################
# https://fontforge.org/docs/techref/pcf-format.html

_HEADER = le.Struct(
    # /* always "\1fcp" */
    header='4s',
    table_count='int32',
)

# fontforge recap has these as apparent signed ints,
# but X sources say CARD32 which is an unsigned int
_TOC_ENTRY = le.Struct(
    # /* See below, indicates which table */
    type='uint32',
    # /* See below, indicates how the data are formatted in the table */
    format='uint32',
    # /* In bytes */
    size='uint32',
    # /* from start of file */
    offset='uint32',
)

# format field
#define PCF_DEFAULT_FORMAT       0x00000000
#define PCF_INKBOUNDS           0x00000200
#define PCF_ACCEL_W_INKBOUNDS   0x00000100
PCF_ACCEL_W_INKBOUNDS = 0x00000100
#define PCF_COMPRESSED_METRICS  0x00000100
PCF_COMPRESSED_METRICS = 0x00000100

# format field modifiers
#define PCF_GLYPH_PAD_MASK       (3<<0)            /* See the bitmap table for explanation */
PCF_GLYPH_PAD_MASK = (3<<0)
#define PCF_BYTE_MASK           (1<<2)            /* If set then Most Sig Byte First */
PCF_BYTE_MASK = (1<<2)
#define PCF_BIT_MASK            (1<<3)            /* If set then Most Sig Bit First */
PCF_BIT_MASK = (1<<3)
#define PCF_SCAN_UNIT_MASK      (3<<4)            /* See the bitmap table for explanation */
PCF_SCAN_UNIT_MASK = (3<<4)

# type field
#define PCF_PROPERTIES               (1<<0)
PCF_PROPERTIES = (1<<0)
#define PCF_ACCELERATORS            (1<<1)
PCF_ACCELERATORS = (1<<1)
#define PCF_METRICS                 (1<<2)
PCF_METRICS = (1<<2)
#define PCF_BITMAPS                 (1<<3)
PCF_BITMAPS = (1<<3)
#define PCF_INK_METRICS             (1<<4)
PCF_INK_METRICS = (1<<4)
#define PCF_BDF_ENCODINGS           (1<<5)
PCF_BDF_ENCODINGS = (1<<5)
#define PCF_SWIDTHS                 (1<<6)
PCF_SWIDTHS = (1<<6)
#define PCF_GLYPH_NAMES             (1<<7)
PCF_GLYPH_NAMES = (1<<7)
#define PCF_BDF_ACCELERATORS        (1<<8)
PCF_BDF_ACCELERATORS = (1<<8)



# Properties table

# can be be or le
_PROPS = dict(
    name_offset='int32',
    isStringProp='int8',
    value='int32',
)

def _read_format(instream):
    format = int(le.uint32.read_from(instream))
    if format & PCF_BYTE_MASK:
        base = be
    else:
        base = le
    return format, base

def _read_properties_table(instream):
    format, base = _read_format(instream)
    nprops = base.uint32.read_from(instream)
    props = (base.Struct(**_PROPS) * nprops).read_from(instream)
    #  pad to next int32 boundary
    padding = instream.read(0 if nprops&3 == 0 else 4-(nprops&3))
    string_size = base.int32.read_from(instream)
    strings = instream.read(string_size)
    xlfd_props = {}
    for prop in props:
        name, _, rest = strings[prop.name_offset:].partition(b'\0')
        name = name.decode('latin-1', 'ignore')
        if prop.isStringProp:
            value, _, _ = rest.partition(b'\0')
            value = value.decode('latin-1', 'ignore')
        else:
            value = int(prop.value)
        xlfd_props[name] = value
    return xlfd_props

# Accelerator table

_UNCOMPRESSED_METRICS = dict(
    left_side_bearing='int16',
    right_side_bearing='int16',
    character_width='int16',
    character_ascent='int16',
    character_descent='int16',
    character_attributes='uint16',
)

# The (compressed) bytes are unsigned bytes which are offset by 0x80
# (so the actual value will be (getc(pcf_file)-0x80). :
_COMPRESSED_METRICS = dict(
    left_side_bearing='uint8',
    right_side_bearing='uint8',
    character_width='uint8',
    character_ascent='uint8',
    character_descent='uint8',
)


_ACC_TABLE = dict(
    noOverlap='uint8',
    constantMetrics='uint8',
    terminalFont='uint8',
    constantWidth='uint8',
    inkInside='uint8',
    inkMetrics='uint8',
    drawDirection='uint8',
    padding='uint8',
    fontAscent='int32',
    fontDescent='int32',
    maxOverlap='int32',
    # minbounds=_UNCOMPRESSED_METRICS,
    # maxbounds=_UNCOMPRESSED_METRICS,
)


def _read_acc_table(instream):
    format, base = _read_format(instream)
    acc_table = base.Struct(**_ACC_TABLE).read_from(instream)
    acc_table = vars(acc_table)
    uncompressed_metrics = base.Struct(**_UNCOMPRESSED_METRICS)
    acc_table.update(dict(
        minbounds=uncompressed_metrics.read_from(instream),
        maxbounds=uncompressed_metrics.read_from(instream),
    ))
    if format & PCF_ACCEL_W_INKBOUNDS:
        acc_table.update(dict(
            ink_minbounds=uncompressed_metrics.read_from(instream),
            ink_maxbounds=uncompressed_metrics.read_from(instream),
        ))
    return acc_table


def _read_metrics(instream):
    format, base = _read_format(instream)
    if format & PCF_COMPRESSED_METRICS:
        compressed_metrics = base.Struct(**_COMPRESSED_METRICS)
        count = base.int16.read_from(instream)
        metrics = (compressed_metrics * count).read_from(instream)
        # adjust unsigned bytes by 0x80 offset
        metrics = tuple(
            Props(**{_k: _v-0x80 for _k, _v in vars(_m).items()})
            for _m in metrics
        )
    else:
        uncompressed_metrics = base.Struct(**_UNCOMPRESSED_METRICS)
        count = base.int32.read_from(instream)
        metrics = (uncompressed_metrics * count).read_from(instream)
    return metrics


def _read_bitmaps(instream):
    format, base = _read_format(instream)
    glyph_count = base.int32.read_from(instream)
    offsets = (base.int32 * glyph_count).read_from(instream)
    bitmapSizes = (base.int32 * 4).read_from(instream)
    bitmap_size = bitmapSizes[format & 3]
    bitmap_data = instream.read(bitmap_size)
    offsets = tuple(offsets) + (None,)
    return format, tuple(
        bitmap_data[_offs:_next]
        for _offs, _next in zip(offsets, offsets[1:])
    )


_ENCODING_TABLE = dict(
    min_char_or_byte2='int16',
    max_char_or_byte2='int16',
    min_byte1 = 'int16',
    max_byte1 = 'int16',
    default_char = 'int16',
)

def _read_encoding(instream):
    format, base = _read_format(instream)
    enc = base.Struct(**_ENCODING_TABLE).read_from(instream)
    count = (enc.max_char_or_byte2-enc.min_char_or_byte2+1)*(enc.max_byte1-enc.min_byte1+1)
    # generate code points
    if not enc.min_byte1 and not enc.max_byte1:
        codepoints = (
            bytes((_cp,))
            for _cp in range(enc.min_char_or_byte2, enc.max_char_or_byte2+1)
        )
    else:
        codepoints = (
            bytes((_hi, _lo))
            for _hi in range(enc.min_char_or_byte2, enc.max_char_or_byte2+1)
            for _lo in range(enc.min_byte1, enc.max_byte1+1)
        )
    glyph_indices = (base.int16 * count).read_from(instream)
    encoding_dict = {
        _cp: _idx for _cp, _idx in zip(codepoints, glyph_indices)
    }
    return encoding_dict


def _read_swidths(instream):
    format, base = _read_format(instream)
    glyph_count = base.int32.read_from(instream)
    swidths = (base.int32 * glyph_count).read_from(instream)
    return swidths


def _read_glyph_names(instream):
    format, base = _read_format(instream)
    glyph_count = base.int32.read_from(instream)
    offsets = (base.int32 * glyph_count).read_from(instream)
    string_size = base.int32.read_from(instream)
    strings = instream.read(string_size)
    glyph_names = []
    for ofs in offsets:
        name, _, _ = strings[ofs:].partition(b'\0')
        name = name.decode('latin-1', 'ignore')
        glyph_names.append(name)
    return glyph_names


def _read_pcf(instream):
    """Read font from X11 PCF font file."""
    header = _HEADER.read_from(instream)
    toc = (_TOC_ENTRY * header.table_count).read_from(instream)
    props = Props()
    for entry in toc:
        instream.seek(entry.offset)
        if entry.type == PCF_PROPERTIES:
            props.xlfd_props = _read_properties_table(instream)
        elif entry.type == PCF_ACCELERATORS:
            # mandatory if BDF_ACCELERATORS not defined
            props.acc_props = _read_acc_table(instream)
        elif entry.type == PCF_BDF_ACCELERATORS:
            # optional
            props.bdf_acc_props = _read_acc_table(instream)
        elif entry.type == PCF_METRICS:
            # mandatory
            props.metrics = _read_metrics(instream)
        elif entry.type == PCF_INK_METRICS:
            # optional
            props.ink_metrics = _read_metrics(instream)
        elif entry.type == PCF_BITMAPS:
            # mandatory
            props.bitmap_format, props.bitmaps = _read_bitmaps(instream)
        elif entry.type == PCF_BDF_ENCODINGS:
            # mandatory, but could be empty
            props.encodings = _read_encoding(instream)
        elif entry.type == PCF_SWIDTHS:
            # optional - does not exist in X11 R6.4 sources
            props.swidths = _read_swidths(instream)
        elif entry.type == PCF_GLYPH_NAMES:
            # optional - does not exist in X11 R6.4 sources
            props.glyph_names = _read_glyph_names(instream)
    return props


###############################################################################
# converter

def _convert_glyphs(pcf_data):
    """Convert glyphs from X11 PCF data to monobit."""
    # label sets
    try:
        # if the table exists, the count should be the same as metrics count
        labelsets = [[Tag(_name)] for _name in pcf_data.glyph_names]
    except AttributeError:
        labelsets = [[] for _ in pcf_data.metrics]
    try:
        for _cp, _idx in pcf_data.encodings.items():
            labelsets[_idx].append(Codepoint(_cp))
    except AttributeError:
        pass
    # /* how each row in each glyph's bitmap is padded (format&3) */
    # /*  0=>bytes, 1=>shorts, 2=>ints */
    glyph_pad_length = pcf_data.bitmap_format & PCF_GLYPH_PAD_MASK
    byte_big = pcf_data.bitmap_format & PCF_BYTE_MASK
    bit_big = pcf_data.bitmap_format & PCF_BIT_MASK
    # /* what the bits are stored in (bytes, shorts, ints) (format>>4)&3 */
    # /*  0=>bytes, 1=>shorts, 2=>ints */
    scan_unit = pcf_data.bitmap_format & PCF_SCAN_UNIT_MASK
    # metrics are as defined in XCharStruct
    # https://tronche.com/gui/x/xlib/graphics/font-metrics/
    # typedef struct {
    # 	short lbearing;			/* origin to left edge of raster */
    # 	short rbearing;			/* origin to right edge of raster */
    # 	short width;			/* advance to next char's origin */
    # 	short ascent;			/* baseline to top edge of raster */
    # 	short descent;			/* baseline to bottom edge of raster */
    # 	unsigned short attributes;	/* per char flags (not predefined) */
    # } XCharStruct;
    #
    # X docs suggest a right-to-left character would have negative character_width (advance)
    # it is unclear about what this means for bearings, as the raster width is given to be rbearing-lbearing
    # in any case, in practice RTL chars appear to have positive metrics
    # see e.g. cuarabic12.pcf, 6x13-ISO8859-8.pcf
    # so we assume character width is always positive, and advance direction is
    # decided by the renderer (as we do it)
    #
    # ascent and descent determine the character height, which we instead infer
    # from bitmap and stride.
    glyphs = tuple(
        Glyph.from_bytes(
            _gb,
            width=_met.right_side_bearing-_met.left_side_bearing,
            stride=align(_met.right_side_bearing-_met.left_side_bearing, glyph_pad_length+3),
            bit_order='big' if bit_big else 'little',
            byte_swap=0 if byte_big else scan_unit+1,
            left_bearing=_met.left_side_bearing,
            right_bearing=_met.character_width-_met.right_side_bearing,
            shift_up=-_met.character_descent,
            labels=_labs,
        )
        for _gb, _met, _labs in zip(pcf_data.bitmaps, pcf_data.metrics, labelsets)
    )
    return glyphs


def _convert_props(pcf_data):
    xlfd_name = pcf_data.xlfd_props.pop('FONT', '')
    pcf_data.xlfd_props = {_k: str(_v) for _k, _v in pcf_data.xlfd_props.items()}
    props = _parse_xlfd_properties(pcf_data.xlfd_props, xlfd_name)
    return props
