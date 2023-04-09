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
        if len(data) != 1:
            # this is where the bug was
            return bytesjoin(map(_reverseBytes, map(chr, data)))
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
