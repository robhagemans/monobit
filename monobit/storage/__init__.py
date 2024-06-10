"""
monobit.storage - recognise files, traverse filesystems, load and save fonts

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import loaders, savers
from .converters import load, save
from .magic import FileFormatError, Regex, Glob, Magic
from .streams import Stream, KeepOpen, get_stringio, get_bytesio
from . import streams

# from .base import (
#     loaders, savers, wrappers, containers, container_loaders, container_savers
# )

# ensure plugins get loaded
from . import containers as _containers
from . import formats as _formats
from . import wrappers as _wrappers
