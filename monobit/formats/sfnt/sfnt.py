"""
monobit.formats.sfnt - TrueType/OpenType and related formats

(c) 2022--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
import json
import math
import re
from unicodedata import bidirectional

from . import fonttools
from .fonttools import check_fonttools

from ...properties import Props
from ...font import Font
from ...glyph import Glyph
from ...raster import Raster
from ...labels import Tag, Char, Codepoint
from ...storage import loaders, savers
from ...magic import FileFormatError
from ..windows import WEIGHT_MAP, CHARSET_MAP


# errors that invalidate only one strike or resource, not the whole file

class ResourceFormatError(FileFormatError):
    """Unsupported parameters in resource."""

class StrikeFormatError(ResourceFormatError):
    """Unsupported parameters in bitmap strike."""


# resource header
SFNT_MAGIC = b'\0\1\0\0'


if fonttools.loaded:
    @loaders.register(
        name='sfnt',
        magic=(
            SFNT_MAGIC,
            # alternative headers which also occur:
            # TrueType
            b'true',
            # OpenType
            b'OTTO',
            # WOFF
            b'wOFF',
        ),
        patterns=('*.otb', '*.ttf', '*.otf', '*.woff', '*.tte',),
    )
    # pylint: disable=function-redefined
    def load_sfnt(
            infile,
            hmtx:bool=False, vmtx:bool=False,
            hhea:bool=False, vhea:bool=False,
            os_2:bool=True, post:bool=True,
        ):
        """
        Load an SFNT resource and convert to Font.

        hmtx: override horizontal bitmap metrics with `hmtx` table (default: False)
        vmtx: override vertical bitmap metrics with `vmtx` table (default: False)
        hhea: include horizontal line metrics from `hhea` table (default: False)
        vhea: include vertical line metrics from `vhea` table (default: False)
        os_2: include metrics from `OS/2` table (default: True)
        post: include metrics from `post` table (default: True)
        """
        tags = _get_tags(hmtx, vmtx, hhea, vhea, os_2, post)
        sfnt = _read_sfnt(infile, tags)
        logging.debug(str(sfnt))
        fonts = _convert_sfnt(sfnt)
        return fonts


    @loaders.register(
        name='ttcf',
        magic=(
            # TrueType
            b'ttcf',
        ),
        patterns=('*.ttc', '*.otc'),
    )
    def load_collection(
            infile,
            hmtx:bool=False, vmtx:bool=False,
            hhea:bool=False, vhea:bool=False,
            os_2:bool=True, post:bool=True,
        ):
        """
        Load a TrueType/OpenType Collection file.

        hmtx: override horizontal bitmap metrics with `hmtx` table (default: False)
        vmtx: override vertical bitmap metrics with `vmtx` table (default: False)
        hhea: include horizontal line metrics from `hhea` table (default: False)
        vhea: include vertical line metrics from `vhea` table (default: False)
        os_2: include metrics from `OS/2` table (default: True)
        post: include metrics from `post` table (default: True)
        """
        tags = _get_tags(hmtx, vmtx, hhea, vhea, os_2, post)
        sfnts = _read_collection(infile, tags)
        fonts = []
        for _sfnt in sfnts:
            fonts.extend(_convert_sfnt(_sfnt))
        return fonts

else:
    # ensure names are importable; sfnt used by mac, win modules
    load_sfnt = check_fonttools
    load_collection = check_fonttools


###############################################################################
# common encoding tables

# shared with mac

# based on:
# [1] Apple Technotes (As of 2002)/te/te_02.html
# [2] https://developer.apple.com/library/archive/documentation/mac/Text/Text-367.html#HEADING367-0
MAC_ENCODING = {
    0: 'mac-roman',
    1: 'mac-japanese',
    2: 'mac-trad-chinese',
    3: 'mac-korean',
    4: 'mac-arabic',
    5: 'mac-hebrew',
    6: 'mac-greek',
    7: 'mac-cyrillic', # [1] russian
    # 8: [2] right-to-left symbols
    9: 'mac-devanagari',
    10: 'mac-gurmukhi',
    11: 'mac-gujarati',
    12: 'mac-oriya',
    13: 'mac-bengali',
    14: 'mac-tamil',
    15: 'mac-telugu',
    16: 'mac-kannada',
    17: 'mac-malayalam',
    18: 'mac-sinhalese',
    19: 'mac-burmese',
    20: 'mac-khmer',
    21: 'mac-thai',
    22: 'mac-laotian',
    23: 'mac-georgian',
    24: 'mac-armenian',
    25: 'mac-simp-chinese', # [1] maldivian
    26: 'mac-tibetan',
    27: 'mac-mongolian',
    28: 'mac-ethiopic', # [2] == geez
    29: 'mac-centraleurope', # [1] non-cyrillic slavic
    30: 'mac-vietnamese',
    31: 'mac-sindhi', # [2] == ext-arabic
    #32: [1] [2] 'uninterpreted symbols'
}

WIN_ENCODING = {
    # Symbol, but apparently not windows-symbol but any undefined encoding
    0: '',
    1: 'utf-16le', # unicode bmp
    2: 'ms932', # shift-jis
    3: 'ms936', # PRC
    4: 'ms950', # Big-5
    5: 'ms949', # Wansung
    6: 'ms1361', # Johab
    10: 'utf-16le', # Unicode full repertoire
}

ISO_ENCODING = {
    0: 'ascii',
    # unicode
    1: 'iso-10646',
    # latin-1
    2: 'iso-8859-1',
}

PLATFORM_ENCODING = {
    # macintosh platform
    1: MAC_ENCODING,
    # ISO platform
    2: ISO_ENCODING,
    # Windows platform
    3: WIN_ENCODING,
    # legacy windows charset value
    4: CHARSET_MAP,
}

###############################################################################
# sfnt resource reader

# tags we will decompile and process
_TAGS = (
    # check `maxp` first to catch any assertion errors on decompile
    'maxp',
    # core bitmap tables
    'head', 'bhed',
    'EBLC', 'bloc',
    'EBDT', 'bdat',
    'EBSC',
    # sbix: currently just warn we don't parse it
    'sbix',
    # metrics
    'hmtx', 'hhea',
    'vmtx', 'vhea',
    'OS/2',
    # underline metrics and glyph name tags
    'post',
    # metadata
    'name',
    # kerning information
    'kern',
    'GPOS',
    # encoding
    'cmap',
)

def _get_tags(hmtx, vmtx, hhea, vhea, os_2, post):
    """Get list of tables to extract."""
    tags = list(_TAGS)
    if not hmtx:
        tags.remove('hmtx')
    if not vmtx:
        tags.remove('vmtx')
    if not hhea:
        tags.remove('hhea')
    if not vhea:
        tags.remove('vhea')
    if not os_2:
        tags.remove('OS/2')
    if not post:
        tags.remove('post')
    return tags


def _read_sfnt(instream, tags):
    """Read an SFNT resource into data structure."""
    # let fonttools parse the SFNT
    check_fonttools()
    try:
        ttf = fonttools.TTFont(instream)
    except (fonttools.TTLibError, AssertionError) as e:
        raise FileFormatError(f'Could not read sfnt file: {e}')
    return _sfnt_props(ttf, tags)

def _read_collection(instream, tags):
    """Read a collection into data structures."""
    # let fonttools parse the SFNT
    check_fonttools()
    try:
        ttcf = fonttools.TTCollection(instream)
    except (fonttools.TTLibError, AssertionError) as e:
        raise FileFormatError(f'Could not read collection file: {e}')
    ttcf_data = []
    for ttf in ttcf:
        try:
            ttcf_data.append(_sfnt_props(ttf, tags))
        except ResourceFormatError as e:
            logging.debug(e)
    return ttcf_data


def _sfnt_props(ttf, tags):
    """Decompile tables and convert from fontTools objects to data structure."""
    tables = {}
    for tag in _TAGS:
        if tag not in tags:
            tables[tag] = None
            continue
        try:
            # __getitem__ forces a decompilation of the table
            tables[tag] = ttf.get(tag, None)
        except (fonttools.TTLibError, AssertionError) as e:
            if not str(e):
                e = f'{type(e).__name__} in fontTools library.'
            logging.debug('Could not read `%s` table in sfnt: %s', tag, e)
    return Props(**_to_props(tables))


def _to_props(obj):
    """Recursively convert fontTools objects to namespaces."""
    # avoid infinite recursion
    if isinstance(obj, fonttools.TTFont):
        return str(obj)
    if obj is None:
        return obj
    if isinstance(obj, dict):
        return {
            _k: _to_props(_v)
            for _k, _v in obj.items()
        }
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return obj
    if isinstance(obj, (list, tuple)):
        return tuple(_to_props(_v) for _v in obj)
    try:
        obj.ensureDecompiled()
    except AttributeError as e:
        pass
    try:
        objdict = {
            _k: _to_props(_v)
            for _k, _v in vars(obj).items() if _k != 'ttFont'
        }
        return Props(_type=type(obj).__name__, **objdict)
    except TypeError:
        pass
    return str(obj)


###############################################################################
# sfnt resource converter

def _convert_sfnt(sfnt):
    """Convert sfnt data structure to Font."""
    if sfnt.bdat:
        source_format = 'sfnt (bdat)'
    else:
        source_format = 'sfnt (EBDT)'
    # synonymous tables
    sfnt.bdat = sfnt.bdat or sfnt.EBDT
    sfnt.bloc = sfnt.bloc or sfnt.EBLC
    sfnt.head = sfnt.bhed or sfnt.head
    if sfnt.sbix:
        logging.warning(
            'Bitmap strikes in `sbix` format not supported.'
        )
    if not sfnt.bdat or not sfnt.bloc:
        raise ResourceFormatError(
            'No `EBDT` or `bdat` bitmap strikes found in sfnt resource.'
        )
    fonts = []
    unitable = _get_unicode_table(sfnt)
    enctable, encoding = _get_encoding_table(sfnt)
    for i_strike in range(sfnt.bloc.numSizes):
        try:
            props = _convert_props(sfnt, i_strike)
            glyphs = _convert_glyphs(
                sfnt, i_strike, props._hfupp, props._vfupp, unitable, enctable
            )
            del props._hfupp
            del props._vfupp
            # disabled - if we remove tags we break kerning (can label() adjust kerning too?)
            # # remove temporary names created by fontTools
            # # if there's no post table or it is empty
            # if not sfnt.post or sfnt.post.formatType == 3.0:
            #     glyphs = (_g.modify(tag=None) if _g.char else _g for _g in glyphs)
            fonts.append(Font(
                glyphs, source_format=source_format, encoding=encoding or None,
                **vars(props)
            ))
        except StrikeFormatError:
            pass
    return fonts


def _convert_props(sfnt, i_strike):
    """Build font properties from sfnt data."""
    # determine the size of a pixel in FUnits
    bmst = sfnt.bloc.strikes[i_strike].bitmapSizeTable
    vert_fu_p_pix = sfnt.head.unitsPerEm / bmst.ppemY
    hori_fu_p_pix = sfnt.head.unitsPerEm / bmst.ppemX
    # we also had pixels per em in the EBLC table, so now we know units per pixel
    props = _convert_bloc_props(sfnt.bloc, i_strike)
    props |= _convert_head_props(sfnt.head)
    props |= _convert_name_props(sfnt.name)
    props |= _convert_os_2_props(getattr(sfnt, 'OS/2'), vert_fu_p_pix, hori_fu_p_pix)
    props |= _convert_hhea_props(sfnt.hhea, vert_fu_p_pix)
    props |= _convert_vhea_props(sfnt.vhea, hori_fu_p_pix)
    props |= _convert_post_props(sfnt.post, vert_fu_p_pix)
    props._hfupp = hori_fu_p_pix
    props._vfupp = vert_fu_p_pix
    return props


def _convert_glyphs(sfnt, i_strike, hori_fu_p_pix, vert_fu_p_pix, unitable, enctable):
    """Build glyphs and glyph properties from sfnt data."""
    glyphs = []
    strike = sfnt.bdat.strikeData[i_strike]
    blocstrike = sfnt.bloc.strikes[i_strike]
    for subtable in blocstrike.indexSubTables:
        # some formats are byte aligned, others bit-aligned
        if subtable.imageFormat in (1, 6):
            align = 'left'
        elif subtable.imageFormat in (2, 5, 7):
            align = 'bit'
        else:
            # format 8, 9: component bitmaps
            # format 3: obsolete, not used
            # format 4: modified-Hufffman compressed, insufficiently documented
            logging.warning(
                'Unsupported image format %d', subtable.imageFormat
            )
            continue
        for name in subtable.names:
            glyph = strike[name]
            try:
                metrics = glyph.metrics
            except AttributeError:
                metrics = subtable.metrics
            width = metrics.width
            height = metrics.height
            if not width or not height:
                glyphbytes = b''
            else:
                try:
                    glyphbytes = glyph.imageData
                except AttributeError:
                    logging.warning(f'No image data for glyph `{name}`')
                    continue
            small_is_vert = blocstrike.bitmapSizeTable.flags == 2
            props = _convert_glyph_metrics(metrics, small_is_vert)
            props.update(_convert_hmtx_metrics(sfnt.hmtx, name, hori_fu_p_pix, width))
            props.update(_convert_vmtx_metrics(sfnt.vmtx, name, vert_fu_p_pix, height))
            raster = Raster.from_bytes(glyphbytes, width=width, align=align)
            raster = raster.crop(bottom=max(0, raster.height-height))
            glyph = Glyph(
                raster,
                tag=name, char=unitable.get(name, ''),
                codepoint=enctable.get(name, b''), **props
            )
            glyphs.append(glyph)
    glyphs = _convert_kern_metrics(glyphs, sfnt.kern, hori_fu_p_pix)
    glyphs = _convert_gpos_metrics(glyphs, sfnt.GPOS, hori_fu_p_pix)
    return glyphs


def _convert_glyph_metrics(metrics, small_is_vert):
    """Convert glyph metrics."""
    if hasattr(metrics, 'horiAdvance'):
        # big metrics
        return dict(
            # hori
            left_bearing=metrics.horiBearingX,
            right_bearing=(
                metrics.horiAdvance - metrics.width - metrics.horiBearingX
            ),
            shift_up=metrics.horiBearingY - metrics.height,
            # vert
            shift_left=metrics.vertBearingX - metrics.width//2,
            top_bearing=metrics.vertBearingY,
            bottom_bearing=(
                metrics.vertAdvance - metrics.height
                - metrics.vertBearingY
            ),
        )
    elif not small_is_vert:
        # small metrics
        return dict(
            left_bearing=metrics.BearingX,
            right_bearing=metrics.Advance - metrics.width - metrics.BearingX,
            shift_up=metrics.BearingY - metrics.height,
        )
    else:
        # small metrics, interpret as vert
        return dict(
            shift_left=metrics.BearingX - metrics.width//2,
            top_bearing=metrics.BearingY,
            bottom_bearing=(
                metrics.Advance - metrics.height - metrics.BearingY
            ),
        )


###############################################################################
# 'cmap' table

# preferred table to use for Unicode: platformID, platEncID
_UNICODE_CHOICES = (
    # Unicode platform, full repertoire
    (0, 4),
    (0, 6),
    # Windows platform, full repertoire
    (3, 10),
    # Unicode platform BMP
    (0, 3),
    # Windows platform BMP
    (3, 1),
    # ISO platform (deprecated), ISO 10646
    (2, 1),
)

def _get_unicode_table(sfnt):
    """Get unicode mapping from sfnt data."""
    # find unicode encoding
    for id_pair in _UNICODE_CHOICES:
        for table in sfnt.cmap.tables:
            if (int(table.platformID), int(table.platEncID)) == id_pair:
                unitable = {
                    _name: chr(int(_ord))
                    for _ord, _name in table.cmap.items()
                }
                break
        else:
            continue
        break
    else:
        unitable = {}
    return unitable

def _get_encoding_table(sfnt):
    """Get non-unicode encoding from sfnt data."""
    # get the largest table for non-unicode mappings
    non_unicode_tables = (
        _t for _t in sfnt.cmap.tables
        if (int(_t.platformID), int(_t.platEncID)) not in _UNICODE_CHOICES
    )
    non_unicode_tables = sorted(
        ((len(_t.cmap), _t) for _t in non_unicode_tables),
        reverse=True
    )
    if not non_unicode_tables:
        return {}, ''
    largest_table = non_unicode_tables[0][1]
    encoding = (
        PLATFORM_ENCODING
        .get(largest_table.platformID, {})
        .get(largest_table.platEncID, '')
    )
    enctable = {
        _name: int(_ord)
        for _ord, _name in largest_table.cmap.items()
    }
    return enctable, encoding


###############################################################################
# 'hmtx' table

def _convert_hmtx_metrics(hmtx, glyph_name, hori_fu_p_pix, width):
    """Convert horizontal metrics from hmtx table."""
    if hmtx:
        hm = hmtx.metrics.get(glyph_name, None)
        if hm:
            advance, left_bearing = hm
            return dict(
                left_bearing=left_bearing // hori_fu_p_pix,
                right_bearing=(advance - left_bearing) // hori_fu_p_pix - width,
            )
    return {}



###############################################################################
# 'vmtx' table

def _convert_vmtx_metrics(vmtx, glyph_name, vert_fu_p_pix, height):
    """Convert vertical metrics from vmtx table."""
    if vmtx:
        vm = vmtx.metrics.get(glyph_name, None)
        if vm:
            advance, top_bearing = vm
            return dict(
                top_bearing=top_bearing // vert_fu_p_pix,
                bottom_bearing=(advance - top_bearing) // vert_fu_p_pix - height,
            )
    return {}


###############################################################################
# 'kern' table

def _convert_kern_metrics(glyphs, kern, hori_fu_p_pix):
    """Convert kerning values form kern table."""
    if kern:
        glyph_props = {}
        for table in kern.kernTables:
            if not hasattr(table, 'coverage') or not hasattr(table, 'kernTable'):
                logging.warning('Kerning subtable format not supported')
                continue
            if table.coverage != 1:
                logging.warning('Vertical or cross-stream kerning not supported')
                continue
            for pair, kern_value in table.kernTable.items():
                left, right = pair
                ktable = glyph_props.get(Tag(left), {})
                ktable[Tag(right)]  = kern_value / hori_fu_p_pix
                glyph_props[Tag(left)] = ktable
        glyphs = tuple(
            _g.modify(right_kerning=glyph_props.get(_g.tags[0], None))
            if _g.tags else _g
            for _g in glyphs
        )
    return glyphs


###############################################################################
# 'GPOS' table

def _convert_gpos_metrics(glyphs, gpos, hori_fu_p_pix):
    """Convert kerning values form GPOS table."""
    logging.debug('parsing gpos')
    if gpos:
        #features = gpos.table.featureList
        llist = gpos.table.LookupList.Lookup
        glyph_props = {}
        for lookup in llist:
            for subtable in lookup.SubTable:
                if subtable._type != 'PairPos':
                    continue
                # per the docs, in logical order
                # i.e first is left for LTR, first is right for RTL
                # presumably to be determined from glyph unicode properties?
                # what happens if one glyph is LTR and the other RTL is unclear
                # the one RTL file I have does things differently,
                # and in line with this comment:
                # https://fontforge-devel.narkive.com/s9C4jFO9/patch-1-2-fix-right-to-left-kerning
                # i.e. the second glyph's Xadvance is adjusted by a negative number
                # is this a hack to compensate for LTR-focussed real-world implementations?
                # do they still mean the logical second (i.e. leftmost) glyph?
                firsts = subtable.Coverage.glyphs
                format1 = subtable.ValueFormat1 & 0xf
                format2 = subtable.ValueFormat2 & 0xf
                # first X_ADVANCE or second X_PLACEMENT
                if format1 not in (0, 4) or format2 not in (0, 1, 4):
                    logging.warning("Vertical and cross kerning not supported.")
                for first, pairset in zip(firsts, subtable.PairSet):
                    for record in pairset.PairValueRecord:
                        second = record.SecondGlyph
                        kern_value = 0
                        direction = 'l'
                        if format1 & 4:
                            kern_value += record.Value1.XAdvance
                        if format2 & 1:
                            kern_value += record.Value2.XPlacement
                        # oddly, this is how RTL kerning is recorded
                        if format2 & 4 and not kern_value:
                            direction = 'r'
                            kern_value = record.Value2.XAdvance
                        ktable = glyph_props.get(Tag(first), {})
                        if kern_value:
                            ktable[Tag(second)] = kern_value / hori_fu_p_pix
                        else:
                            logging.debug(
                                'Dropped zero kerning value %s->%s',
                                first, second
                            )
                        glyph_props[Tag(first)] = ktable
        glyphs = tuple(
            _g.modify(right_kerning=glyph_props.get(_g.tags[0], None))
            if _g.tags and not _is_rtl(_g) else _g
            for _g in glyphs
        )
        # interpret as left-hand kerning for RTL glyphs
        glyphs = tuple(
            _g.modify(left_kerning=glyph_props.get(_g.tags[0], None))
            if _g.tags and _is_rtl(_g) else _g
            for _g in glyphs
        )
    return glyphs

def _is_rtl(glyph):
    """Determine if a glyph is RTL for GPOS kerning."""
    return glyph.char and bidirectional(glyph.char)[:1] in ('R', 'A')


###############################################################################
# 'EBLC' or 'bloc' table

def _convert_bloc_props(bloc, i_strike):
    """Convert font properties from EBLC/bloc table."""
    strike = bloc.strikes[i_strike]
    bmst = strike.bitmapSizeTable
    # validations
    if bmst.bitDepth != 1:
        raise StrikeFormatError(
            'Colour and grayscale not supported.'
        )
    if bmst.flags not in (1, 2):
        logging.warning(
            f'Unsupported metric flag value {bmst.flags}, '
            'using 1 (horizontal) instead.'
        )
        bmst.flags = 1
    props = Props()
    # aspect ratio is the inverse of pixels-per-em ratio
    den = math.gcd(bmst.ppemY, bmst.ppemX)
    props.pixel_aspect = (bmst.ppemY//den, bmst.ppemX//den)
    small_metrics_are_vert = bmst.flags == 2
    # horizontal line metrics
    # according to the EBLC spec the sbit metrics also define the linegap
    # but I don't see it. widthMax looks like a max advance
    props.ascent = bmst.hori.ascender
    # descender should be negative - use abs in case it is incorrectly +
    props.descent = abs(bmst.hori.descender)
    # vertical line metrics
    # we don't keep track of 'ascent' and 'descent' for vert, maybe we should
    # anyway, which way is the 'ascent', left or right?
    return props


###############################################################################
# 'head' or 'bhed' table

# interpretation of head.macStyle flags
STYLE_MAP = {
    0: 'bold',
    1: 'italic',
    2: 'underline',
    3: 'outline',
    4: 'shadow',
    5: 'condensed',
    6: 'extended',
}

def mac_style_name(font_style):
    """Get human-readable representation of font style."""
    return ' '.join(
        _tag for _bit, _tag in STYLE_MAP.items() if font_style & (1 << _bit)
    )

def _convert_head_props(head):
    """Convert font properties from head/bhed table."""
    if not head:
        return Props()
    props = Props(
        revision=head.fontRevision,
        style=mac_style_name(head.macStyle) or None,
    )
    return props


###############################################################################
# 'hhea' table

def _convert_hhea_props(hhea, vert_fu_p_pix):
    """Convert font properties from hhea table."""
    if not hhea:
        return Props()
    props = Props(
        ascent=hhea.ascent // vert_fu_p_pix,
        descent=abs(hhea.descent // vert_fu_p_pix),
        line_height=(
            (hhea.ascent + abs(hhea.descent) + hhea.lineGap)
            // vert_fu_p_pix
        ),
    )
    return props


###############################################################################
# 'vhea' table

def _convert_vhea_props(vhea, horiz_fu_p_pix):
    """Convert font properties from vhea table."""
    if not vhea:
        return Props()
    props = Props(
        # > from the centerline to the previous line’s descent
        # > assuming top-to-bottom right-to-left
        right_extent=vhea.ascent // horiz_fu_p_pix,
        # > from the centerline to the next line’s descent
        left_extent=abs(vhea.descent) // horiz_fu_p_pix,
        line_width=(
            (vhea.ascent + abs(vhea.descent) + vhea.lineGap)
            // horiz_fu_p_pix
        ),
    )
    return props


###############################################################################
# 'name' table

def _decode_name(namerecs, nameid):
    for namerec in namerecs:
        if namerec.nameID != nameid:
            continue
        if namerec.platformID == 1:
            # mac
            encoding = MAC_ENCODING.get(namerec.platEncID, 'mac-roman')
        elif namerec.platformID == 3:
            # windows
            # > All string data for platform 3 must be encoded in UTF-16BE.
            encoding = 'utf-16be'
            #WIN_ENCODING.get(namerec.platEncID, 'utf-16le')
        elif namerec.platformID == 0:
            # unicode platform
            encoding = 'utf-16be'
        try:
            return namerec.string.decode(encoding) or None
        except UnicodeError:
            pass
        # not all these encodings will be recognised by Python
        # fallback to latin-1
        return namerec.string.decode('latin-1') or None
    return None


def _convert_version_string(version_string):
    """Convert standard sfnt version string to something more like ours."""
    # version is encoded as 'Version x.y', optionally followed by non-numeric info
    # split by non-(digit or dot)
    groups = re.split(r'([\d\.]+)', version_string)
    if len(groups) < 2 or groups[0].lower() != 'version ':
        # non-compliant version string, preserve as is
        pass
    else:
        version_number = str(float(groups[1]))
        if len(groups) == 2:
            return version_number
        version_string = ''.join(groups[2:])
        if version_number not in version_string:
            version_string = version_number + version_string
        # non-alpha separator
        if not version_string[0].isalnum():
            version_string = version_string[1:]
    return version_string.strip().rstrip('0').rstrip('.')

def _convert_name_props(name):
    """Convert font properties from name table."""
    if not name:
        return Props()
    props = Props(
        copyright=_decode_name(name.names, 0),
        family=_decode_name(name.names, 1),
        # weight or slant or both
        subfamily=_decode_name(name.names, 2),
        font_id=_decode_name(name.names, 3),
        name=_decode_name(name.names, 4),
        #
        revision=_convert_version_string(_decode_name(name.names, 5)),
        #
        #postscript_name
        #
        #trademark=_decode_name(name.names, 7),
        foundry=_decode_name(name.names, 8),
        author=_decode_name(name.names, 9),
        #
        #description=_decode_name(name.names, 10),
        #
        #vendor_url=_decode_name(name.names, 11),
        #
        #author_url=_decode_name(name.names, 12),
        notice=_decode_name(name.names, 13),
        #license_url=_decode_name(name.names, 14),
    )
    return props


###############################################################################
# 'OS/2' table

# usWeightClass
# these align with Windows values
#WEIGHT_MAP

# usWidthClass
SETWIDTH_MAP = {
    1: 'ultra-condensed',
    2: 'extra-condensed',
    3: 'condensed',
    4: 'semi-condensed',
    5: 'normal', #'medium',
    6: 'semi-expanded',
    7: 'expanded',
    8: 'extra-expanded',
    9: 'ultra-expanded',
}

def _convert_os_2_props(os_2, vert_fu_p_pix, hori_fu_p_pix):
    """Convert font properties from OS/2 table."""
    if not os_2:
        return Props()
    weight = min(900, max(100, 100 * round(os_2.usWeightClass / 100)))
    props = Props(
        weight=WEIGHT_MAP.get(weight, None),
        setwidth=SETWIDTH_MAP.get(os_2.usWidthClass, None),
        subscript_size=os_2.ySubscriptYSize // vert_fu_p_pix,
        subscript_offset=(
            int(os_2.ySubscriptXOffset // hori_fu_p_pix),
            -int(os_2.ySubscriptYOffset // vert_fu_p_pix)
        ),
        superscript_size=os_2.ySuperscriptYSize // vert_fu_p_pix,
        superscript_offset=(
            int(os_2.ySuperscriptXOffset // hori_fu_p_pix),
            int(os_2.ySuperscriptYOffset // vert_fu_p_pix)
        ),
        #ascent=os_2.sTypoAscender // vert_fu_p_pix,
        # the spec states sTypoDescender is 'usually' negative,
        # but fonttosfnt produces + values while fontforge -
        # abs should be fine as I have no interpretation for a negative descent
        # note the sign also affects int division
        #descent=abs(os_2.sTypoDescender // vert_fu_p_pix),
        line_height=(
            os_2.sTypoAscender + abs(os_2.sTypoDescender) + os_2.sTypoLineGap
        ) // vert_fu_p_pix,
    )
    if os_2.version > 1:
        props |= Props(
            x_height=os_2.sxHeight // vert_fu_p_pix,
            cap_height=os_2.sCapHeight // vert_fu_p_pix,
            default_char=Char(chr(os_2.usDefaultChar)),
            word_boundary=Char(chr(os_2.usBreakChar)),
        )
        # > This is the Unicode code point, in UTF-16 encoding, of a character
        # > that can be used for a default glyph if a requested character is not
        # > supported in the font. If the value of this field is zero,
        # > glyph ID 0 is to be used for the default character.
        if props.default_char == Char('\0'):
            props.default_char = Tag('.notdef')
    return props


###############################################################################
# 'post' table

def _convert_post_props(post, vert_fu_p_pix):
    """Convert font properties from `post` table."""
    if not post:
        return Props()
    props = Props(
        underline_descent=-post.underlinePosition // vert_fu_p_pix or None,
        underline_thickness=post.underlineThickness // vert_fu_p_pix or None,
    )
    return props
