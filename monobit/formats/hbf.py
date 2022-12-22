"""
monobit.hbf - Hanzi Bitmap File Format

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..properties import normalise_property
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font, Coord
from ..glyph import Glyph
from ..binary import ceildiv

from .bdf import read_props, _parse_xlfd_properties



##############################################################################
# top-level calls

@loaders.register('hbf', magic=(b'HBF_START_FONT ',), name='hanzi-bf')
def load_hbf(instream, where):
    """
    Load font from Hanzi Bitmap Format (HBF) file.
    """
    instream = instream.text
    comments, hbf_props, x_props, b2_ranges, c_ranges = _read_hbf_global(instream)
    logging.info('hbf properties:')
    for name, value in hbf_props.items():
        logging.info('    %s: %s', name, value)
    logging.info('x properties:')
    for name, value in x_props.items():
        logging.info('    %s: %s', name, value)
    glyphs = _read_hbf_glyphs(instream, where, b2_ranges, c_ranges, hbf_props)
    # check number of characters, but don't break if no match
    # if nchars != len(glyphs):
    #     logging.warning('Number of characters found does not match CHARS declaration.')
    properties = _parse_properties(hbf_props, x_props)
    font = Font(glyphs, comment=comments, **properties)
    #TODO: label glyphs with code scheme
    return font


##############################################################################
# HBF reader

# https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/Format.html
# https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/BitmapFile.html
# https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/CodeSchemes.html


def _read_hbf_global(instream):
    """Read global section of HBF file."""
    props_0, comments_0 = read_props(instream, end='STARTPROPERTIES')
    x_props, x_comments = read_props(instream, end='ENDPROPERTIES')
    props_1, comments_1 = read_props(instream, end='HBF_START_BYTE_2_RANGES')
    b2_ranges, b2_comments = _read_list(instream, end='HBF_END_BYTE_2_RANGES')
    props_2, comments_2 = read_props(instream, end='HBF_START_CODE_RANGES')
    c_ranges, c_comments = _read_list(instream, end='HBF_END_CODE_RANGES')
    props_3, comments_3 = read_props(instream, end='HBF_END_FONT')
    hbf_props = {**props_0, **props_1, **props_2, **props_3}
    comments = '\n'.join(
        '\n'.join(_list)
        for _list in (
            comments_0, x_comments, comments_1, b2_comments,
            comments_2, c_comments, comments_3
        )
    )
    return comments, hbf_props, x_props, b2_ranges, c_ranges


def _read_list(instream, end):
    """Read values (with ignored keys) with comments."""
    # read global section
    output = []
    comments = []
    for line in instream:
        line = line.strip()
        if not line:
            continue
        if line.startswith('COMMENT'):
            comments.append(line[8:])
            continue
        keyword, _, value = line.partition(' ')
        if keyword == end:
            break
        else:
            output.append(value)
    return output, comments

def indexer(code_range, b2_ranges):
    """Gnenerator to run through code range keeping to allowed low-bytes."""
    if not code_range:
        return
    for codepoint in code_range:
        lobyte = codepoint % 256
        if all(lobyte not in _range for _range in b2_ranges):
            continue
        yield codepoint

def _read_hbf_glyphs(instream, where, b2_ranges, c_ranges, props):
    """Read glyphs from bitmap files and index according to ranges."""
    width, height, _, _ = _split_hbf_ints(props['HBF_BITMAP_BOUNDING_BOX'])
    bytesize = height * ceildiv(width, 8)
    b2_ranges = tuple(
        _split_hbf_ints(_range, sep='-')
        for _range in b2_ranges
    )
    b2_ranges = tuple(
        range(_range[0], _range[1]+1)
        for _range in b2_ranges
    )
    code_ranges = []
    glyphs = []
    for c_desc in c_ranges:
        code_range, filename, offset = c_desc.split()
        code_range = _split_hbf_ints(code_range, sep='-')
        code_range = range(code_range[0], code_range[1]+1)
        offset = hbf_int(offset)
        with where.open(filename, 'r') as bitmapfile:
            # discard offset bytes
            bitmapfile.read(offset)
            for codepoint in indexer(code_range, b2_ranges):
                glyphbytes = bitmapfile.read(bytesize)
                glyphs.append(Glyph.from_bytes(
                    glyphbytes, width=width, codepoint=codepoint
                ))
    return glyphs


##############################################################################
# properties

def hbf_int(numstr):
    """Convert HBF int representation to int."""
    # HBF has c-style octals 0777
    if numstr.startswith('0') and numstr[1:2].isdigit():
        return int(numstr[1:], 8)
    return int(numstr, 0)


def _split_hbf_ints(value, sep=None):
    """Split a string and convert elements to int."""
    return tuple(hbf_int(_p) for _p in value.split(sep))


def _parse_properties(hbf_props, x_props):
    """Parse metrics and metadata."""
    # parse meaningful metadata
    properties, unparsed = _parse_hbf_properties(hbf_props)
    # the FONT field *may* conform to xlfd but doesn't have to. don't parse it
    xlfd_props = _parse_xlfd_properties(x_props, xlfd_name='', to_int=hbf_int)
    for key, value in unparsed.items():
        logging.info(f'Unrecognised HBF property {key}={value}')
        # preserve as property
        properties[key] = value
    for key, value in xlfd_props.items():
        if key in properties and properties[key] != value:
            logging.warning(
                'Inconsistency between HBF and XLFD properties: '
                '%s=%s (from XLFD) but %s=%s (from HBF). Taking HBF property.',
                key, value, key, properties[key]
            )
        else:
            properties[key] = value
    # TODO: convert code scheme name to encoding name
    # prefer hbf code scheme to charset values from xlfd
    logging.info('yaff properties:')
    for name, value in properties.items():
        logging.info('    %s: %s', name, value)
    return properties

def _parse_hbf_properties(hbf_props):
    """Parse HBF properties."""
    size, xdpi, ydpi = _split_hbf_ints(hbf_props.pop('SIZE'))
    properties = {
        'source-format': 'HBF v{}'.format(hbf_props.pop('HBF_START_FONT')),
        'point-size': size,
        'dpi': (xdpi, ydpi),
    }
    width, height, offset_x, offset_y = _split_hbf_ints(
        hbf_props.pop('HBF_BITMAP_BOUNDING_BOX')
    )
    # https://www.ibiblio.org/pub/packages/ccic/software/info/HBF-1.1/BoundingBoxes.html
    # fontboundingbox is equal or larger than bitmap bounding box
    # may be used to specify inter-glyph and inter-line spacing
    # the documented examples show the effect of different bounding box heights
    # but the impact of the fondboundingbox offset is unclear to me
    full_width, full_height, full_offset_x, full_offset_y = _split_hbf_ints(
        hbf_props.pop('FONTBOUNDINGBOX')
    )
    properties.update({
        'line-height': full_height,
        # full_width :==: advance-width == left-bearing + width + right-bearing
        'left-bearing': offset_x,
        'right-bearing': full_width - width - offset_x,
        # I think the fontboundingbox offsets actually go unused
        'shift_up': offset_y,
    })
    # known but we don't use it
    properties['hbf.font'] = hbf_props.pop('FONT', None)
    # keep unparsed hbf props
    return properties, hbf_props
