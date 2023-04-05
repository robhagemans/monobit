from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.tables.E_B_D_T_ import ebdt_bitmap_format_1
from fontTools.ttLib.tables.BitmapGlyphMetrics import SmallGlyphMetrics
from fontTools.ttLib.tables.E_B_L_C_ import Strike, BitmapSizeTable, eblc_index_sub_table_3, SbitLineMetrics
from fontTools.ttLib.tables._g_l_y_f import Glyph as Glyf
from fontTools import ttLib

import logging
logging.basicConfig(level=logging.DEBUG)

from monobit import Glyph


fb = FontBuilder(1024, isTTF=True)
glyphnames = [".notdef", ".null", "space", "A", "a"]
fb.setupGlyphOrder(glyphnames)
fb.setupCharacterMap({32: "space", 65: "A", 97: "a"})
advanceWidths = {".notdef": 600, "space": 500, "A": 600, "a": 600, ".null": 0}

familyName = "HelloTestFont"
styleName = "TotallyNormal"
version = "0.1"
nameStrings = dict(
    familyName=familyName, #dict(en=familyName, nl="HalloTestFont"),
    styleName=styleName, #dict(en=styleName, nl="TotaalNormaal"),
    uniqueFontIdentifier="fontBuilder: " + familyName + "." + styleName,
    fullName=familyName + "-" + styleName,
    psName=familyName + "-" + styleName,
    version="Version " + version,
)

glyph = Glyf()
# fontBuilder needs all these defined, even if empty
# that aligns with fonttosfnt default, but we should be able to leave glyf table empty (fontforge default)
glyphs = {".notdef": glyph, "space": glyph, "A": glyph, "a": glyph, ".null": glyph}
fb.setupGlyf(glyphs)

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

glyph = Glyph.from_bytes(b'\0\xff\x81\x81\xff\x81\x81\x81', width=8)
bmga = convert_to_glyph(glyph, fb)

from copy import copy

ebdt.strikeData = [{
    ".notdef": bmga,
    "space": copy(bmga),
    "A": copy(bmga),
    "a": copy(bmga),
    ".null": copy(bmga)
}]


strike = Strike()

# create the BitmapSize record
# this is not contructed by any compile() method as far as I can see

# > The line metrics are not used directly by the rasterizer, but are available to applications that want to parse the EBLC table.


bst = BitmapSizeTable()
bst.colorRef = 0
bst.flags = 0x01  # hori | 0x02 for vert
bst.ppemX = 8
bst.ppemY = 8
bst.bitDepth = 1

bst.hori = SbitLineMetrics()
# check: sbit ascender/descender are in pixels? this is what we assume in the reader
bst.hori.ascender = 7
bst.hori.descender = 0
bst.hori.widthMax = 8
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





strike.bitmapSizeTable = bst
ist = eblc_index_sub_table_3(data=b'', ttFont=fb.font)
ist.names = glyphnames
ist.indexFormat = 3

# FIXME - base on BDAT info (ebdt_bitmap_format_1)
ist.imageFormat = 1

strike.indexSubTables = [ist]
eblc.strikes = [strike]
# eblc strike locations are filled out by ebdt compiler

# is this needed? or does ft do this automatically?
# eblc.numSizes = len(eblc.strikes)

# bitmap size table is not updated by fontTools, do it explicitly
bst.numberOfIndexSubTables = len(strike.indexSubTables)


# ebdt.compile(fb.font)
# print(dir(eblc.strikes[0].bitmapSizeTable))
# eblc.strikes[0].indexSubTables[0].imageFormat  = 0
# eblc.strikes[0].indexSubTables[0].indexFormat  = 3

metrics = {}
glyphTable = fb.font["glyf"]
for gn, advanceWidth in advanceWidths.items():
    metrics[gn] = (advanceWidth, glyphTable[gn].xMin)

fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=824, descent=-200)
fb.setupNameTable(nameStrings)

fb.setupOS2(sTypoAscender=824, usWinAscent=824, usWinDescent=200)
fb.setupPost()
fb.save("test.otb")
