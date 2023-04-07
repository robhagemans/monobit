"""
monobit.formats.sfnt_writer - TrueType/OpenType and related formats (writer)

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

try:
    from fontTools import ttLib
except ImportError:
    ttLib = None
else:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.ttLib.tables.E_B_D_T_ import ebdt_bitmap_format_1
    from fontTools.ttLib.tables.BitmapGlyphMetrics import SmallGlyphMetrics
    from fontTools.ttLib.tables.E_B_L_C_ import (
        Strike, BitmapSizeTable, eblc_index_sub_table_3, SbitLineMetrics
    )
    from fontTools.ttLib.tables._g_l_y_f import Glyph as Glyf

from ..glyph import Glyph
from ..binary import ceildiv
from ..storage import loaders, savers
from ..taggers import tagmaps

if ttLib:
    from .sfnt import load_sfnt

    @savers.register(linked=load_sfnt)
    def save_sfnt(fonts, outfile, funits_per_em:int=1024):
        """
        Save font to an SFNT resource.
        Currently only saves bitmap-only SFNTs (OTB flavour)

        funits_per_em: number of design units (FUnits) per em-width (default 1024)
        """
        font, *rest = fonts
        if rest:
            raise ValueError(
                'Currently only supporting saving one font to SFNT.'
            )
        _write_sfnt(font, outfile, funits_per_em)
        return font


def _label_to_utf16(font, label):
    """Convert a glyph label to a UTF-16 codepoint, if possible; 0 if not."""
    try:
        utf16 = ord(font.get_glyph(label).char)
    except KeyError:
        utf16 = 0
    else:
        if utf16 > 0x1000:
            utf16 = 0
    return utf16


def _convert_to_os_2_props(font, _to_funits):
    """Convert font properties to `OS/2` table."""
    # weight = min(900, max(100, 100 * round(os_2.usWeightClass / 100)))
    props = dict(
        version=3,
        # characteristics
        # TODO weight=_WEIGHT_MAP.get(weight, None),
        # TODO setwidth=_SETWIDTH_MAP.get(os_2.usWidthClass, None),
        sxHeight=_to_funits(font.x_height),
        sCapHeight=_to_funits(font.cap_height),
        # subscript metrics
        ySubscriptXSize=_to_funits(font.subscript_size),
        ySubscriptYSize=_to_funits(font.subscript_size),
        ySubscriptXOffset=_to_funits(font.subscript_offset.x),
        ySubscriptYOffset=-_to_funits(font.subscript_offset.y),
        # superscript metrics
        ySuperscriptXSize=_to_funits(font.superscript_size),
        ySuperscriptYSize=_to_funits(font.superscript_size),
        ySuperscriptXOffset=_to_funits(font.superscript_offset.x),
        ySuperscriptYOffset=_to_funits(font.superscript_offset.y),
        # typographic extents
        usWinAscent=_to_funits(font.ascent),
        usWinDescent=_to_funits(font.descent),
        sTypoAscender=_to_funits(font.ascent),
        # the spec states sTypoDescender is 'usually' negative,
        # but fonttosfnt produces + values while fontforge -
        sTypoDescender=-_to_funits(font.descent),
        sTypoLineGap=_to_funits(font.leading),
        # not included: strikeout metrics
        # not included: panose table
        # special characters
        usDefaultChar=_label_to_utf16(font, font.default_char),
        usBreakChar=_label_to_utf16(font, font.word_boundary),
        # vendor ID - can be left blank (four spaces)
        achVendID=b'    ',
    )
    return props


def _convert_to_name_props(font):
    """Convert font properties to `name` table."""
    props = dict(
        # 0
        copyright=font.copyright,
        # 1
        familyName=font.family,
        # 2
        styleName=font.subfamily,
        # 3
        uniqueFontIdentifier=font.font_id,
        # 4
        fullName=font.name,
        # 5
        # TODO: should be 'Version x.y'
        version=font.revision,
        # 6
        #psName=font.name.replace(' ', '-'),
        # trademark (nameID 7)
        # 8
        manufacturer=font.foundry,
        # 9
        designer=font.author,
        # 10
        # description=font.description,
        # vendorURL (nameID 11)
        # designerURL (nameID 12)
        # 13
        licenseDescription=font.notice,
        # licenseInfoURL (nameID 14)
        # typographicFamily (nameID 16)
        # typographicSubfamily (nameID 17)
        # compatibleFullName (nameID 18)
        # sampleText (nameID 19)
        # postScriptCIDFindfontName (nameID 20)
        # wwsFamilyName (nameID 21)
        # wwsSubfamilyName (nameID 22)
        # lightBackgroundPalette (nameID 23)
        # darkBackgroundPalette (nameID 24)
        # variationsPostScriptNamePrefix (nameID 25)
    )
    return props

def _convert_to_hhea_props(font, _to_funits):
    """Convert font properties to `hhea` table."""
    return dict(
        ascent=_to_funits(font.ascent),
        descent=-_to_funits(font.descent),
        lineGap=_to_funits(font.leading),
        # other values are compiled by fontTools
    )


def _convert_to_hmtx_props(glyphs, _to_funits):
    """Convert glyph properties to `hmtx` table."""
    return {
        _name: (_to_funits(_g.advance_width), _to_funits(_g.left_bearing))
        for _name, _g in glyphs.items()
    }


def _convert_to_cmap_props(glyphs):
    """Convert glyph properties to `cmap` table."""
    return {
        int(_g.codepoint): _name
        for _name, _g in glyphs.items() if _g.codepoint and _name not in ('.notdef', '.null')
    }


def _create_empty_glyf_props(glyphs):
    """Create `glyf` table withh empty glyphs."""
    # fontBuilder needs all these defined, even if empty
    # we'll remove it at the end as OTB files should not have any
    return {_name: Glyf() for _name in glyphs}


def _setup_bitmap_tables(fb, font, glyphs):
    """Build `EBLC` and `EBDT` tables."""
    ebdt = ttLib.newTable('EBDT')
    fb.font['EBDT'] = ebdt
    ebdt.version = 2.0

    eblc = ttLib.newTable('EBLC')
    fb.font['EBLC'] = eblc
    eblc.version = 2.0

    glyphtable = {
        _name: convert_to_glyph(_g, fb)
        for _name, _g in glyphs.items()
    }
    ebdt.strikeData = [glyphtable]

    # create the BitmapSize record
    # this is not contructed by any compile() method as far as I can see

    # > The line metrics are not used directly by the rasterizer, but are available to applications that want to parse the EBLC table.
    bst = BitmapSizeTable()
    bst.colorRef = 0
    bst.flags = 0x01  # hori | 0x02 for vert
    bst.bitDepth = 1

    # ppem need to be the same both ways for fontforge
    bst.ppemX = font.pixel_size
    bst.ppemY = font.pixel_size
    # build horizontal line metrics
    bst.hori = SbitLineMetrics()
    bst.hori.ascender = font.ascent
    bst.hori.descender = -font.descent
    bst.hori.widthMax = font.max_width
    # defaults for caret metrics
    bst.hori.caretSlopeNumerator = 0
    bst.hori.caretSlopeDenominator = 1
    bst.hori.caretOffset = 0
    # shld be minimum of horibearingx. pixels? funits?
    bst.hori.minOriginSB = 0
    bst.hori.minAdvanceSB = 0
    bst.hori.maxBeforeBL = 0
    bst.hori.minAfterBL = 0
    bst.hori.pad1 = 0
    bst.hori.pad2 = 0

    # ignore vertical metrics for now
    bst.vert = bst.hori

    strike = Strike()
    strike.bitmapSizeTable = bst
    ist = eblc_index_sub_table_3(data=b'', ttFont=fb.font)

    ist.names = tuple(glyphs.keys())

    ist.indexFormat = 3

    # this should be based on EBDT info (ebdt_bitmap_format_1)
    ist.imageFormat = 1

    strike.indexSubTables = [ist]
    eblc.strikes = [strike]
    # eblc strike locations are filled out by ebdt compiler
    # bitmap size table is not updated by fontTools, do it explicitly
    bst.numberOfIndexSubTables = len(strike.indexSubTables)


def convert_to_glyph(glyph, fb):
    """Create fontTools bitmap glyph."""
    bmga = ebdt_bitmap_format_1(data=b'', ttFont=fb.font)
    # horizontal metrics
    bmga.metrics = SmallGlyphMetrics()
    bmga.metrics.height = glyph.height
    bmga.metrics.width = glyph.width
    bmga.metrics.BearingX = glyph.left_bearing
    bmga.metrics.BearingY = glyph.shift_up + glyph.height
    bmga.metrics.Advance = glyph.advance_width
    bmga.setRows(glyph.as_byterows())
    return bmga


def _write_sfnt(f, outfile, funits_per_em):
    """Convert to SFNT and write out."""

    def _to_funits(pixel_amount):
        # note that x and y ppem are equal - if not, fontforge rejects the bitmap
        return ceildiv(pixel_amount * funits_per_em, f.pixel_size)

    # get char labels if we don't have them
    f = f.label()
    # TODO: drop glyphs without char labels as not-storable
    # label with unicode
    f = f.label(codepoint_from='unicode', overwrite=True)
    # we need Adobe glyph names
    f = f.label(tag_from=tagmaps['adobe'])
    # cut back to glyph bounding boxes
    f = f.reduce()
    # get the storable glyphs
    glyphnames = ('.notdef', *(_t.value for _t in f.get_tags()))
    glyphs = {
        _name: f.get_glyph(tag=_name, missing='default')
        for _name in glyphnames
    }
    # build font object
    fb = FontBuilder(funits_per_em, isTTF=True)
    fb.setupGlyphOrder(glyphnames)
    fb.setupCharacterMap(_convert_to_cmap_props(glyphs))
    fb.setupGlyf(_create_empty_glyf_props(glyphs))
    _setup_bitmap_tables(fb, f, glyphs)
    fb.setupHorizontalMetrics(_convert_to_hmtx_props(glyphs, _to_funits))
    fb.setupHorizontalHeader(**_convert_to_hhea_props(f, _to_funits))
    fb.setupNameTable(_convert_to_name_props(f))
    fb.setupOS2(**_convert_to_os_2_props(f, _to_funits))
    # for otb: version-3 table, defines no names
    fb.setupPost(keepGlyphNames=False)

    # TODO: kern table (GPOS? only needed for CFF opentype)
    # TODO: vmtx, big glyph metrics
    # TODO: AAT version with bhed, bdat, bloc

    # OTB output
    # ensure we get an empty glyf table
    fb.font['glyf'].compile = lambda self: b''
    # loca table with null for every glyph
    fb.font['loca'].compile = lambda self: bytes(len(glyphnames)*2+2)
    fb.save(outfile)
