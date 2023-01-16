"""
monobit.formats.windows - Windows FON and FNT files

`monobit.formats.windows` is copyright 2019--2023 Rob Hagemans
`mkwinfont` is copyright 2001 Simon Tatham. All rights reserved.
`dewinfont` is copyright 2001,2017 Simon Tatham. All rights reserved.

See `LICENSE.md` in this package's directory.
"""

from ...storage import loaders, savers
from .fnt import parse_fnt, create_fnt
from .ne import _parse_ne, _create_fon
from .pe import _parse_pe
from .mz import _MZ_HEADER

# used by other formats
from .fnt import _normalise_metrics, CHARSET_MAP, CHARSET_REVERSE_MAP


@loaders.register(
    #'fnt',
    magic=(b'\0\x01', b'\0\x02', b'\0\x03'),
    name='win-fnt',
)
def load_win_fnt(instream, where=None):
    """Load font from a Windows .FNT resource."""
    font = parse_fnt(instream.read())
    return font

@savers.register(linked=load_win_fnt)
def save_win_fnt(fonts, outstream, where=None, version:int=2):
    """
    Save font to a Windows .FNT resource.

    version: Windows font format version
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to Windows font resource.')
    font = fonts[0]
    outstream.write(create_fnt(font, version*0x100))
    return font


@loaders.register(
    'fon',
    magic=(b'MZ',),
    name='win-fon',
)
def load_win_fon(instream, where=None):
    """Load fonts from a Windows .FON container."""
    data = instream.read()
    mz_header = _MZ_HEADER.from_bytes(data)
    if mz_header.magic not in (b'MZ', b'ZM'):
        raise FileFormatError('MZ signature not found. Not a Windows .FON file')
    ne_magic = data[mz_header.ne_offset:mz_header.ne_offset+2]
    if ne_magic == b'NE':
        fonts = _parse_ne(data, mz_header.ne_offset)
    elif ne_magic == b'PE':
        # PE magic should be padded by \0\0 but I'll believe it at this stage
        fonts = _parse_pe(data, mz_header.ne_offset)
    else:
        raise FileFormatError(
            'Executable signature is `{}`, not NE or PE. Not a Windows .FON file'.format(
                ne_magic.decode('latin-1', 'replace')
            )
        )
    fonts = [
        font.modify(
            source_format=font.source_format+' ({} FON container)'.format(ne_magic.decode('ascii'))
        )
        for font in fonts
    ]
    return fonts

@savers.register(linked=load_win_fon)
def save_win_fon(fonts, outstream, where=None, version:int=2):
    """
    Save fonts to a Windows .FON container.

    version: Windows font format version
    """
    outstream.write(_create_fon(fonts, version*0x100))
