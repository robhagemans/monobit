"""
monobit.formats.mac - Mac OS fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ...storage import loaders, savers

from .dfont import _parse_mac_resource
from .nfnt import _extract_nfnt, _convert_nfnt


# the magic is optional - a 'maybe magic'
# .rsrc is what we use as a 'filename' for resources inside containers
@loaders.register('dfont', 'suit', 'rsrc', name='mac', magic=(b'\0\0\1\0\0',))
def load_mac_dfont(instream, where=None):
    """Load font from a MacOS suitcase."""
    data = instream.read()
    return _parse_mac_resource(data)

# \x90\0 is not a formal signature, but the most common set of FONT_TYPE flags
@loaders.register('nfnt', name='nfnt', magic=(b'\x90\0',))
def load_nfnt(instream, where=None, offset:int=0):
    """
    Load font from a bare FONT/NFNT resource.

    offset: starting offset in bytes of the NFNT record in the file (default 0)
    """
    instream.seek(offset)
    data = instream.read()
    fontdata = _extract_nfnt(data, 0)
    return _convert_nfnt({}, **fontdata)
