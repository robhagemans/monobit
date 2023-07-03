"""
monobit.formats.xlfd.pcf - X11 portable compiled format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ...struct import big_endian as be, little_endian as le
from ...storage import loaders, savers
from ...magic import FileFormatError
from ...properties import Props
from ...font import Font
from ...glyph import Glyph
from ...raster import Raster
from ...labels import Tag, Codepoint
from ...binary import align, ceildiv

from .bdf import swidth_to_pixel, pixel_to_swidth
from .xlfd import (
    parse_xlfd_properties, create_xlfd_properties, create_xlfd_name,
    from_quoted_string
)

MAGIC = b'\1fcp'

@loaders.register(
    name='pcf',
    magic=(MAGIC,),
    patterns=('*.pcf',),
)
def load_pcf(instream):
    """Load font from X11 Portable Compiled Format (PCF)."""
    pcf_data = _read_pcf(instream)
    glyphs = _convert_glyphs(pcf_data)
    props = _convert_props(pcf_data)
    font = Font(glyphs, **props)
    return font.label()

@savers.register(linked=load_pcf)
def save_pcf(
        fonts, outstream, *,
        byte_order:str='big', ink_bounds:bool=True, scan_unit:int=1,
        padding_bytes:int=1, bit_order:str='big',
    ):
    """
    Save font to X11 Portable Compiled Format (PCF).

    ink_bounds: include optional ink-bounds metrics (default: True)
    byte_order: 'big'-endian (default) or 'little'-endian
    bit_order: 'big'-endian (default) if left pixel is most significant bit, or 'little'-endian if left is lsb
    scan_unit: number of bytes per unit in bitmap (1, 2, 4 or 8; default is 1)
    padding_bytes: make raster row a multiple of this number of bytes (1, 2, 4 or 8; default is 1)
    """
    font, *more = fonts
    if more:
        raise FileFormatError('Can only save one font to BDF file.')
    # can only do big-endian for now
    _write_pcf(
        outstream, font, endian=byte_order, create_ink_bounds=ink_bounds,
        scan_unit=scan_unit, padding_bytes=padding_bytes, bit_order=bit_order,
    )
    return font

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
PCF_DEFAULT_FORMAT = 0x00000000
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
            props.encodings, props.default_char = _read_encoding(instream)
        elif entry.type == PCF_SWIDTHS:
            # optional - does not exist in X11 R6.4 sources
            props.swidths = _read_swidths(instream)
        elif entry.type == PCF_GLYPH_NAMES:
            # optional - does not exist in X11 R6.4 sources
            props.glyph_names = _read_glyph_names(instream)
    return props


def _read_format(instream):
    """Read the format record at start of tables."""
    format = int(le.uint32.read_from(instream))
    if format & PCF_BYTE_MASK:
        base = be
    else:
        base = le
    return format, base


# Properties table

# can be be or le
_PROPS = dict(
    name_offset='int32',
    isStringProp='int8',
    value='int32',
)

def _read_properties_table(instream):
    """Read the Properties table."""
    format, base = _read_format(instream)
    nprops = base.uint32.read_from(instream)
    props = (base.Struct(**_PROPS) * nprops).read_from(instream)
    #  pad to next int32 boundary
    padding = instream.read(0 if nprops&3 == 0 else 4-(nprops&3))
    string_size = base.int32.read_from(instream)
    strings = instream.read(string_size)
    xlfd_props = {}
    for prop in props:
        name, _, _ = strings[prop.name_offset:].partition(b'\0')
        name = name.decode('latin-1', 'ignore')
        if prop.isStringProp:
            value, _, _ = strings[int(prop.value):].partition(b'\0')
            value = value.decode('latin-1', 'ignore')
        else:
            value = int(prop.value)
        xlfd_props[name] = value
    return xlfd_props


# Glyph metrics and ink-metrics

# There are two different metrics tables, PCF_METRICS and PCF_INK_METRICS, the
# former contains the size of the stored bitmaps, while the latter contains the
# minimum bounding box. The two may contain the same data, but many CJK fonts
# pad the bitmaps so all bitmaps are the same size.

# from https://tronche.com/gui/x/xlib/graphics/font-metrics/#XCharStruct
# typedef struct {
# 	short lbearing;			/* origin to left edge of raster */
# 	short rbearing;			/* origin to right edge of raster */
# 	short width;			/* advance to next char's origin */
# 	short ascent;			/* baseline to top edge of raster */
# 	short descent;			/* baseline to bottom edge of raster */
# 	unsigned short attributes;	/* per char flags (not predefined) */
# } XCharStruct;

# X docs suggest a right-to-left character would have negative character_width (advance)
# it is unclear about what this means for bearings, as the raster width is given to be rbearing-lbearing
# in any case, in practice RTL chars appear to have positive metrics
# see e.g. cuarabic12.pcf, 6x13-ISO8859-8.pcf
# so we assume character width is always positive, and advance direction is
# decided by the renderer (as we do it)

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


# Accelerator table

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
    # minimum and maximum value for each metric
    #minbounds=_UNCOMPRESSED_METRICS,
    #maxbounds=_UNCOMPRESSED_METRICS,
    # if format PCF_ACCEL_W_INKBOUNDS:
    # maximum and maximum value for each ink metric
    ##ink_minbounds=_UNCOMPRESSED_METRICS,
    ##ink_maxbounds=_UNCOMPRESSED_METRICS,
)


def _read_acc_table(instream):
    """Read the Accelerator or BDF Accelerator table."""
    format, base = _read_format(instream)
    acc_table = base.Struct(**_ACC_TABLE).read_from(instream)
    acc_table = Props(**vars(acc_table))
    uncompressed_metrics = base.Struct(**_UNCOMPRESSED_METRICS)
    acc_table |= Props(
        minbounds=uncompressed_metrics.read_from(instream),
        maxbounds=uncompressed_metrics.read_from(instream),
    )
    if format & PCF_ACCEL_W_INKBOUNDS:
        acc_table |= Props(
            ink_minbounds=uncompressed_metrics.read_from(instream),
            ink_maxbounds=uncompressed_metrics.read_from(instream),
        )
    return acc_table


def _read_metrics(instream):
    """Read the Metrics or Ink-Metrics table."""
    format, base = _read_format(instream)
    if format & PCF_COMPRESSED_METRICS:
        compressed_metrics = base.Struct(**_COMPRESSED_METRICS)
        # documented as signed int, but unsigned it makes more sense
        # also this is used as uint by bdftopcf for e.g. unifont
        count = base.uint16.read_from(instream)
        metrics = (compressed_metrics * count).read_from(instream)
        # adjust unsigned bytes by 0x80 offset
        metrics = tuple(
            Props(**{_k: _v-0x80 for _k, _v in vars(_m).items()})
            for _m in metrics
        )
    else:
        uncompressed_metrics = base.Struct(**_UNCOMPRESSED_METRICS)
        count = base.uint32.read_from(instream)
        metrics = (uncompressed_metrics * count).read_from(instream)
    return metrics


def _read_bitmaps(instream):
    """Read the Bitmaps table."""
    format, base = _read_format(instream)
    glyph_count = base.int32.read_from(instream)
    offsets = (base.int32 * glyph_count).read_from(instream)
    bitmap_sizes = (base.int32 * 4).read_from(instream)
    bitmap_size = bitmap_sizes[format & 3]
    bitmap_data = instream.read(bitmap_size)
    offsets = tuple(offsets) + (None,)
    return format, tuple(
        bitmap_data[_offs:_next]
        for _offs, _next in zip(offsets, offsets[1:])
    )

# from https://tronche.com/gui/x/xlib/graphics/font-metrics/#XFontStruct
# typedef struct {
# 	XExtData *ext_data;		/* hook for extension to hang data */
# 	Font fid;			/* Font id for this font */
# 	unsigned direction;		/* hint about the direction font is painted */
# 	unsigned min_char_or_byte2;	/* first character */
# 	unsigned max_char_or_byte2;	/* last character */
# 	unsigned min_byte1;		/* first row that exists */
# 	unsigned max_byte1;		/* last row that exists */
# 	Bool all_chars_exist;		/* flag if all characters have nonzero size */
# 	unsigned default_char;		/* char to print for undefined character */
# 	int n_properties;		/* how many properties there are */
# 	XFontProp *properties;		/* pointer to array of additional properties */
# 	XCharStruct min_bounds;		/* minimum bounds over all existing char */
# 	XCharStruct max_bounds;		/* maximum bounds over all existing char */
# 	XCharStruct *per_char;		/* first_char to last_char information */
# 	int ascent;			/* logical extent above baseline for spacing */
# 	int descent;			/* logical decent below baseline for spacing */
# } XFontStruct;

# FontForge docs suggest the encoding table has signed integers
# but the XFontStruct has them unsigned
# they also make more sense unsigned, especially default_char which may be two-byte.
_ENCODING_TABLE = dict(
    min_char_or_byte2='uint16',
    max_char_or_byte2='uint16',
    min_byte1='uint16',
    max_byte1='uint16',
    default_char='uint16',
)

def _generate_codepoints(enc):
    """Generate all code points based on encoding table."""
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
    return codepoints

def _read_encoding(instream):
    format, base = _read_format(instream)
    enc = base.Struct(**_ENCODING_TABLE).read_from(instream)
    count = (enc.max_char_or_byte2-enc.min_char_or_byte2+1)*(enc.max_byte1-enc.min_byte1+1)
    # generate code points
    codepoints = _generate_codepoints(enc)
    glyph_indices = (base.int16 * count).read_from(instream)
    encoding_dict = {
        _cp: _idx for _cp, _idx in zip(codepoints, glyph_indices)
        # -1 means 'not used'
        if _idx >= 0
    }
    return encoding_dict, enc.default_char


def _read_swidths(instream):
    """Read the Scalable Widths table."""
    format, base = _read_format(instream)
    glyph_count = base.uint32.read_from(instream)
    swidths = (base.int32 * glyph_count).read_from(instream)
    return swidths


def _read_glyph_names(instream):
    """Read the Glyph Names table."""
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


###############################################################################
# converter

def _convert_glyphs(pcf_data):
    """Convert glyphs from X11 PCF data to monobit."""
    # label sets
    n_glyphs = len(pcf_data.metrics)
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
    # scalable width reference values
    if hasattr(pcf_data, 'swidths'):
        dpi_y = pcf_data.xlfd_props.get('RESOLUTION_Y', 72)
        try:
            point_size = pcf_data.xlfd_props['POINT_SIZE'] / 10
        except KeyError:
            try:
                point_size = pcf_data.xlfd_props['PIXEL_SIZE'] * dpi_y / 72 / 10
            except KeyError:
                logging.warning('No point-size information - dropping scalable width table')
                # can't calculate swidths
                pcf_data.swidths = None
    if hasattr(pcf_data, 'swidths') and pcf_data.swidths:
        pcf_data.swidths = tuple(
            swidth_to_pixel(_swidth, point_size, dpi_y)
            for _swidth in pcf_data.swidths
        )
    else:
        pcf_data.swidths = (None,) * n_glyphs
    # /* how each row in each glyph's bitmap is padded (format&3) */
    # /*  0=>bytes, 1=>shorts, 2=>ints */
    glyph_pad_length = pcf_data.bitmap_format & PCF_GLYPH_PAD_MASK
    byte_big = pcf_data.bitmap_format & PCF_BYTE_MASK
    bit_big = pcf_data.bitmap_format & PCF_BIT_MASK
    # /* what the bits are stored in (bytes, shorts, ints) (format>>4)&3 */
    # /*  0=>bytes, 1=>shorts, 2=>ints */
    scan_unit = (pcf_data.bitmap_format & PCF_SCAN_UNIT_MASK) >> 4
    # metrics are as defined in XCharStruct (above)
    # https://tronche.com/gui/x/xlib/graphics/font-metrics/
    # ascent and descent determine the character height, which we instead infer
    # from bitmap and stride.
    glyphs = tuple(
        Glyph.from_bytes(
            _gb,
            width=_met.right_side_bearing-_met.left_side_bearing,
            stride=align(_met.right_side_bearing-_met.left_side_bearing, glyph_pad_length+3),
            height=_met.character_ascent+_met.character_descent,
            bit_order='big' if bit_big else 'little',
            byte_swap=0 if (bool(byte_big) == bool(bit_big)) else 2**scan_unit,
            left_bearing=_met.left_side_bearing,
            right_bearing=_met.character_width-_met.right_side_bearing,
            shift_up=-_met.character_descent,
            scalable_width=_swidth if _swidth != _met.character_width else None,
            labels=_labs,
        )
        for _gb, _met, _labs, _swidth in zip(
            pcf_data.bitmaps, pcf_data.metrics, labelsets, pcf_data.swidths
        )
    )
    return glyphs


def _convert_props(pcf_data):
    """Convert properties for PCF to monobit."""
    xlfd_name = pcf_data.xlfd_props.pop('FONT', '')
    pcf_data.xlfd_props = {_k: str(_v) for _k, _v in pcf_data.xlfd_props.items()}
    props = parse_xlfd_properties(pcf_data.xlfd_props, xlfd_name)
    props.update(dict(
        default_char=Codepoint(pcf_data.default_char),
    ))
    # ascent and descent - these are stored in accelerator table rather than XLFD props
    if hasattr(pcf_data, 'bdf_acc_props'):
        props.update(dict(
            ascent=pcf_data.bdf_acc_props.fontAscent,
            descent=pcf_data.bdf_acc_props.fontDescent,
        ))
    elif hasattr(pcf_data, 'acc_props'):
        props.update(dict(
            ascent=pcf_data.acc_props.fontAscent,
            descent=pcf_data.acc_props.fontDescent,
        ))
    return props


###############################################################################
# pcf writer

def _write_pcf(
        outstream, font,
        endian, create_ink_bounds, scan_unit, padding_bytes, bit_order,
    ):
    """Write font to X11 PCF font file."""
    if endian[:1].lower() == 'b':
        base = be
    else:
        base = le
    # full format needs to be repeated in every table (at least the low byte)
    # or pcf2bdf won't recognise the bitmaps correctly
    format = PCF_DEFAULT_FORMAT
    if bit_order[:1].lower() == 'b':
        format |= PCF_BIT_MASK
    if base == be:
        format |= PCF_BYTE_MASK
    # /* how each row in each glyph's bitmap is padded (format&3) */
    # /*  0=>bytes, 1=>shorts, 2=>ints */
    # do a int(log2())
    format |= (padding_bytes.bit_length()-1) & PCF_GLYPH_PAD_MASK
    # /* what the bits are stored in (bytes, shorts, ints) (format>>4)&3 */
    # /*  0=>bytes, 1=>shorts, 2=>ints */
    format |= ((scan_unit.bit_length()-1) << 4) & PCF_SCAN_UNIT_MASK
    # tables MUST be in this order or pcf2bdf will reject the file
    tables = (
        (PCF_PROPERTIES, *_create_properties_table(font, format, base)),
        (PCF_ACCELERATORS, *_create_acc_table(font, format, base, create_ink_bounds)),
        (PCF_METRICS, *_create_metrics_table(font, format, base, _create_glyph_metrics)),
        # pcf2bdf doesn't read ink metrics, assume they go here?
        (PCF_INK_METRICS, *_create_metrics_table(font, format, base, _create_ink_metrics)),
        (PCF_BITMAPS, *_create_bitmaps(
            font, format, base,
            scan_unit_bytes=scan_unit, padding_bytes=padding_bytes,
            bit_order=bit_order,
        )),
        (PCF_BDF_ENCODINGS, *_create_encoding(font, format, base)),
        (PCF_SWIDTHS, *_create_swidths(font, format, base)),
        (PCF_GLYPH_NAMES, *_create_glyph_names(font, format, base)),
        # we're using the same table for accelerators and BDF accelerators
        # intended difference is unclear
        (PCF_BDF_ACCELERATORS, *_create_acc_table(font, format, base, create_ink_bounds)),
    )
    # calculate offsets, construct ToC
    offset = _HEADER.size + _TOC_ENTRY.size * len(tables)
    toc = []
    for type, table, format in tables:
        toc.append(_TOC_ENTRY(
            type=type,
            format=format,
            size=len(table),
            offset=offset,
        ))
        # align on 2**5==32-bit boundaries
        offset += align(len(table), 5)
    # write out file
    header = _HEADER(header=MAGIC, table_count=len(tables))
    outstream.write(bytes(header))
    for entry in toc:
        outstream.write(bytes(entry))
    for (_, table, _), next in zip(tables, toc[1:] + [None]):
        outstream.write(table)
        # padding
        if next:
            outstream.write(bytes(next.offset - outstream.tell()))



def _create_properties_table(font, format, base):
    """Create the Properties table."""
    propstrings = bytearray()
    xlfd_props = create_xlfd_properties(font)
    xlfd_props['FONT'] = create_xlfd_name(xlfd_props)
    props = []
    props_struct = base.Struct(**_PROPS)
    for key, value in xlfd_props.items():
        prop = props_struct(
            name_offset=len(propstrings),
            isStringProp=isinstance(value, str),
        )
        propstrings += key.encode('ascii', 'replace') + b'\0'
        if prop.isStringProp:
            prop.value = len(propstrings)
            value = from_quoted_string(value)
            propstrings += value.encode('ascii', 'replace') + b'\0'
        else:
            prop.value = int(value)
        props.append(prop)
    table_bytes = (
        bytes(le.uint32(format))
        + bytes(base.uint32(len(props)))
        + bytes((props_struct * len(props))(*props))
        # pad to next int32 boundary
        + bytes(0 if len(props)&3 == 0 else 4-(len(props)&3))
        + bytes(base.uint32(len(propstrings)))
        + bytes(propstrings)
    )
    return table_bytes, format


def _create_glyph_metrics(glyph, base):
    """Convert monobit glyph properties to PCF metrics."""
    metrics = base.Struct(**_UNCOMPRESSED_METRICS)(
        left_side_bearing=glyph.left_bearing,
        right_side_bearing=glyph.left_bearing + glyph.width,
        character_width=glyph.advance_width,
        character_ascent=glyph.height+glyph.shift_up,
        character_descent=-glyph.shift_up,
        character_attributes=0,
    )
    return metrics

def _create_ink_metrics(glyph, base):
    """Create the Ink Metrics table."""
    return _create_glyph_metrics(glyph.reduce(), base)


def _aggregate_metrics(metrics, aggfunc, base):
    """Get minimum or maximum from listo of metrics."""
    return base.Struct(**_UNCOMPRESSED_METRICS)(
        left_side_bearing=aggfunc(_m.left_side_bearing for _m in metrics),
        right_side_bearing=aggfunc(_m.right_side_bearing for _m in metrics),
        character_width=aggfunc(_m.character_width for _m in metrics),
        character_ascent=aggfunc(_m.character_ascent for _m in metrics),
        character_descent=aggfunc(_m.character_descent for _m in metrics),
        character_attributes=0,
    )

# xc/lib/font/util/fontaccel.c
# FontComputeInfoAccelerators(pFontInfo)
#     FontInfoPtr pFontInfo;
# {
#     pFontInfo->noOverlap = FALSE;
#     if (pFontInfo->maxOverlap <= pFontInfo->minbounds.leftSideBearing)
# 	pFontInfo->noOverlap = TRUE;
#
#     if ((pFontInfo->minbounds.ascent == pFontInfo->maxbounds.ascent) &&
# 	    (pFontInfo->minbounds.descent == pFontInfo->maxbounds.descent) &&
# 	    (pFontInfo->minbounds.leftSideBearing ==
# 	     pFontInfo->maxbounds.leftSideBearing) &&
# 	    (pFontInfo->minbounds.rightSideBearing ==
# 	     pFontInfo->maxbounds.rightSideBearing) &&
# 	    (pFontInfo->minbounds.characterWidth ==
# 	     pFontInfo->maxbounds.characterWidth) &&
#       (pFontInfo->minbounds.attributes == pFontInfo->maxbounds.attributes)) {
# 	pFontInfo->constantMetrics = TRUE;
# 	if ((pFontInfo->maxbounds.leftSideBearing == 0) &&
# 		(pFontInfo->maxbounds.rightSideBearing ==
# 		 pFontInfo->maxbounds.characterWidth) &&
# 		(pFontInfo->maxbounds.ascent == pFontInfo->fontAscent) &&
# 		(pFontInfo->maxbounds.descent == pFontInfo->fontDescent))
# 	    pFontInfo->terminalFont = TRUE;
# 	else
# 	    pFontInfo->terminalFont = FALSE;
#     } else {
# 	pFontInfo->constantMetrics = FALSE;
# 	pFontInfo->terminalFont = FALSE;
#     }
#     if (pFontInfo->minbounds.characterWidth == pFontInfo->maxbounds.characterWidth)
# 	pFontInfo->constantWidth = TRUE;
#     else
# 	pFontInfo->constantWidth = FALSE;
#
#     if ((pFontInfo->minbounds.leftSideBearing >= 0) &&
# 	    (pFontInfo->maxOverlap <= 0) &&
# 	    (pFontInfo->minbounds.ascent >= -pFontInfo->fontDescent) &&
# 	    (pFontInfo->maxbounds.ascent <= pFontInfo->fontAscent) &&
# 	    (-pFontInfo->minbounds.descent <= pFontInfo->fontAscent) &&
# 	    (pFontInfo->maxbounds.descent <= pFontInfo->fontDescent))
# 	pFontInfo->inkInside = TRUE;
#     else
# 	pFontInfo->inkInside = FALSE;
# }

def _create_acc_table(font, format, base, create_ink_bounds):
    """Create the Accelerators table."""
    if create_ink_bounds:
        format |= PCF_ACCEL_W_INKBOUNDS
    if not font.glyphs:
        raise ValueError('No glyphs in font.')
    metrics = tuple(_create_glyph_metrics(_g, base) for _g in font.glyphs)
    ink_metrics = tuple(_create_ink_metrics(_g, base) for _g in font.glyphs)
    minbounds = _aggregate_metrics(metrics, min, base)
    maxbounds = _aggregate_metrics(metrics, max, base)
    if create_ink_bounds:
        ink_minbounds = _aggregate_metrics(ink_metrics, min, base)
        ink_maxbounds = _aggregate_metrics(ink_metrics, max, base)
    # based on fontaccel.c code and FontForge's reverse engineered description
    # this is max(left_bearing + width - advance_width) == max(-right_bearing)
    maxOverlap = max(_m.right_side_bearing - _m.character_width for _m in metrics)
    # based on fontaccel.c
    constantMetrics = minbounds == maxbounds
    # checked against bdftopcf and pcf2bdf - these are bdf's FONT_ASCENT and FONT_DESCENT
    # which are kept only here and not in XLFD properties
    fontAscent = font.ascent
    fontDescent = font.descent
    acc_table = base.Struct(**_ACC_TABLE)(
        # /* if for all i, max(metrics[i].rightSideBearing - metrics[i].characterWidth) */
        # /*      <= minbounds.leftSideBearing */
        noOverlap=(maxOverlap <= minbounds.left_side_bearing),
        # /* Means the perchar field of the XFontStruct can be NULL */
        constantMetrics=constantMetrics,
        # /* constantMetrics true and forall characters: */
        # /*      the left side bearing==0 */
        # /*      the right side bearing== the character's width */
        # /*      the character's ascent==the font's ascent */
        # /*      the character's descent==the font's descent */
        terminalFont=(
            constantMetrics
            and (maxbounds.left_side_bearing == 0)
            and (maxbounds.right_side_bearing == maxbounds.character_width)
            and (maxbounds.character_ascent == fontAscent)
            and (maxbounds.character_descent == fontDescent)
        ),
        # /* monospace font like courier */
        constantWidth=(minbounds.character_width == maxbounds.character_width),
        # /* Means that all inked bits are within the rectangle with x between [0,charwidth] */
        # /*  and y between [-descent,ascent]. So no ink overlaps another char when drawing */
        # ===> this seems to imply fontAscent + fontDescent includes leading
        inkInside=(
            (minbounds.left_side_bearing >= 0)
            and (maxOverlap <= 0)
            and (minbounds.character_ascent >= -fontDescent)
            and (maxbounds.character_ascent <= fontAscent)
            and (-minbounds.character_descent <= fontAscent)
            and (maxbounds.character_descent <= fontDescent)
        ),
        # /* true if the ink metrics differ from the metrics somewhere */
        inkMetrics=create_ink_bounds and any(_m != _i for _m, _i in zip(metrics, ink_metrics)),
        # /* 0=>left to right, 1=>right to left */
        # however in practice this is set to 0 even on fonts with RTL glyphs
        # e.g. /usr/share/fonts/arabic24.pcf.gz
        drawDirection=0,
        padding=0,
        fontAscent=fontAscent,
        fontDescent=fontDescent,
        # where set in X11 code?
        maxOverlap=maxOverlap,
        # minbounds=_UNCOMPRESSED_METRICS,
        # maxbounds=_UNCOMPRESSED_METRICS,
    )
    table_bytes = [
        bytes(le.uint32(format)),
        bytes(acc_table),
        bytes(minbounds),
        bytes(maxbounds),
    ]
    if create_ink_bounds:
        table_bytes.extend([
            bytes(ink_minbounds),
            bytes(ink_maxbounds),
    ])
    return b''.join(table_bytes), format


def _create_metrics_table(font, format, base, create_glyph_metrics):
    """Create the Metrics table."""
    # we don't set PCF_COMPRESSED_METRICS
    metrics = tuple(create_glyph_metrics(_g, base) for _g in font.glyphs)
    table_bytes = (
        bytes(le.uint32(format))
        + bytes(base.int32(len(metrics)))
        + b''.join(bytes(_t) for _t in metrics)
    )
    return table_bytes, format


def _create_bitmaps(
        font, format, base,
        scan_unit_bytes=1, padding_bytes=1, bit_order='little',
    ):
    """Create the Bitmaps table."""
    byte_big = base == be
    bit_big = bit_order[:1].lower() == 'b'
    bitmaps = (
        _g.as_bytes(
            # align rows on padding_bytes boundaries
            stride=ceildiv(_g.width, padding_bytes*8) * padding_bytes*8,
            byte_swap=0 if (bool(byte_big) == bool(bit_big)) else scan_unit_bytes,
            bit_order='big' if bit_big else 'little',
        )
        for _g in font.glyphs
    )
    # align full byte sequence on scan_unit boundaries
    bitmaps = tuple(
        _bits.ljust(ceildiv(len(_bits), scan_unit_bytes) * scan_unit_bytes)
        for _bits in bitmaps
    )
    offsets = tuple(accumulate((len(_b) for _b in bitmaps), initial=0))[:-1]
    offsets = (base.int32 * len(bitmaps))(*offsets)
    bitmap_data = b''.join(bitmaps)
    # bytes # shorts # ints #?
    # apparently we do need to calculate all 4
    bitmap_sizes = [
        sum(
            # align full byte sequence on scan_unit boundaries
            ceildiv(
                # align rows on padding_bytes boundaries
                _g.pixels.get_byte_size(stride=ceildiv(_g.width, 8*2**_p) * 8*(2**_p)),
                scan_unit_bytes
            ) * scan_unit_bytes
            for _g in font.glyphs
        )
        for _p in range(4)
    ]
    assert bitmap_sizes[format&3] == len(bitmap_data), f'{bitmap_sizes[format&3]} != {len(bitmap_data)}'
    bitmap_sizes = (base.int32 * 4)(*bitmap_sizes)
    table_bytes = (
        bytes(le.uint32(format))
        + bytes(base.int32(len(offsets)))
        + bytes(offsets)
        + bytes(bitmap_sizes)
        + bitmap_data
    )
    return table_bytes, format


def _create_encoding(font, format, base):
    """Create the Encoding table."""
    font = font.label(codepoint_from=font.encoding)
    enc = base.Struct(**_ENCODING_TABLE)(
        default_char=int(font.get_default_glyph().codepoint or 0)
    )
    codepoints = font.get_codepoints()
    if not codepoints:
        raise ValueError('No storable code points in font.')
    byte_length = len(max(codepoints))
    if byte_length > 2:
        logging.warning(
            'Code points greater than 2 bytes cannot be stored in PCF.'
        )
    elif byte_length == 1:
        enc.min_byte1 = enc.max_byte1 = 0
        enc.min_char_or_byte2 = ord(min(codepoints))
        enc.max_char_or_byte2 = ord(max(codepoints))
    elif byte_length == 2:
        byte2 = [_cp[0] for _cp in codepoints if len(_cp) == 2]
        if any(len(_cp) == 1 for _cp in codepoints):
            byte2.append(0)
        enc.min_char_or_byte2 = min(byte2)
        enc.max_char_or_byte2 = max(byte2)
        byte1 = tuple(_cp[-1] for _cp in codepoints)
        enc.min_byte1 = min(byte1)
        enc.max_byte1 = max(byte1)
    glyph_indices = []
    for cp in _generate_codepoints(enc):
        try:
            index = font.get_index(cp)
        except KeyError:
            # -1 means 'not used'
            index = -1
        glyph_indices.append(index)
    glyph_indices = (base.int16 * len(glyph_indices))(*glyph_indices)
    table_bytes = (
        bytes(le.uint32(format))
        + bytes(enc)
        + bytes(glyph_indices)
    )
    return table_bytes, format


def _create_swidths(font, format, base):
    """Create the Scalable Widths table."""
    swidths = (base.int32 * len(font.glyphs))(*(
        pixel_to_swidth(_g.scalable_width, font.point_size, font.dpi.x)
        for _g in font.glyphs
    ))
    table_bytes = (
        bytes(le.uint32(format))
        + bytes(base.uint32(len(swidths)))
        + bytes(swidths)
    )
    return table_bytes, format


def _create_glyph_names(font, format, base):
    """Create the Glyph Names table."""
    names = tuple(
        _g.tags[0].value.encode('ascii', 'replace') + b'\0'
        if _g.tags else b'glyph%d\0' % (_i,)
        for _i, _g in enumerate(font.glyphs)
    )
    strings = b''.join(_n for _n in names)
    offsets = tuple(accumulate((len(_n) for _n in names), initial=0))[:-1]
    offsets = (base.uint32 * len(names))(*offsets)
    table_bytes = (
        bytes(le.uint32(format))
        + bytes(base.uint32(len(offsets)))
        + bytes(offsets)
        + bytes(base.uint32(len(strings)))
        + strings
    )
    return table_bytes, format
