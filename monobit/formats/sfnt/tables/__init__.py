try:
    from fontTools import ttLib
except ImportError:
    ttLib = None

from ....magic import FileFormatError


def _no_fonttools():
    raise FileFormatError(
        'Parsing `sfnt` resources requires package `fontTools`, '
        'which is not available.'
    )

def _init_fonttools():
    """Register extension classes for fontTools."""
    if not ttLib:
        _no_fonttools()


if ttLib:
    ttLib.registerCustomTableClass('bhed', 'monobit.formats.sfnt.tables._b_h_e_d')
    ttLib.registerCustomTableClass('bloc', 'monobit.formats.sfnt.tables._b_l_o_c')
    ttLib.registerCustomTableClass('bdat', 'monobit.formats.sfnt.tables._b_d_a_t')
    ttLib.registerCustomTableClass('EBSC', 'monobit.formats.sfnt.tables.E_B_S_C_')
