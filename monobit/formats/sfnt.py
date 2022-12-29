"""
monobit.formats.sfnt - TrueType/OpenType and related formats

(c) 2022 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
import json


try:
    from fontTools import ttLib
except ImportError:
    ttLib = None
else:
    from fontTools.ttLib import TTLibError
    from fontTools.ttLib.ttFont import TTFont
    from fontTools.ttLib.ttCollection import TTCollection

from ..properties import Props
from ..font import Font
from ..glyph import Glyph
from ..storage import loaders, savers
from ..streams import FileFormatError


# errors that invalidates only one strike or resource, not the whole file

class ResourceFormatError(FileFormatError):
    """Unsupported parameters in resource."""

class StrikeFormatError(ResourceFormatError):
    """Unsupported parameters in bitmap strike."""


# must be importable by mac module
load_sfnt = None

if ttLib:
    @loaders.register(
        'otb', 'ttf', 'otf', 'woff', 'tte',
        magic=(
            # TrueType
            b'\0\1\0\0',
            b'true',
            # OpenType
            b'OTTO',
            # WOFF
            b'wOFF',
        ),
        name='sfnt',
    )
    def load_sfnt(infile, where=None):
        """Load an SFNT resource and convert to Font."""
        sfnt = _read_sfnt(infile)
        logging.debug(str(sfnt))
        fonts = _convert_sfnt(sfnt)
        return fonts

    @loaders.register(
        'ttc', 'otc',
        magic=(
            # TrueType
            b'ttcf',
        ),
        name='ttcf',
    )
    def load_collection(infile, where=None):
        """Load a TrueType/OpenType Collection file."""
        sfnts = _read_collection(infile)
        fonts = []
        for _sfnt in sfnts:
            fonts.extend(_convert_sfnt(_sfnt))
        return fonts


###############################################################################
# fontTools extensions

# bdat/bloc tables are Apple's version of EBDT/EBLC.
# They have the same structure but a different tag.
table__b_h_e_d = None
table__b_l_o_c = None
table__b_d_a_t = None

def _init_fonttools():
    """Register extension classes for fontTools."""
    if not ttLib:
        raise FileFormatError(
            'Parsing `sfnt` resources requires module `fontTools`, '
            'which is not available.'
        )
    global table__b_h_e_d, table__b_l_o_c, table__b_d_a_t
    if table__b_d_a_t:
        return

    from fontTools.ttLib.tables._h_e_a_d import table__h_e_a_d
    from fontTools.ttLib.tables.E_B_L_C_ import table_E_B_L_C_
    from fontTools.ttLib.tables.E_B_D_T_ import table_E_B_D_T_

    class table__b_h_e_d(table__h_e_a_d): pass
    class table__b_l_o_c(table_E_B_L_C_): pass

    class table__b_d_a_t(table_E_B_D_T_):
        locatorName = "bloc"

    ttLib.registerCustomTableClass('bhed', 'monobit.formats.sfnt')
    ttLib.registerCustomTableClass('bloc', 'monobit.formats.sfnt')
    ttLib.registerCustomTableClass('bdat', 'monobit.formats.sfnt')


###############################################################################
# sfnt resource reader

# tags we will decompile and process
_TAGS = (
    'maxp',
    'cmap',
    'bhed', 'head',
    'EBDT', 'bdat', 'EBLC', 'bloc',
    'hmtx', 'hhea',
)


def _read_sfnt(instream):
    """Read an SFNT resource into data structure."""
    # let fonttools parse the SFNT
    _init_fonttools()
    try:
        ttf = TTFont(instream)
    except (TTLibError, AssertionError) as e:
        raise FileFormatError(f'Could not read sfnt file: {e}')
    return _sfnt_props(ttf)

def _read_collection(instream):
    """Read a collection into data structures."""
    # let fonttools parse the SFNT
    _init_fonttools()
    try:
        ttfc = TTCollection(instream)
    except (TTLibError, AssertionError) as e:
        raise FileFormatError(f'Could not read collection file: {e}')
    ttfc_data = []
    for ttf in ttfc:
        try:
            ttfc_data.append(_sfnt_props(ttf))
        except ResourceFormatError as e:
            logging.warning(e)
    return ttfc_data


def _sfnt_props(ttf):
    """Decompile tables and convert from fontTools objects to data structure."""
    try:
        tables = {_tag: ttf.get(_tag, None) for _tag in _TAGS}
        return Props(**_to_props(tables))
    except (TTLibError, AssertionError) as e:
        raise ResourceFormatError(f'Could not read sfnt: {e}') from e


def _to_props(obj):
    """Recursively convert fontTools objects to namespaces."""
    # avoid infinite recursion
    if isinstance(obj, TTFont):
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
    sfnt.bhed = sfnt.bhed or sfnt.head
    if not sfnt.bdat or not sfnt.bloc:
        raise ResourceFormatError('No bitmap strikes found in sfnt resource.')
    fonts = []
    for i_strike in range(sfnt.bloc.numSizes):
        props = _convert_props(sfnt, i_strike)
        glyphs = _convert_glyphs(sfnt, i_strike)
        fonts.append(Font(glyphs, source_format=source_format, **vars(props)))
    return fonts



# preferred table to use for Unicode: platformID, platEncID
_UNICODE_CHOICES = (
    # Unicode platform, full repertoire
    (0, 4),
    (0, 6),
    # Windows platform, full repertoiire
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
    known_tables = tuple(_t for _t in sfnt.cmap.tables)
    for id_pair in _UNICODE_CHOICES:
        for table in known_tables:
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
    known_tables = tuple(_t for _t in sfnt.cmap.tables)
    # get the largest table for non-unicode mappings
    non_unicode_tables = (
        _t.cmap for _t in known_tables
        if (int(_t.platformID), int(_t.platEncID)) not in _UNICODE_CHOICES
    )
    non_unicode_tables = sorted(
        ((len(_t), _t) for _t in non_unicode_tables),
        reverse=True
    )
    enctable = non_unicode_tables[0][1] if non_unicode_tables else {}
    enctable = {
        _name: int(_ord)
        for _ord, _name in enctable.items()
    }
    return enctable


def _convert_glyph_metrics(metrics, small_is_vert):
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
            shift_left=metrics.vertBearingX,
            top_bearing=metrics.vertBearingY,
            bottom_bearing=(
                metrics.vertAdvance - metrics.height
                - metrics.vertBearingY
            ),
        )
    elif not small_is_vert:
        # small metrics
        return dict(
            left_bearing=metrics.dearingX,
            right_bearing=metrics.advance - metrics.width - metrics.bearingX,
            shift_up=metrics.bearingY - metrics.height,
        )
    else:
        # small metrics, interpret as vert
        return dict(
            shift_left=metrics.bearingX,
            top_bearing=metrics.bearingY,
            bottom_bearing=(
                metrics.advance - metrics.height - metrics.bearingY
            ),
        )


def _convert_glyphs(sfnt, i_strike):
    """Build glyphs and glyph properties from sfnt data."""
    unitable = _get_unicode_table(sfnt)
    enctable = _get_encoding_table(sfnt)
    glyphs = []
    strike = sfnt.bdat.strikeData[i_strike]
    blocstrike = sfnt.bloc.strikes[i_strike]
    for name, glyph in strike.items():
        try:
            metrics = glyph.metrics
        except AttributeError:
            for subtable in blocstrike.indexSubTables:
                if name in subtable.names:
                    metrics = subtable.metrics
                    break
            else:
                logging.warning('No metrics found.')
                metrics = {}
        byts = getattr(glyph, 'imageData', '')
        bits = bin(int.from_bytes(byts, 'big'))
        width = metrics.width
        small_is_vert = blocstrike.bitmapSizeTable.flags == 2
        props = _convert_glyph_metrics(metrics, small_is_vert)
        glyph = Glyph.from_bytes(
            byts, width=8, align='bit',
            tag=name, char=unitable.get(name, ''),
            codepoint=enctable.get(name, b''), **props
        )
        glyphs.append(glyph)
    return glyphs


def _convert_props(sfnt, i_strike):
    """Build font properties from sfnt data."""
    strike = sfnt.bloc.strikes[i_strike]
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
    # asppect ratio is the inverse of pixels-per-em ratio
    props.pixel_aspect = (bmst.ppemY, bmst.ppemX)
    small_metrics_are_vert = bmst.flags == 2
    # horizontal line metrics
    # according to the EBLC spec the sbit metrics also define the linegap
    # but I don't see it. widthMax looks like a max advance
    props.ascent = bmst.hori.ascender
    props.descent = -bmst.hori.descender
    # vertical line metrics
    # we don't keep track of 'ascent' and 'descent' for vert, maybe we should
    # anyway, which way is the 'ascent', left or right?
    return props

# maxp

# name - metadata strings

# hhea, hmtx - horizontal metrics. not used in apple. ff adds them to otb
# vhea, vmtx
# OS/2 - Windows metrics
# post - postscript printer information

# kern - Apple kerning
# GPOS - Opentype kerning

# ESBC - embedded bimap scling table.
# see fontforge, not supported by fonttools
# used by fforge to generate fake windows bitmap-only ttfs

# loca, glyf - added but empty in fontforge's otb
# but https://github.com/fonttools/fonttools/issues/684
# > I think the empty `glyf`/`loca` tables are complicating thins needlessly. They are not needed, HarfBuzz (and I think FreeType) will handle the fonts without these tables just fine and no other systems support these fonts any way. FontForge should either no added the empty table or have an option not to do so.
