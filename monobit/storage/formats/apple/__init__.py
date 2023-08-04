"""
monobit.storage.formats.apple - Mac OS and other Apple font formats

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers
from monobit.encoding import EncodingName
from monobit.base import NOT_SET
from monobit.base import import_all

import_all(__name__)

from .dfont import parse_resource_fork, save_dfont
from .nfnt import extract_nfnt, convert_nfnt, create_nfnt
from .lisa import _load_lisa
from .iigs import _load_iigs, _save_iigs


@loaders.register(
    name='mac',
    # the magic is optional - a 'maybe magic'
    magic=(b'\0\0\1\0\0',),
    patterns=('*.dfont', '*.suit', '*.rsrc',),
)
def load_mac_dfont(instream):
    """Load font from MacOS resource fork or data-fork resource."""
    data = instream.read()
    return parse_resource_fork(data)


@savers.register(linked=load_mac_dfont)
def save_mac_dfont(
        fonts, outstream, resource_type:str='NFNT', family_id:int=None,
        resample_encoding:EncodingName=NOT_SET,
    ):
    """Save font to MacOS resource fork or data-fork resource.

    resource_type: type of resource to store font in. One of `sfnt`, `NFNT`.
    resample_encoding: encoding to use for NFNT resources. Must be one of the `mac-` encodings. Default: use font's encoding.
    """
    save_dfont(fonts, outstream, resource_type, resample_encoding)


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
    fontdata = extract_nfnt(data, 0)
    return convert_nfnt({}, **fontdata)


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
def save_iigs(
        fonts, outstream, version:int=None, resample_encoding:EncodingName=NOT_SET,
    ):
    """
    Write font to a IIgs font file.

    version: IIgs font format version (0x101, 0x105). Default: 0x101 unless needed for bitmap size.
    resample_encoding: encoding to use for NFNT resources. Must be one of the `mac-` encodings. Default: use font's encoding.
    """
    if len(fonts) > 1:
        logging.warning('IIgs font file can only store one font.')
    font = fonts[0]
    _save_iigs(
        outstream, font, version=version, resample_encoding=resample_encoding
    )


@savers.register(linked=load_nfnt)
def save_nfnt(
        fonts, outstream,
        create_width_table:bool=True,
        create_height_table:bool=False,
        resample_encoding:EncodingName=NOT_SET,
    ):
    """
    Write font to a bare FONT/NFNT resource.

    create_width_table: include a fractional glyph-width table in the resource (default: True)
    create_height_table: include an image-height table in the resource (default: False)
    resample_encoding: encoding to use for NFNT resources. Must be one of the `mac-` encodings. Default: use font's encoding.
    """
    if len(fonts) > 1:
        logging.warning('NFNT resource can only store one font.')
    font = fonts[0]
    data, _, _ = create_nfnt(
        font, endian='big', ndescent_is_high=True,
        create_width_table=create_width_table,
        create_height_table=create_height_table,
        resample_encoding=resample_encoding,
    )
    outstream.write(data)
