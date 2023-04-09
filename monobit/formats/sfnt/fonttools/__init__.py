from importlib.resources import files
from pathlib import Path

try:
    from fontTools import ttLib
except ImportError:
    ttLib = None

from ....magic import FileFormatError


if ttLib:
    for file in files(__name__).iterdir():
        name = Path(file.name).stem
        if name.startswith('__'):
            continue
        tag = name.replace('_', '')
        ttLib.registerCustomTableClass(tag, f'{__package__}.{name}')

    def check_fonttools(*args, **kwargs): pass
else:
    def check_fonttools(*args, **kwargs):
        raise FileFormatError(
            'Parsing `sfnt` resources requires package `fontTools`, '
            'which is not available.'
        )
