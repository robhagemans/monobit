from importlib.resources import files
from pathlib import Path

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
    for file in files(__name__).iterdir():
        name = Path(file.name).stem
        if name.startswith('__'):
            continue
        tag = name.replace('_', '')
        ttLib.registerCustomTableClass(tag, f'{__package__}.{name}')
