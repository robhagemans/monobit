from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.tables.E_B_D_T_ import ebdt_bitmap_format_1
from fontTools.ttLib.tables.BitmapGlyphMetrics import SmallGlyphMetrics
from fontTools.ttLib.tables.E_B_L_C_ import Strike, BitmapSizeTable, eblc_index_sub_table_3, SbitLineMetrics
from fontTools.ttLib.tables._g_l_y_f import Glyph as Glyf
from fontTools import ttLib

import logging
logging.basicConfig(level=logging.DEBUG)

import monobit
from monobit import Glyph


f, *_ = monobit.load('tests/fonts/4x6.yaff')
# f, *_ = monobit.load('tests/fonts/8x8.bbc')
# f = f.modify(encoding='unicode')

# get char labels if we don't have them
f = f.label()

# TODO: drop glyphs without char labels as not-storable

# label with unicode
f = f.label(codepoint_from='unicode', overwrite=True)
# we need Adobe glyph names
f = f.label(tag_from=monobit.tagmaps['adobe'])

funits_per_em = 1024

fb = FontBuilder(funits_per_em, isTTF=True)
#glyphnames = ('.notdef', *(str(_t) for _t in f.get_tags()))
glyphnames= ['.notdef', '.null', 'space', 'A', 'a']
fb.setupGlyphOrder(glyphnames)


glyphs = {
    _name: f.get_glyph(tag=_name, missing='default')
    for _name in glyphnames
}

map = {
    int(_g.codepoint): _name
    for _name, _g in glyphs.items() if _g.codepoint and _name not in ('.notdef', '.null')
}
# map[0] = '.null'
print(map.keys())
fb.setupCharacterMap(map)



# fontBuilder needs all these defined, even if empty
# that aligns with fonttosfnt, but fonttforge leaves glyf table empty (both by default)
fb.setupGlyf({
    _name: Glyf()
    for _name in glyphnames
})

# EBLC, EBDT
ebdt = ttLib.newTable('EBDT')
fb.font['EBDT'] = ebdt
ebdt.version = 2.0

eblc = ttLib.newTable('EBLC')
fb.font['EBLC'] = eblc
eblc.version = 2.0


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
    # bmga.compile(fb.font)
    return bmga


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
bst.ppemX = f.bounding_box.x
bst.ppemY = f.line_height

bst.hori = SbitLineMetrics()
bst.hori.ascender = f.ascent
bst.hori.descender = f.descent
bst.hori.widthMax = f.max_width

# ?
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
bst.vert = SbitLineMetrics()
bst.vert.ascender = 0
bst.vert.descender = 0
bst.vert.widthMax = 8
bst.vert.caretSlopeNumerator = 0
bst.vert.caretSlopeDenominator = 0
bst.vert.caretOffset = 0
bst.vert.minOriginSB = 0
bst.vert.minAdvanceSB = 0
bst.vert.maxBeforeBL = 0
bst.vert.minAfterBL = 0
bst.vert.pad1 = 0
bst.vert.pad2 = 0




strike = Strike()
strike.bitmapSizeTable = bst
ist = eblc_index_sub_table_3(data=b'', ttFont=fb.font)

ist.names = glyphnames

ist.indexFormat = 3

# this should be based on EBDT info (ebdt_bitmap_format_1)
ist.imageFormat = 1

strike.indexSubTables = [ist]
eblc.strikes = [strike]
# eblc strike locations are filled out by ebdt compiler

# is this needed? or does ft do this automatically?
# eblc.numSizes = len(eblc.strikes)

# bitmap size table is not updated by fontTools, do it explicitly
bst.numberOfIndexSubTables = len(strike.indexSubTables)

fuppx = funits_per_em // bst.ppemX
fuppy = funits_per_em // bst.ppemY

# horizontal metrics tables
metrics = {
    # CHECK: should this have left_bearing instead of xMin?
    _name: (_g.advance_width * fuppx

    # number of h metrics gets reduced from the right so long as metrics are the same
    # -len(_name)

    , _g.left_bearing * fuppx)
    for _name, _g in glyphs.items()
}


# glyphs MUST BE SORTED by GlyphID (codepoint??) or fontTools will calculate numberOfHMetrics wrong
metrics['.null'] = (0, 0)

print(metrics)
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=f.ascent*fuppx, descent=-f.descent*fuppy)


styleName = "TotallyNormal"

fb.setupNameTable(dict(
    familyName=f.family,
    styleName=styleName,
    uniqueFontIdentifier=f.font_id or 'test',
    fullName=f.name,
    psName=f.family + "-" + styleName,
    version=f.revision,
))

fb.setupOS2(sTypoAscender=f.ascent*fuppx, usWinAscent=f.ascent*fuppx, usWinDescent=f.descent*fuppx)

# todo: store Adobe names, or move to version-3 table
fb.setupPost()

fb.save("test.otb")
