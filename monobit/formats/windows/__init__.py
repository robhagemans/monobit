"""
monobit.formats.windows - Windows FON and FNT files

`monobit.formats.windows` is copyright 2019--2023 Rob Hagemans
`mkwinfont` is copyright 2001 Simon Tatham. All rights reserved.
`dewinfont` is copyright 2001,2017 Simon Tatham. All rights reserved.

See `LICENSE.md` in this package's directory.
"""

import logging

from ...storage import loaders, savers
from ...magic import FileFormatError
from .fnt import create_fnt
from .fnt import convert_win_fnt_resource, FNT_MAGIC_1, FNT_MAGIC_2, FNT_MAGIC_3

# used by other formats
from .fnt import WEIGHT_MAP, WEIGHT_REVERSE_MAP, CHARSET_MAP, CHARSET_REVERSE_MAP


@loaders.register(
    name='win',
    magic=(FNT_MAGIC_1, FNT_MAGIC_2, FNT_MAGIC_3),
    patterns=('*.fnt',),
)
def load_win_fnt(instream):
    """Load font from a Windows .FNT resource."""
    resource = instream.read()
    font = convert_win_fnt_resource(resource)
    return font

@savers.register(linked=load_win_fnt)
def save_win_fnt(fonts, outstream, version:int=2, vector:bool=False):
    """
    Save font to a Windows .FNT resource.

    version: Windows font format version (default 2)
    vector: output a vector font (if the input font has stroke paths defined; default False)
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to Windows font resource.')
    font = fonts[0]
    outstream.write(create_fnt(font, version*0x100, vector))
    return font
