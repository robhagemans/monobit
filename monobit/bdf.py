"""
monobit.hexdraw - read and write .bdf files

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging
import binascii

from .base import Font, ensure_stream


@Font.loads('bdf')
def load(infile):
    """Load font from a .bdf file."""
    with ensure_stream(infile, 'r') as instream:
        nchars, comments, bdf_props, x_props = _read_bdf_global(instream)
        glyphs, glyph_props = _read_bdf_characters(instream)
        # check number of characters, but don't break if no match
        if nchars != len(glyphs):
            logging.warning('Possibly corrupted BDF file: number of characters found does not match CHARS declaration.')
        properties = _parse_properties(glyphs, glyph_props, bdf_props, x_props, instream.name)
        return Font(glyphs, comments, properties)


def _read_dict(instream, until=None):
    """Read key-value pairs."""
    result = {}
    for line in instream:
        if not line:
            continue
        if ' ' not in line:
            break
        keyword, values = line[:-1].split(' ', 1)
        result[keyword] = values.strip()
        if keyword == until:
            break
    return result

def _read_bdf_characters(instream):
    """Read character section."""
    # state
    current_char = None
    bitmap = False
    # output
    glyphs = {}
    glyph_meta = {}
    for line in instream:
        line = line[:-1]
        if not line:
            continue
        if line.startswith('ENDFONT'):
            break
        elif not line.startswith('STARTCHAR'):
            raise ValueError('Expected STARTCHAR')
        keyword, values = line.split(' ', 1)
        meta = _read_dict(instream, until='BITMAP')
        meta[keyword] = values
        width, height, _, _ = meta['BBX'].split(' ')
        width, height = int(width), int(height)
        # fix for ami2bdf fonts
        #if width > 65534:
        #    width -= 65534
        # convert from hex-string to list of bools
        data = [instream.readline()[:-1] for _ in range(height)]
        bytewidth = len(data[0]) // 2
        fmt = '{:0%db}' % (bytewidth*8,)
        glyphstrs = [fmt.format(int(_row, 16)).ljust(width, '\0')[:width] for _row in data]
        glyph = [[_c == '1' for _c in _row] for _row in glyphstrs]
        # store in dict
        # ENCODING must be single integer or -1 followed by integer
        encvalue = int(meta['ENCODING'].split(' ')[-1])
        # no encoding number found
        if encvalue == -1 or encvalue in glyphs:
            encvalue = meta['STARTCHAR']
        glyphs[encvalue] = glyph
        glyph_meta[encvalue] = meta
        if not instream.readline().startswith('ENDCHAR'):
            raise('Expected ENDCHAR')
    return glyphs, glyph_meta

def _read_bdf_global(instream):
    """Read global section of BDF file."""
    # read global section
    bdf_props = {}
    x_props = {}
    comments = []
    parsing_x = False
    nchars = -1
    for line in instream:
        line = line.strip('\r\n')
        if not line:
            continue
        elif line.startswith('COMMENT'):
            comments.append(line[8:])
        elif line.startswith('STARTPROPERTIES'):
            parsing_x = True
        elif line.startswith('ENDPROPERTIES'):
            parsing_x = False
        else:
            keyword, values = line.split(' ', 1)
            values = values.strip()
            if keyword == 'CHARS':
                # value equals number of chars
                # this signals the end of the global section
                nchars = int(values)
                return nchars, comments, bdf_props, x_props
            elif parsing_x:
                x_props[keyword] = values
            else:
                # record all keywords in the same metadata table
                bdf_props[keyword] = values
    raise ValueError('No character information found in BDF file.')

def _parse_properties(glyphs, glyph_props, bdf_props, x_props, filename):
    """Parse metrics and metadata."""
    logging.info('bdf properties:')
    for name, value in bdf_props.items():
        logging.info('    %s: %s', name, value)
    logging.info('x properties:')
    for name, value in x_props.items():
        logging.info('    %s: %s', name, value)
    # converter-supplied metadata
    properties = {
        'source-name': os.path.basename(filename),
    }
    # parse meaningful metadata
    glyphs, bdf_properties = _parse_bdf_properties(glyphs, glyph_props, bdf_props)
    properties.update(bdf_properties)
    properties.update(_parse_xlfd_properties(x_props))
    if 'slant' in properties and properties['slant']:
        properties['slant'] = {
            'R': 'roman', 'I': 'italic', 'O': 'oblique', 'RO': 'reverse-oblique',
            'RI': 'reverse-italic', 'OT': 'other'
        }[properties['slant']]
    # encoding
    try:
        registry = properties.pop('charset-registry')
        encoding = properties.pop('charset-encoding')
    except KeyError:
        pass
    else:
        properties['encoding'] = registry + '-' + encoding
    #'spacing': {
    #    'P': 'proportional', 'M': 'monospace', 'C': 'cell',
    #}[xlfd[11]] if xlfd[11] else '',
    if 'DEFAULT_CHAR' in x_props:
        defaultchar = x_props['DEFAULT_CHAR']
        # if the number doesn't occur, no default is set.
        if int(defaultchar) in glyphs:
            properties['default-char'] = hex(int(defaultchar))
    return properties


def _parse_bdf_properties(glyphs, glyph_props, bdf_props):
    """Parse BDF global and per-glyph geometry."""
    # FIXME: parse per-glyph geometry ... we need BBX and the offsets in swidth (I think)
    # modify glyphs if necessary to get to one global offset value
    properties = {
        'source-format': 'BDF ' + bdf_props['STARTFONT'],
    }
    # we ignore SIZE and FONTBOUNDINGBOX as they are overridden by per-glyph metrics
    properties.update(_parse_xlfd_string(bdf_props['FONT']))
    #
    # DWIDTH dwx0 dwy0
    # DWIDTH specifies the widths in x and y, dwx0 and dwy0, in device pixels.
    # Like SWIDTH , this width information is a vector indicating the position of
    # the next glyph’s origin relative to the origin of this glyph. DWIDTH is manda-
    # tory for all writing mode 0 fonts.
    #
    # BBX BBw BBh BBxoff0x BByoff0y
    # BBX is followed by BBw, the width of the black pixels in x, and BBh, the
    # height in y. These are followed by the x and y displacement, BBxoff0 and
    # BByoff0, of the lower left corner of the bitmap from origin 0. All values are
    # are an integer number of pixels.
    # If the font specifies metrics for writing direction 1, VVECTOR specifies the
    # offset from origin 0 to origin 1. For example, for writing direction 1, the
    # offset from origin 1 to the lower left corner of the bitmap would be:
    # BBxoff1x,y = BBxoff0x,y – VVECTOR
    offsets_x = []
    offsets_y = []
    overshoots = []
    heights = []
    for ordinal, glyph in glyphs.items():
        props = glyph_props[ordinal]
        bbx_width, bbx_height, offset_x, offset_y = (int(_p) for _p in props['BBX'].split(' '))
        dwidth_x, dwidth_y = (int(_p) for _p in props['DWIDTH'].split(' '))
        offsets_x.append(offset_x)
        offsets_y.append(offset_y)
        overshoots.append((offset_x + bbx_width) - dwidth_x)
        heights.append(bbx_height + offset_y)
    leftmost = min(offsets_x)
    rightmost = max(overshoots)
    bottommost = min(offsets_y)
    topmost = max(heights)
    properties['bearing-before'] = -leftmost
    properties['bearing-after'] = rightmost
    properties['baseline'] = -bottommost
    for ordinal, glyph in glyphs.items():
        props = glyph_props[ordinal]
        bbx_width, bbx_height, offset_x, offset_y = (int(_p) for _p in props['BBX'].split(' '))
        dwidth_x, dwidth_y = (int(_p) for _p in props['DWIDTH'].split(' '))
        overshoot = (offset_x + bbx_width) - dwidth_x
        padding_right = rightmost - overshoot
        padding_left = offset_x - leftmost
        padding_bottom = offset_y - bottommost
        padding_top = topmost - bbx_height - offset_y
        glyph = [
            [False] * padding_left
            + _row[:bbx_width]
            + [False] * padding_right
            for _row in glyph[:bbx_height]
        ]
        matrix_width = padding_left + bbx_width + padding_right
        glyph = (
            [[False] * matrix_width for _ in range(padding_top)]
            + glyph
            + [[False] * matrix_width for _ in range(padding_bottom)]
        )
        glyphs[ordinal] = glyph
    return glyphs, properties

def _parse_xlfd_string(xlfd_str):
    """Parse X logical font description font name string."""
    mapping = {
        'foundry': 1,
        'family': 2,
        'weight': 3,
        'slant': 4,
        'width': 5,
        'style': 6,
        # pixel-size
        # point-size
        # resolution-x
        # resolution-y
        # spacing
        # average-width
        'charset-registry': 13,
        'charset-encoding': 14,
    }
    xlfd = xlfd_str.split('-')
    properties = {}
    if len(xlfd) >= 15:
        for key, index in mapping.items():
            if xlfd[index]:
                properties[key] = xlfd[index]
    else:
        logging.warning('Could not parse X font name string `%s`', xlfd_str)
    return properties


def _parse_xlfd_properties(x_props):
    """Parse X metadata."""
    mapping = {
        'ascent': 'FONT_ASCENT',
        'descent': 'FONT_DESCENT',
        'x-height': 'X_HEIGHT',
        'cap-height': 'CAP_HEIGHT',
        'copyright': 'COPYRIGHT',
        'notice': 'NOTICE',
        'foundry': 'FOUNDRY',
        'family': 'FAMILY_NAME',
        'weight': 'WEIGHT_NAME',
        'slant': 'SLANT',
        'width': 'SETWIDTH_NAME',
        'style': 'STYLE_NAME',
        # SPACING can be deducted from bitmaps
        #'spacing': 'SPACING',
        # we ignore AVERAGE_WIDTH
        'charset-registry': 'CHARSET_REGISTRY',
        'charset-encoding': 'CHARSET_ENCODING',
    }
    properties = {}
    for key, xkey in mapping.items():
        try:
            value = x_props[xkey].strip('"')
        except KeyError:
            pass
        else:
            if value:
                properties[key] = value
    return properties


# from:  Glyph Bitmap Distribution Format (BDF) Specification 2.2 (22 Mar 93)
#
# global font information
#
# COMMENT string
# One or more lines beginning with the word COMMENT . These lines can be
# ignored by any program reading the file.
#
# CONTENTVERSION integer
# (Optional) The value of CONTENTVERSION is an integer which can be
# assigned by an installer program to keep track of the version of the included
# data. The value is intended to be valid only in a single environment, under the
# control of a single installer. The value of CONTENTVERSION should only
# reflect upgrades to the quality of the bitmap images, not to the glyph comple-
# ment or encoding.
#
# FONT string
# FONT is followed by the font name, which should exactly match the Post-
# Script TM language FontName in the corresponding outline font program.
# SIZE PointSize Xres Yres
# SIZE is followed by the point size of the glyphs and the x and y resolutions of
# the device for which the font is intended.
#
# FONTBOUNDINGBOX FBBx FBBy Xoff Yoff
# FONTBOUNDINGBOX is followed by the width in x and the height in y, and
# the x and y displacement of the lower left corner from origin 0 (for horizontal
# writing direction); all in integer pixel values. (See the examples in section 4.)
#
# METRICSSET integer
# (Optional) The integer value of METRICSSET may be 0, 1, or 2, which corre-
# spond to writing direction 0 only, 1 only, or both (respectively). If not
# present, METRICSSET 0 is implied. If METRICSSET is 1, DWIDTH and
# SWIDTH keywords are optional.
#
# SWIDTH
# DWIDTH
# SWIDTH1
# DWIDTH1
# VVECTOR
# These metrics keywords may be present at the global level to define a single
# value for the whole font. The values may be defined at this level, yet over-
# ridden for individual glyphs by including the same keyword and a value in
# the information for an individual glyph. For a composite font containing a
# large number of ideographic glyphs with identical metrics, defining those
# values at the global level can provide a significant savings in the size of the
# resulting file.
#
# Note
# Version 2.1 of this document only allowed the metrics keywords SWIDTH and
# DWIDTH , and only at the glyph level. If compatibility with 2.1 is an issue,
# metrics should not be specified as global values.
# These keywords all have the same meanings as specified in section 3.2, Indi-
# vidual Glyph Information.


# per-glyph info:
# STARTCHAR string
# The word STARTCHAR followed by a string containing the name for the
# glyph. In base fonts, this should correspond to the name in the PostScript
# language outline font’s encoding vector. In a Composite font (Type 0), the
# value may be a numeric offset or glyph ID.
# Note: In versions of this document prior to 2.2, this value was limited to a string of
# 14 characters.
#
# ENCODING integer (integer)
# ENCODING is followed by a positive integer representing the Adobe Stan-
# dard Encoding value. If the character is not in the Adobe Standard Encoding,
# ENCODING is followed by –1 and optionally by another integer specifying
# the glyph index for the non-standard encoding.
#
# SWIDTH swx0 swy0
# SWIDTH is followed by swx0 and swy0, the scalable width of the glyph in x
# and y for writing mode 0. The scalable widths are of type Number and are in
# units of 1/1000th of the size of the glyph and correspond to the widths found
# in AFM files (for outline fonts). If the size of the glyph is p points, the width
# information must be scaled by p /1000 to get the width of the glyph in
# printer’s points. This width information should be regarded as a vector indi-
# cating the position of the next glyph’s origin relative to the origin of this
# glyph. SWIDTH is mandatory for all writing mode 0 fonts.
# To convert the scalable width to the width in device pixels, multiply SWIDTH
# times p /1000 times r /72, where r is the device resolution in pixels per inch.
# The result is a real number giving the ideal width in device pixels. The actual
# device width must be an integral number of device pixels and is given by the
#
# SWIDTH1 swx1 swy1
# SWIDTH 1 is followed by the values for swx1 and swy1, the scalable width of
# the glyph in x and y, for writing mode 1 (vertical direction). The values are of
# type Number , and represent the widths in glyph space coordinates.
#
# DWIDTH1 dwx1 dwy1
# DWIDTH1 specifies the integer pixel width of the glyph in x and y. Like
# SWIDTH 1, this width information is a vector indicating the position of the
# next glyph’s origin relative to the origin of this glyph. DWIDTH1 is manda-
# tory for all writing mode 1 fonts.
#
# Note
# If METRICSSET is 1 or 2, both SWIDTH1 and DWIDTH1 must be present; if
# METRICSSET is 0, both should be absent.
#
# VVECTOR xoff yoff
# VVECTOR (optional) specifies the components of a vector from origin 0 (the
# origin for writing direction 0) to origin 1 (the origin for writing direction 1).
# If the value of METRICSSET is 1 or 2, VVECTOR must be specified either at
# the global level, or for each individual glyph. If specified at the global level,
# the VVECTOR is the same for all glyphs, though the inclusion of this
# keyword in an individual glyph has the effect of overriding the bal value for
# that specific glyph.
