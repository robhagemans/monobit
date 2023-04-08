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
    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

from ..glyph import Glyph
from ..binary import ceildiv
from ..storage import loaders, savers
from ..properties import reverse_dict
from .sfnt import _WEIGHT_MAP, _SETWIDTH_MAP
from ..labels import Tag

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


def _label_to_utf16(font, label, default):
    """Convert a glyph label to a UTF-16 codepoint, if possible; 0 if not."""
    try:
        utf16 = ord(font.get_glyph(label).char)
    except KeyError:
        utf16 = default
    else:
        if utf16 > 0x1000:
            utf16 = default
    return utf16


def _convert_to_os_2_props(font, _to_funits):
    """Convert font properties to `OS/2` table."""
    # weight = min(900, max(100, 100 * round(os_2.usWeightClass / 100)))
    props = dict(
        version=3,
        # characteristics
        usWeightClass=reverse_dict(_WEIGHT_MAP).get(font.weight, 400),
        usWidthClass=reverse_dict(_SETWIDTH_MAP).get(font.setwidth, 5),
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
        # if default_char can't be mappped to a utf-16 codepoint,
        # it falls back to 0 which is taken to mean .notdef (not u+0000)
        usDefaultChar=_label_to_utf16(font, font.default_char, 0),
        # if break char can't be matched, fall back to SPACE
        usBreakChar=_label_to_utf16(font, font.word_boundary, 0x20),
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

def _convert_to_vhea_props(font, _to_funits):
    """Convert font properties to `vhea` table."""
    return dict(
        ascent=_to_funits(font.right_extent),
        descent=-_to_funits(font.left_extent),
        lineGap=_to_funits(font.line_width - font.right_extent - font.left_extent),
        # other values are compiled by fontTools
    )


def _convert_to_hmtx_props(glyphs, _to_funits):
    """Convert glyph properties to `hmtx` table."""
    return {
        _name: (_to_funits(_g.advance_width), _to_funits(_g.left_bearing))
        for _name, _g in glyphs.items()
    }

def _convert_to_vmtx_props(glyphs, _to_funits):
    """Convert glyph properties to `vmtx` table."""
    return {
        _name: (_to_funits(_g.advance_height), _to_funits(_g.top_bearing))
        for _name, _g in glyphs.items()
    }



def _convert_to_cmap_props(glyphs):
    """Convert glyph properties to `cmap` table."""
    return {
        int(_g.codepoint): _name
        for _name, _g in glyphs.items() if _g.codepoint and _name not in ('.notdef', '.null')
    }


def _convert_to_kern_props(font, glyphs, _to_funits):
    """Convert kerning values to `kern` table."""
    kern_table = {}
    for tag, glyph in glyphs.items():
        for label, value in glyph.right_kerning.items():
            try:
                rtag, *_ = font.get_glyph(label).tags
            except (KeyError, ValueError) as e:
                continue
            kern_table[(tag, rtag.value)] = _to_funits(value)
        for label, value in glyph.left_kerning.items():
            try:
                ltag, *_ = font.get_glyph(label).tags
            except (KeyError, ValueError) as e:
                continue
            kern_table[(ltag.value, tag)] = _to_funits(value)
    return dict(
        # version 1.0 means apple==True
        version=0,
        # coverage=1 means horizontal kerning
        kernTables=(dict(coverage=1, kernTable=kern_table),),
    )

def _setup_kern_table(fb, version=0, kernTables=()):
    """Build `kern` table."""
    kern_table = ttLib.newTable('kern')
    kern_table.version = version
    kern_table.kernTables = []
    for subdict in kernTables:
        subtable = KernTable_format_0(apple=version==1.0)
        subtable.__dict__.update(subdict)
        kern_table.kernTables.append(subtable)
    if any(_k.kernTable for _k in kern_table.kernTables):
        fb.font['kern'] = kern_table


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


def _prepare_for_sfnt(font):
    """Prepare monobit font for storing in sfnt."""
    # get char labels if we don't have them
    # label with unicode and Adobe glyph names
    font = font.label(match_whitespace=False, match_graphical=False)
    # warn we're dropping glyphs without char labels as not-storable
    dropped = tuple(_g for _g in font.glyphs if not _g.char)
    if dropped:
        logging.warning(
            '%d glyphs could not be stored: could not label with unicode character', len(dropped)
        )
        logging.debug('Dropped glyphs: %s', tuple(_g.get_labels()[0] for _g in dropped if _g.get_labels()))
    default = font.get_default_glyph()
    font = font.label(
        codepoint_from='unicode', overwrite=True,
        match_whitespace=False, match_graphical=False
    )
    font = font.label(tag_from='adobe')
    # cut back to glyph bounding boxes
    font = font.reduce()
    return font, default


def _write_sfnt(font, outfile, funits_per_em):
    """Convert to SFNT and write out."""
    # converter from pixels to design units
    # note that x and y ppem are equal - if not, fontforge rejects the bitmap
    def _to_funits(pixel_amount):
        return ceildiv(pixel_amount * funits_per_em, font.pixel_size)

    font, default = _prepare_for_sfnt(font)
    # get the storable glyphs
    glyphnames = ('.notdef', *(_t.value for _t in font.get_tags()))
    glyphs = {
        _name: font.get_glyph(tag=_name, missing=default)
        for _name in glyphnames
    }
    # build font object
    fb = FontBuilder(funits_per_em, isTTF=True)
    fb.setupGlyphOrder(glyphnames)
    fb.setupCharacterMap(_convert_to_cmap_props(glyphs))
    fb.setupGlyf(_create_empty_glyf_props(glyphs))
    _setup_bitmap_tables(fb, font, glyphs)
    fb.setupHorizontalMetrics(_convert_to_hmtx_props(glyphs, _to_funits))
    fb.setupHorizontalHeader(**_convert_to_hhea_props(font, _to_funits))
    # todo: check for vertical metrics, omit if not present
    fb.setupVerticalMetrics(_convert_to_vmtx_props(glyphs, _to_funits))
    fb.setupVerticalHeader(**_convert_to_vhea_props(font, _to_funits))
    fb.setupNameTable(_convert_to_name_props(font))
    fb.setupOS2(**_convert_to_os_2_props(font, _to_funits))
    # for otb: version-3 table, defines no names
    fb.setupPost(keepGlyphNames=False)
    _setup_kern_table(fb, **_convert_to_kern_props(font, glyphs, _to_funits))
    # OTB output
    # ensure we get an empty glyf table
    fb.font['glyf'].compile = lambda self: b''
    # loca table with null for every glyph
    fb.font['loca'].compile = lambda self: bytes(len(glyphnames)*2+2)
    fb.save(outfile)
