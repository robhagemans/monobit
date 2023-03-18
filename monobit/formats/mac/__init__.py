"""
monobit.formats.mac - Mac OS fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...storage import loaders, savers

from .dfont import _parse_mac_resource
from .nfnt import _extract_nfnt, _convert_nfnt, _create_nfnt
from .lisa import _load_lisa
from .iigs import _load_iigs, _save_iigs


@loaders.register(
    name='mac',
    # the magic is optional - a 'maybe magic'
    magic=(b'\0\0\1\0\0',),
    patterns=('*.dfont', '*.suit', '*.rsrc',),
)
def load_mac_dfont(instream):
    """Load font from a MacOS suitcase."""
    data = instream.read()
    return _parse_mac_resource(data)


@loaders.register(
    name='nfnt',
    # \x90\0 is not a formal signature, but the most common set of FONT_TYPE flags
    # the \x80 sigs are LISA compressed NFNTs
    magic=(b'\x90\0', b'\xb0\0', b'\x90\x80', b'\xb0\x80'),
    patterns=('*.f',),
)
def load_nfnt(instream, offset:int=0):
    """
    Load font from a bare FONT/NFNT resource.

    offset: starting offset in bytes of the NFNT record in the file (default 0)
    """
    instream.seek(offset)
    data = instream.read()
    fontdata = _extract_nfnt(data, 0)
    return _convert_nfnt({}, **fontdata)


@loaders.register(name='lisa')
def load_lisa(instream):
    """Load a LISA font library."""
    return _load_lisa(instream)


@loaders.register(
    name='iigs',
    patterns=('*.fon',),
)
def load_iigs(instream):
    """Load a IIgs font."""
    return _load_iigs(instream)


@savers.register(linked=load_iigs)
def save_iigs(fonts, outstream, version:int=None):
    """
    Write font to a IIgs font file.

    version: IIgs font format version (0x101, 0x105). Default: 0x101 unless needed for bitmap size.
    """
    if len(fonts) > 1:
        logging.warning('IIgs font file can only store one font.')
    font = fonts[0]
    _save_iigs(outstream, font, version=version)


@savers.register(linked=load_nfnt)
def save_nfnt(fonts, outstream):
    """Write font to a bare FONT/NFNT resource."""
    if len(fonts) > 1:
        logging.warning('NFNT resource can only store one font.')
    font = fonts[0]
    data, _, _ = _create_nfnt(font, endian='big', ndescent_is_high=True)
    outstream.write(data)
