from importlib.resources import files
from pathlib import Path

try:
    from fontTools import ttLib
    loaded = True
except ImportError:
    ttLib = None
    loaded = False

from ....magic import FileFormatError


def register_extensions():
    """Register extension tables"""
    for file in files(__name__).iterdir():
        name = Path(file.name).stem
        if name.startswith('__'):
            continue
        tag = name.replace('_', '')
        ttLib.registerCustomTableClass(tag, f'{__package__}.{name}')


def ebdt_monkey_patch():
    """Monkey patch to fix a bug in fontTools (as of 4.39.3)"""
    from fontTools.ttLib.tables import E_B_D_T_
    from fontTools.ttLib.tables.E_B_D_T_ import bytesjoin, byteord, bytechr

    def _reverseBytes(data):
        if isinstance(data, bytes) and len(data) != 1:
            # this is where the bug was
            return bytesjoin(map(_reverseBytes, data))
        byte = byteord(data)
        result = 0
        for i in range(8):
            result = result << 1
            result |= byte & 1
            byte = byte >> 1
        return bytechr(result)

    E_B_D_T_._reverseBytes = _reverseBytes


if not loaded:
    def check_fonttools(*args, **kwargs):
        raise FileFormatError(
            'Parsing `sfnt` resources requires package `fontTools`, '
            'which is not available.'
        )
else:
    def check_fonttools(*args, **kwargs):
        pass

    ebdt_monkey_patch()
    register_extensions()

    from fontTools.ttLib import TTLibError
    from fontTools.ttLib.ttFont import TTFont
    from fontTools.ttLib.ttCollection import TTCollection

    from fontTools.ttLib import newTable
    from fontTools.fontBuilder import FontBuilder


    # `EBLC` builder

    from fontTools.ttLib.tables.E_B_L_C_ import (
        Strike, BitmapSizeTable, eblc_index_sub_table_3, SbitLineMetrics
    )

    def _create_index_subtables(fb, sdata):
        """Create the IndexSubTables"""
        imageformats = {_n: _g.getFormat() for _n, _g in sdata.items()}
        istables = []
        last_format = None
        for name, format in imageformats.items():
            if format !=  last_format:
                # create index sub table
                ist = eblc_index_sub_table_3(data=b'', ttFont=fb.font)
                ist.indexFormat = 3
                ist.imageFormat = format
                ist.names = []
                istables.append(ist)
            ist.names.append(name)
            last_format = format
        return istables


    def _create_sbit_line_metrics(**kwargs):
        """Create SbitLineMetrics object."""
        sblm = SbitLineMetrics()
        sblm.ascender = 0
        sblm.descender = 0
        sblm.widthMax = 0
        # defaults for caret metrics
        sblm.caretSlopeNumerator = 0
        sblm.caretSlopeDenominator = 1
        sblm.caretOffset = 0
        # aggregate glyph metrics
        # based on pictures in spec
        # note that formulas in spec make no sense
        # min of horiBearingX
        # min of vertBearingY
        sblm.minOriginSB = 0
        # min of horiAdvance - (horiBearingX + width)
        # == minimum right side bearing
        # min of vertAdvance - (vertBearingY + height)
        sblm.minAdvanceSB = 0
        # max of horiBearingY
        # max of vertBearingX
        sblm.maxBeforeBL = 0
        # min of horiBearingY - height
        # min of vertBearingX - width
        sblm.minAfterBL = 0
        sblm.pad1 = 0
        sblm.pad2 = 0
        sblm.__dict__.update(kwargs)
        return sblm


    def _create_bitmap_size_table(ppem, hori, vert):
        """Create the BitmapSize record."""
        # this is not contructed by any compile() method as far as I can see
        # > The line metrics are not used directly by the rasterizer, but are available to applications that want to parse the EBLC table.
        bst = BitmapSizeTable()
        bst.colorRef = 0
        bst.flags = 0x01  # hori | 0x02 for vert
        bst.bitDepth = 1
        # ppem need to be the same both ways for fontforge
        bst.ppemX = ppem
        bst.ppemY = ppem
        # build horizontal line metrics
        bst.hori = hori
        bst.vert = vert
        return bst


    # `kern` builder

    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

    def _setup_kern_table(fb, version=0, kernTables=()):
        """Build `kern` table."""
        kern_table = newTable('kern')
        kern_table.version = version
        kern_table.kernTables = []
        for subdict in kernTables:
            subtable = KernTable_format_0(apple=version==1.0)
            subtable.__dict__.update(subdict)
            kern_table.kernTables.append(subtable)
        if any(_k.kernTable for _k in kern_table.kernTables):
            fb.font['kern'] = kern_table


    # `glyf`

    from fontTools.ttLib.tables._g_l_y_f import Glyph


    # `EBDT`

    from fontTools.ttLib.tables.E_B_D_T_ import ebdt_bitmap_classes
    from fontTools.ttLib.tables.BitmapGlyphMetrics import (
        SmallGlyphMetrics, BigGlyphMetrics
    )

    # `EBSC`

    from .E_B_S_C_ import BitmapScaleTable

    def _setup_ebsc_table(fb, scaler_mapping):
        # EBSC should only be used with EBDT, EBLC tables
        # not the apple ones
        fb.font['EBSC'] = ebsc = newTable('EBSC')
        ebsc.version = 2.0
        for to_size, from_sizes in scaler_mapping.items():
            for strike in fb.font['EBLC'].strikes:
                if strike.bitmapSizeTable.ppemY == to_size:
                    break
            else:
                # no strike with to_size found, ignore
                continue
            ebsc.bitmapScaleTables = [
                BitmapScaleTable(
                    hori=strike.bitmapSizeTable.hori,
                    vert=strike.bitmapSizeTable.vert,
                    ppemX=size,
                    ppemY=size,
                    substitutePpemX=to_size,
                    substitutePpemY=to_size,
                )
                for size in from_sizes
            ]
        ebsc.numSizes = len(ebsc.bitmapScaleTables)
