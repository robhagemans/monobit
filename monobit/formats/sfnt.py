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
    from fontTools.ttLib.ttFont import TTFont
    from fontTools.ttLib.tables.E_B_D_T_ import BitmapGlyph
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
except ImportError:
    ttLib = None

from ..properties import Props
from ..font import Font
from ..glyph import Glyph


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

    # bdat/bloc tables are Apple's version of EBDT/EBLC.
    # They have the same structure but a different tag.
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


def load_sfnt(instream):
    sfnt = _read_sfnt(instream)
    logging.debug(repr(sfnt))
    font = _convert_sfnt(sfnt)
    return font


def _read_sfnt(instream):
    """Read an SFNT resource into data structure."""
    # let fonttools parse the SFNT
    _init_fonttools()
    ttf = TTFont(instream)
    # decoompile tables we will need
    tags = ('cmap', 'bhed', 'head', 'EBDT', 'bdat', 'EBLC', 'bloc', 'maxp')
    tables = {_tag: ttf.get(_tag, None) for _tag in tags}
    return Props(**_to_props(tables))


def _to_props(obj):
    """Recursively convert fontTools objects to namespaces."""
    # avoid infinite recursion
    if isinstance(obj, TTFont):
        return str(obj)
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
    glyphs = _convert_glyphs(sfnt)
    return Font(glyphs, source_format=source_format)


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


def _convert_glyphs(sfnt):
    unitable = _get_unicode_table(sfnt)
    enctable = _get_encoding_table(sfnt)
    glyphs = []
    for i_strike, strike in enumerate(sfnt.bdat.strikeData):
        for name, glyph in strike.items():
            try:
                metrics = glyph.metrics
            except AttributeError:
                for subtable in sfnt.bloc.strikes[i_strike].indexSubTables:
                    if name in subtable.names:
                        metrics = subtable.metrics
                        break
                else:
                    logging.warning('No metrics found.')
                    metrics = {}
            byts = getattr(glyph, 'imageData', '')
            bits = bin(int.from_bytes(byts, 'big'))
            width = metrics.width

            glyph = Glyph.from_bytes(
                byts, width=8, align='bit',
                tag=name, char=unitable.get(name, ''),
                codepoint=enctable.get(name, b''),
            )
            glyphs.append(glyph)
    return glyphs



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
