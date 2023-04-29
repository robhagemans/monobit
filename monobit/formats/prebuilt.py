"""
monobit.formats.prebuilt - Adobe BE/LE Prebuilt Format

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import cycle

from ..struct import bitfield, little_endian as le, big_endian as be
from ..properties import Props
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..magic import FileFormatError


@loaders.register(
    name='prebuilt',
    patterns=('*.bepf', '*.lepf'),
)
def load_pf(instream):
    """Load font from bepf/lepf file."""
    pf_props, pf_glyphs = _read_pf(instream)
    logging.info(pf_props)
    fonts = _convert_from_pf(pf_props, pf_glyphs)
    return fonts


################################################################################
# Adobe prebuilt format
# https://github.com/johnsonjh/NeXTDPS/blob/master/fonts-21/bin/prebuiltformat.h
# https://github.com/johnsonjh/NeXTDPS/blob/master/fonts-21/bin/prebuild.c

# we have a choice of big and little endian files, need different base classes
_BASE = {'l': le, 'b': be}


_PREBUILTFILEVERSION = 3

# typedef struct _t_PrebuiltFile {
_PREBUILT_FILE = {
    _endian: _BASE[_endian].Struct(
        # /* equal to 0 iff little-endian, otherwise big-endian */
        # byteOrder='short',
        # /* file version number (equal to PREBUILTFILEVERSION) */
        version='short',
        # /* font's fid */
        identifier='long',
        # /* file position of name of font (null terminated) */
        fontName='long',
        # /* file position of name of character set (null terminated)
        # (equal to either "ISOLatin1CharacterSet" or the name of the font) */
        characterSetName='long',
        # /* number of character in character set */
        numberChar='short',
        # /* number of distinct matrices imaged */
        numberMatrix='short',
        # /* file position of the first element of an
        # array of numberChar PrebuiltWidth's */
        widths='long',
        # /* file position of first of numberChar character name's
        # (sorted lexicographically, each null terminated) */
        names='long',
        # /* total number of bytes of character name's (including nulls) */
        lengthNames='long',
        # /* file position of the first element of an
        # array of numberMatrix PrebuiltMatrix 's */
        matrices='long',
        # /* file position of the first element of an
        # array of numberChar*numberMatrix PrebuiltMask's */
        masks='long',
        # /* equal to 0 iff vertical data NOT included,
        # otherwise file position of first element of an
        # array of numberChar PrebuiltVertWidths's */
        vertWidths='long',
        # /* equal to 0 iff vertical data NOT included,
        # otherwise file position of first element of an
        # array of numberChar*numberMatrix PrebuiltVertMetrics's */
        vertMetrics='long',
        # /* total number of bytes of mask data.  Mask
        # data are positioned in the file in the
        # same order as their corresponding PrebuiltMask. */
        lengthMaskData='long',
    )
    for _endian in ('l', 'b')
}


# typedef struct _t_PrebuiltMatrix {
_PREBUILT_MATRIX = {
    _endian: _BASE[_endian].Struct(
        # /* x' = a*x + c*y + tx (fixed)*/
        a='int32',
        # /* y' = b*x + d*y + ty (fixed)*/
        b='int32',
        # /* (fixed)*/
        c='int32',
        # /* (fixed)*/
        d='int32',
        # /* (fixed)*/
        tx='int32',
        # /* (fixed)*/
        ty='int32',
        # /* depth of mask pixel */
        depth='int32',
    )
    for _endian in ('l', 'b')
}

# typedef struct _t_PrebuiltWidth {
_PREBUILT_WIDTH = {
    _endian: _BASE[_endian].Struct(
        # /* x component of horizontal vector (fixed) */
        hx='int32',
        # /* y component of horizontal vector (fixed) */
        hy='int32',
    )
    for _endian in ('l', 'b')
}


_HCOORD = {
    _endian: _BASE[_endian].Struct(
        hx='int8',
        hy='int8',
    )
    for _endian in ('l', 'b')
}


# typedef struct _t_PrebuiltMask {
_PREBUILT_MASK = {
    _endian: _BASE[_endian].Struct(
        # /* width of mask in pixels */
        width='uint8',
        # /* height of mask in pixels */
        height='uint8',
        # /* horizontal offsets */
        maskOffset=_HCOORD[_endian],
        # /* horizontal widths */
        maskWidth=_HCOORD[_endian],
        # /* pad to make multiple of 4 bytes; */
        pad='short',
        # /* file position of mask data ((width * depth + 7) / 8 * height bytes) */
        maskData='long',
    )
    for _endian in ('l', 'b')
}


# typedef struct _t_PrebuiltVertWidths {
_PREBUILT_VERT_WIDTHS = {
    _endian: _BASE[_endian].Struct(
        # /* x component of vertical vector; (fixed) */
        vx='int32',
        # /* y component of vertical vector; (fixed) */
        vy='int32',
    )
    for _endian in ('l', 'b')
}


_VCOORD = {
    _endian: _BASE[_endian].Struct(
        vx='int8',
        vy='int8',
    )
    for _endian in ('l', 'b')
}

# typedef struct _t_PrebuiltVertMetrics {
_PREBUILT_VERT_METRICS = {
    _endian: _BASE[_endian].Struct(
        # /* vertical offsets */
        offset=_VCOORD[_endian],
        # /* vertical widths */
        width=_VCOORD[_endian]
    )
    for _endian in ('l', 'b')
}



# assumed max string length
MAX_STRING = 256

def _read_pf(instream):
    """Read an Adobe prebuilt file."""
    pf_props = Props()
    pf_props.byteOrder = instream.read(2)
    endian = 'l' if pf_props.byteOrder == b'\0\0' else 'b'
    header = _PREBUILT_FILE[endian].read_from(instream)
    pf_props |= Props(**vars(header))
    instream.seek(header.fontName)
    pf_props.fontName, _, _ = instream.read(MAX_STRING).partition(b'\0')
    instream.seek(header.characterSetName)
    pf_props.characterSetName, _, _ = instream.read(MAX_STRING).partition(b'\0')
    instream.seek(header.names)
    pf_props.names = instream.read(header.lengthNames-1).split(b'\0')
    instream.seek(header.widths)
    pf_props.widths = (_PREBUILT_WIDTH[endian] * header.numberChar).read_from(instream)
    instream.seek(header.matrices)
    pf_props.matrices = (_PREBUILT_MATRIX[endian] * header.numberMatrix).read_from(instream)
    if header.vertWidths:
        instream.seek(header.vertWidths)
        pf_props.vert_idths = (_PREBUILT_VERT_WIDTHS[endian] * header.numberChar).read_from(instream)
    if header.vertMetrics:
        instream.seek(header.vertMetrics)
        pf_props.vertMetrics = ((_PREBUILT_VERT_METRICS[endian] * header.numberChar) * header.numberMatrix).read_from(instream)
    instream.seek(header.masks)
    # glyph data in pf_props.masks
    pf_masks = ((_PREBUILT_MASK[endian] * header.numberChar) * header.numberMatrix).read_from(instream)
    pf_masks = tuple(
        tuple(Props(**vars(_mask)) for _mask in _strike)
        for _strike in pf_masks
    )
    for strike in pf_masks:
        for mask in strike:
            instream.seek(mask.maskData)
            # FIXME need to refer to corresponding matrix
            depth = 1
            size = ((mask.width * depth + 7) // 8) * mask.height
            mask.maskData = instream.read(size)
    return pf_props, pf_masks


def _convert_from_pf(pf_props, pf_masks):
    """Convert Adobe prebuilt format data to monobit."""
    strikes = tuple(
        tuple(
            Glyph.from_bytes(
                _m.maskData, width=_m.width, height=_m.height,
                left_bearing=_m.maskOffset.hx, shift_up=_m.maskOffset.hy-_m.height,
                # we don't support hy
                right_bearing=_m.maskWidth.hx+_m.maskOffset.hx-_m.width,
                tag=_name.decode('latin-1'),
            )
            for _m, _name in zip(_strike, pf_props.names)
        )
        for _strike in pf_masks
    )
    fonts = tuple(
        Font(
            _glyphs, font_id=pf_props.identifier,
            family=pf_props.fontName.decode('latin-1')
        )
        for _glyphs in strikes
    )
    return fonts
