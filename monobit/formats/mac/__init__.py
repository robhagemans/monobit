"""
monobit.formats.mac - Mac OS fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from io import BytesIO

from ...storage import loaders, savers

from .dfont import _parse_mac_resource, _write_dfont
from .nfnt import _extract_nfnt, _convert_nfnt, _create_nfnt
from .lisa import _load_lisa
from .iigs import _load_iigs, _save_iigs

from ..sfnt import save_sfnt, MAC_ENCODING
from ...properties import Props, reverse_dict


@loaders.register(
    name='mac',
    # the magic is optional - a 'maybe magic'
    magic=(b'\0\0\1\0\0',),
    patterns=('*.dfont', '*.suit', '*.rsrc',),
)
def load_mac_dfont(instream):
    """Load font from MacOS resource fork or data-fork resource."""
    data = instream.read()
    return _parse_mac_resource(data)


def _hash_to_id(family_name, script):
    """Generate a resource id based on the font family name."""
    # see https://github.com/zoltan-dulac/fondu/blob/master/ufond.c
    low = 128
    high = 0x4000
    hash = 0
    if script:
        low = 0x4000 + (script-1)*0x200;
        high = low + 0x200;
    for ch in family_name:
        temp = (hash>>28) & 0xf
        hash = (hash<<4) | temp
        hash ^= ord(ch) - 0x20
    hash %= (high-low)
    hash += low
    return hash


@savers.register(linked=load_mac_dfont)
def save_mac_dfont(fonts, outstream, resource_type='sfnt', family_id=None):
    """Save font to MacOS resource fork or data-fork resource.

    resource_type: type of resource to store font in. One of `sfnt`, `NFNT`, `FONT`.
    family_id: font family-id to use. Default: calculate based on encoding and hash of font family name.
    """
    if resource_type != 'sfnt':
        raise ValueError('Only saving to sfnt resource currently supported')
    sfnt_io = BytesIO()
    result = save_sfnt(fonts, sfnt_io)
    font, *_ = fonts
    if family_id is None:
        script_code = reverse_dict(MAC_ENCODING).get(font.encoding, 0)
        family_id = _hash_to_id(font.family, script=script_code)
    resources = [
        Props(type=b'sfnt', id=family_id, name='', data=sfnt_io.getvalue())
    ]
    _write_dfont(outstream, resources)
    return result


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
