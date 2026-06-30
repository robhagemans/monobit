"""
monobit.storageformats.sfnt_writer - TrueType/OpenType and related formats (writer)

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO

from monobit.core import Glyph
from monobit.core import Tag
from monobit.base.binary import ceildiv
from monobit.storage import loaders, savers
from monobit.storage.utils.limitations import ensure_single
from monobit.base import reverse_dict, to_number, safe_import
from monobit.renderer import glyph_to_image

from .sfnt import WEIGHT_MAP, SETWIDTH_MAP, NOTDEF_NAME, fonttools_loaded
from .sfnt import load_sfnt, load_collection
from ..common import to_postscript_name

fonttools = safe_import('monobit.storage.fontformats.sfnt.fonttools')


if fonttools_loaded:

    @savers.register(linked=load_sfnt)
    def save_sfnt(
            fonts, outfile,
            funits_per_em:int=1024, strike_format:str='bit', flavour:str='otb',
            glyph_names:str=None,
        ):
        """
        Save bitmap font to an sfnt resource (TrueType/OpenType file).

        funits_per_em: number of design units (FUnits) per em-width (default 1024)
        strike_format: store as bitmaps aligned by 'byte', 'bit' (default) or as 'png' or 'tiff' (sbix only)
        flavour: type of sfnt resource: 'otb' (EBDT or CBDT-based; default) or 'apple' (bdat or sbix-based)
        glyph_names: tagger to set glyph names with. Default is no glyph names. Use 'tags' to use existing tags as glyph names.
        """
        # some sfnt flavours *can* store multiple fonts, e.g. different dpi in sbix
        # we don't currently support that.
        font = ensure_single(fonts)
        tt_font = _create_sfnt(
            font, funits_per_em, strike_format,
            flavour=flavour.lower(),
            glyph_names=glyph_names,
        )
        tt_font.save(outfile)
        return font

    @savers.register(linked=load_collection)
    def save_collection(
            fonts, outfile,
            funits_per_em:int=1024, strike_format:str='bit', flavour:str='otb',
            glyph_names:str=None,
        ):
        """
        Save bitmap fonts to a TrueType/OpenType Collection file.

        funits_per_em: number of design units (FUnits) per em-width (default 1024)
        strike_format: store as bitmaps aligned by 'byte', 'bit' (default) or as 'png' or 'tiff' (sbix only)
        flavour: type of sfnt resource: 'otb' (EBDT- or CBDT-based; default) or 'apple' (bdat- or sbix-based)
        glyph_names: tagger to set glyph names with. Default is no glyph names. Use 'tags' to use existing tags as glyph names.
        """
        _write_collection(
            fonts, outfile, funits_per_em, strike_format,
            flavour=flavour.lower(), glyph_names=glyph_names,
        )
        return fonts

    def check_fonttools():
        pass
else:
    def check_fonttools():
        raise FileFormatError(
            'Writing `sfnt` resources requires package `fontTools`, '
            'which is not available.'
        )
    save_sfnt = check_fonttools
    save_collection = check_fonttools

# sizes defined in EBSC table (following fontforge)
EBSC_SIZES = (*range(8, 26), 30, 32, 33, 40)


def _label_to_utf16(font, label, default):
    """Convert a glyph label to a UTF-16 codepoint, if possible; 0 if not."""
    try:
        utf16 = ord(font.get_glyph(label).char)
    except (KeyError, TypeError):
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
        usWeightClass=reverse_dict(WEIGHT_MAP).get(font.weight, 400),
        usWidthClass=reverse_dict(SETWIDTH_MAP).get(font.setwidth, 5),
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
        # strikeout metrics
        yStrikeoutSize=_to_funits(font.strikethrough_thickness),
        yStrikeoutPosition=_to_funits(font.strikethrough_ascent),
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
    # `name` table should only store x.y version numbers
    # while font.revision could be any string
    try:
        version_number = to_number(font.revision)
        extra = ''
    except ValueError:
        version_number = 0.0
        extra = f'; {font.revision}'
    props = dict(
        # 0
        copyright=font.copyright,
        # 1
        familyName=font.family,
        # 2
        styleName=font.subfamily,
        # 3
        uniqueFontIdentifier=(
            font.get_property('sfnt.font_id') or font.font_id
            or to_postscript_name(font.name)
        ),
        # 4
        fullName=font.name,
        # 5
        # must start with 'Version x.y'
        # but may contain additional info after `;`
        version=f'Version {version_number:1.1f}{extra}',
        # 6
        psName=(
            font.get_property('sfnt.postscript_name')
            or to_postscript_name(font.name)
        ),
        # 7
        trademark=font.get_property('sfnt.trademark'),
        # 8
        manufacturer=font.foundry,
        # 9
        designer=font.author,
        # 10
        description=font.get_property('sfnt.description'),
        # vendorURL (nameID 11)
        vendorURL=font.get_property('sfnt.vendor_url'),
        # designerURL (nameID 12)
        designerURL=font.get_property('sfnt.author_url'),
        # 13
        licenseDescription=font.notice,
        # licenseInfoURL (nameID 14)
        licenseInfoURL=font.get_property('sfnt.license_url'),
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
    props = {_k: _v for _k, _v in props.items() if _v is not None}
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
        ord(_g.char): _name
        for _name, _g in glyphs.items()
        # .notdef should not be mapped  in cmap
        if _g.char and _name != NOTDEF_NAME
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


def _create_empty_glyf_props(glyphs):
    """Create `glyf` table with empty glyphs."""
    # fontBuilder needs all these defined, even if empty
    # we'll remove it at the end as OTB files should not have any
    return {_name: fonttools.Glyph() for _name in glyphs}


def _determine_table_types(font, flavour):
    """Determine what type of tables to create."""
    if font.rgb_table or font.levels > 256:
        return 'CBDT', 'CBLC'
    elif flavour == 'apple':
        return 'bdat', 'bloc'
    return 'EBDT', 'EBLC'


def _setup_ebdt_table(fb, font, glyphs, strike_format, ebdt_name):
    """Build `bdat`, `EBDT` or `CBDT` bitmap data table."""
    ebdt = fonttools.newTable(ebdt_name)
    strike_format = strike_format.lower()
    if ebdt_name == 'CBDT':
        allowed_formats = ('bit', 'byte', 'png')
        ebdt.version = 3.0
    else:
        allowed_formats = ('bit', 'byte')
        ebdt.version = 2.0
    if strike_format not in allowed_formats:
        raise ValueError(
            f"For `{ebdt_name}` tables, `strike_format` must be one of "
            f"{allowed_formats}; not '{strike_format}'."
        )
    # create one strike - multiple strikes of different size are possible
    ebdt.strikeData = [{
        _name: convert_to_glyph(_g, fb, strike_format, font.rgb_table)
        for _name, _g in glyphs.items()
    }]
    fb.font[ebdt_name] = ebdt


_BITMAP_DATA_FORMATS = {
    # (metrics, strike_format): format
    ('small', 'byte'): fonttools.ebdt_bitmap_classes[1],
    ('small', 'bit'): fonttools.ebdt_bitmap_classes[2],
    # ('none', 'bit'): fonttools.ebdt_bitmap_classes[5],
    ('big', 'byte'): fonttools.ebdt_bitmap_classes[6],
    ('big', 'bit'): fonttools.ebdt_bitmap_classes[7],
    # ('small', 'component'): fonttools.ebdt_bitmap_classes[8],
    # ('big', 'component'): fonttools.ebdt_bitmap_classes[9],
    ('small', 'png'): fonttools.cbdt_bitmap_classes[17],
    ('big', 'png'): fonttools.cbdt_bitmap_classes[18],
    # ('none', 'png'): fonttools.cbdt_bitmap_classes[18],
}


def convert_to_glyph(glyph, fb, strike_format, rgb_table):
    """Create fontTools bitmap glyph."""
    if glyph.has_vertical_metrics():
        metrics = 'big'
    else:
        metrics = 'small'
    ebdt_bitmap = _BITMAP_DATA_FORMATS[metrics, strike_format]
    bmga = ebdt_bitmap(data=b'', ttFont=fb.font)
    if metrics == 'small':
        # horizontal metrics
        bmga.metrics = fonttools.SmallGlyphMetrics()
        bmga.metrics.height = glyph.height
        bmga.metrics.width = glyph.width
        bmga.metrics.BearingX = glyph.left_bearing
        bmga.metrics.BearingY = glyph.shift_up + glyph.height
        bmga.metrics.Advance = glyph.advance_width
    else:
        # 6, 7 - big glyph metrics
        bmga.metrics = fonttools.BigGlyphMetrics()
        bmga.metrics.height = glyph.height
        bmga.metrics.width = glyph.width
        bmga.metrics.horiBearingX = glyph.left_bearing
        bmga.metrics.horiBearingY = glyph.shift_up + glyph.height
        bmga.metrics.horiAdvance = glyph.advance_width
        bmga.metrics.vertBearingX = glyph.shift_left + glyph.width//2
        bmga.metrics.vertBearingY = glyph.top_bearing
        bmga.metrics.vertAdvance = glyph.advance_height
    if rgb_table:  # or font.levels > 256
        # could use P for <=256-colour
        img = glyph_to_image(glyph, image_mode='RGBA', inklevels=rgb_table)
        if strike_format == 'png':
            bytesio = BytesIO()
            img.save(bytesio, format='png')
            bmga.imageData = bytesio.getvalue()
        else:
            # no difference between bit or byte alignment for 32-bit strikes
            # per the spec, these are premultiplied RGBA so PIL's 'RGBa'
            bmga.imageData = img.convert('RGBa').tobytes()
    else:
        bmga.setRows(glyph.as_byterows(), bitDepth=(glyph.levels-1).bit_length())
    return bmga


def _setup_eblc_table(fb, font, glyphs, ebdt_name, eblc_name):
    """Build `EBLC` bitmap locations table."""
    eblc = fonttools.newTable(eblc_name)
    eblc.version = 3.0 if eblc_name == 'CBLC' else 2.0
    eblc.strikes = []
    for sdata in fb.font[ebdt_name].strikeData:
        # create strike
        strike = fonttools.Strike()
        hori = fonttools._create_sbit_line_metrics(
            ascender=font.ascent,
            descender=-font.descent,
            widthMax=font.max_width,
            minOriginSB=min((_g.left_bearing for _g in glyphs.values())),
            minAdvanceSB=min((_g.right_bearing for _g in glyphs.values())),
            maxBeforeBL=max((_g.height + _g.shift_up for _g in glyphs.values())),
            minAfterBL=min((_g.shift_up for _g in glyphs.values())),
        )
        if font.has_vertical_metrics():
            vert = fonttools._create_sbit_line_metrics(
                ascender=font.right_extent,
                descender=-font.left_extent,
                widthMax=max(
                    (_g.advance_height for _g in glyphs.values()),
                    default=0
                ),
                minOriginSB=min((_g.top_bearing for _g in glyphs.values())),
                minAdvanceSB=min((_g.bottom_bearing for _g in glyphs.values())),
                maxBeforeBL=max((
                    _g.shift_left + _g.width//2
                    for _g in glyphs.values()
                )),
                # ??
                minAfterBL=min((
                    -_g.shift_left - _g.width//2 + _g.width
                    for _g in glyphs.values()
                )),
            )
        else:
            vert = fonttools._create_sbit_line_metrics()
        strike.bitmapSizeTable = fonttools._create_bitmap_size_table(
            font.pixel_size, hori, vert,
            depth=32 if font.rgb_table else (font.levels-1).bit_length(),
        )
        strike.indexSubTables = fonttools._create_index_subtables(fb, sdata)
        # eblc strike locations are filled out by ebdt compiler
        # bitmap size table is not updated by fontTools, do it explicitly
        strike.bitmapSizeTable.numberOfIndexSubTables = len(strike.indexSubTables)
        eblc.strikes.append(strike)
    fb.font[eblc_name] = eblc


def _setup_sbix_table(fb, font, glyphs, strike_format):
    """Build `sbix` bitmap table."""
    strike_format = strike_format[:4].lower().ljust(4)
    if strike_format not in ('png ', 'tiff'):
        # sbix supports 'jpeg' but the glyph isn't preserved correctly
        raise ValueError(
            "For `sbix` tables, `strike_format` must be one of "
            f"('png', 'tiff'); not '{strike_format}'."
        )
    sbix = fonttools.newTable('sbix')
    sbix.version = 1
    # > Bit 0: Set to 1.
    # > Bit 1: Draw outlines.
    # > Bits 2 to 15: reserved (set to 0).
    sbix.flags = 1
    # create strike
    strike = fonttools.sbixStrike()
    strike.ppem = font.pixel_size
    strike.resolution = font.dpi[0]
    strike.glyphs = {}
    for name, glyph in glyphs.items():
        img = glyph_to_image(glyph, image_mode='RGBA', inklevels=font.rgb_table)
        bytesio = BytesIO()
        img.save(bytesio, format=strike_format.strip())
        sbix_glyph = fonttools.sbixGlyph(
            glyphName=name,
            # keep originOffsets as 0, use hmtx/vmtx instead
            graphicType=strike_format,
            imageData=bytesio.getvalue()
        )
        strike.glyphs[name] = sbix_glyph
    sbix.strikes = {0: strike}
    fb.font['sbix'] = sbix


def _prepare_for_sfnt(font, glyph_names):
    """Prepare monobit font for storing in sfnt."""
    # get char labels if we don't have them but we do have an encoding
    font = font.label(match_whitespace=False, match_graphical=False)
    default = font.get_default_glyph()
    # we need a name for each glyph to be able to store it
    # if glyph_names == 'tags', must be tagged already
    # otherwise, only glyphs without chars must have names
    if glyph_names != 'tags':
        font = font.label(tag_from=glyph_names or 'truetype', overwrite=True)
        # tag remaining glyphs based on index
        glyphs = (
            _g.modify(tag=f'glyph{_i}') if not _g.tags else _g
            for _i, _g in enumerate(font.glyphs)
        )
        font = font.modify(glyphs)
    else:
        # warn we're dropping glyphs without tags as not-storable
        dropped = tuple(_g for _g in font.glyphs if not _g.tags)
        if dropped:
            logging.warning(
                '%d untagged glyphs could not be stored', len(dropped)
            )
            logging.debug(
                'Dropped glyphs: %s',
                tuple(_g.get_labels()[0] for _g in dropped if _g.get_labels())
            )
    # cut back to glyph bounding boxes
    font = font.reduce()
    return font, default


def _create_sfnt(font, funits_per_em, strike_format, flavour, glyph_names):
    """Convert to a fontTools TTFont object."""
    # converter from pixels to design units
    # note that x and y ppem are equal - if not, fontforge rejects the bitmap
    def _to_funits(pixel_amount):
        return ceildiv(pixel_amount * funits_per_em, font.pixel_size)

    check_fonttools()
    font, default = _prepare_for_sfnt(font, glyph_names)
    # get the storable glyphs
    glyphnames = (NOTDEF_NAME, *(_t.value for _t in font.get_tags()))
    glyphs = {
        _name: font.get_glyph(tag=_name, missing=default)
        for _name in glyphnames
    }
    # build font object
    fb = fonttools.FontBuilder(funits_per_em, isTTF=True)
    fb.setupGlyphOrder(glyphnames)
    fb.setupCharacterMap(_convert_to_cmap_props(glyphs))
    fb.setupGlyf(_create_empty_glyf_props(glyphs))
    ebdt_name, eblc_name = _determine_table_types(font, flavour)
    if font.rgb_table and flavour == 'apple':
        _setup_sbix_table(fb, font, glyphs, strike_format)
    else:
        _setup_ebdt_table(fb, font, glyphs, strike_format, ebdt_name)
        _setup_eblc_table(fb, font, glyphs, ebdt_name, eblc_name)
    if flavour == 'ms':
        fonttools._setup_ebsc_table(fb, {font.pixel_size: EBSC_SIZES})
    if flavour != 'apple':
        fb.setupHorizontalMetrics(_convert_to_hmtx_props(glyphs, _to_funits))
        fb.setupHorizontalHeader(**_convert_to_hhea_props(font, _to_funits))
        # check for vertical metrics, include `vhea` and `vmtx` if present
        if font.has_vertical_metrics():
            fb.setupVerticalMetrics(_convert_to_vmtx_props(glyphs, _to_funits))
            fb.setupVerticalHeader(**_convert_to_vhea_props(font, _to_funits))
    fb.setupNameTable(_convert_to_name_props(font))
    if flavour != 'apple':
        fb.setupOS2(**_convert_to_os_2_props(font, _to_funits))
    # for otb: version-3 table, defines no names
    fb.setupPost(
        keepGlyphNames=bool(glyph_names),
        isFixedPitch=font.spacing in ('monospace', 'character-cell'),
        # descriptive italic angle, counter-clockwise degrees from vertical
        #italicAngle
        # negative is below baseline
        underlinePosition=-_to_funits(font.underline_descent),
        underlineThickness=_to_funits(font.underline_thickness),
    )
    fonttools._setup_kern_table(fb, **_convert_to_kern_props(font, glyphs, _to_funits))
    # bitmap-only formats
    if flavour == 'otb':
        # OTB output
        fb.font.recalcBBoxes = False
        # ensure we get an empty glyf table
        fb.font['glyf'].compile = lambda self: b''
        # loca table with null for every glyph
        fb.font['loca'].compile = lambda self: bytes(len(glyphnames)*2+2)
        # del `loca` in ms file? fontforge does.
    elif flavour == 'apple':
        fb.font.recalcBBoxes = False
        # glyf, loca tables are usually omitted in apple sbit fonts,
        # but must be present in sbix fonts for hmtx/vmtx to be used
        if not font.rgb_table:
            # bhed is used to indicate glyf is not present
            fb.font['bhed'] = fb.font['head']
            del fb.font['head']
            del fb.font['glyf']
            del fb.font['loca']
    return fb.font

def _write_collection(fonts, outfile, funits_per_em, strike_format, flavour, glyph_names):
    """Convert to TrueType collection and write out."""
    check_fonttools()
    ttc = fonttools.TTCollection()
    ttc.fonts = tuple(
        _create_sfnt(_font, funits_per_em, strike_format, flavour, glyph_names)
        for _font in fonts
    )
    ttc.save(outfile)
