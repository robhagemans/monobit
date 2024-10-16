"""
monobit.storage.fontformats.apple.fctb - Mac `fctb` colour table resources

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from monobit.base.struct import big_endian as be
from monobit.base import RGBTable
from monobit.render import create_gradient


# https://vintageapple.org/inside_o/pdf/Inside_Macintosh_Volume_V_1986.pdf
# p V-135
_COLOR_TABLE = be.Struct(
    # > unique identifier from table
    # > minimum seed value >= 1024
    ctSeed='uint32',
    # > high bit is set for gDevice, clear for a pixMap
    # > significant for gDevices only; otherwise 0
    ctFlags='uint16',
    # > number of entries in table -1
    ctSize='uint16',
)

_COLOR_SPEC = be.Struct(
    # > color representation
    value='uint16',
    # > the components in an RGBTable are left-justified rather than right-justified in a word
    # > [...] extract the appropriate number of bits from the high order side of the component
    red='uint16',
    green='uint16',
    blue='uint16',
)


def extract_fctb(data, offset):
    """Extract colour table from an fctb resource."""
    ct_header = _COLOR_TABLE.from_bytes(data, offset)
    cspecs = (_COLOR_SPEC * (ct_header.ctSize+1)).from_bytes(data, offset)
    return dict(color_table=ct_header, color_specs=cspecs)


def convert_fctb(color_table, color_specs, levels):
    """Convert fctb color spec to RGBTable."""
    if not color_specs:
        return None
    # use leftmost 8 bits of the 16-bit components
    color_dict = {
        _c.value: (_c.red >> 8, _c.green >> 8, _c.blue >> 8)
        for _c in color_specs
    }
    # fill out colour table with greyscale levels (as per V-183)
    levels_needed = levels - len(color_specs)
    # use a reverse gradient so we can pop from the tail
    greyscale = (
        create_gradient((255, 255, 255), (0, 0, 0), levels_needed)
    )
    # this should exactly exhaust greyscale
    rgb_table = []
    for i in range(levels):
        try:
            rgb = color_dict[i]
        except KeyError:
            rgb = greyscale.pop()
        rgb_table.append(rgb)
    return RGBTable(rgb_table)


def convert_to_fctb(rgb_table):
    """Convert RGBTable to fctb."""
    color_specs = (_COLOR_SPEC * len(rgb_table))(*(
        _COLOR_SPEC(value=_i, red=_c.r << 8, green=_c.g << 8, blue=_c.b << 8)
        for _i, _c in enumerate(rgb_table)
    ))
    # unclear how seed should be chosen
    color_table = _COLOR_TABLE(ctSeed=1024, ctSize=len(rgb_table))
    return dict(color_table=color_table, color_specs=color_specs)


def fctb_data_to_bytes(fctb_data):
    """Convert fctb to bytes."""
    return bytes(fctb_data['color_table']) + bytes(fctb_data['color_specs'])
