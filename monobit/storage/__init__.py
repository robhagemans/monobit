"""
monobit.storage - recognise files, traverse filesystems, load and save fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .converters import loaders, savers, load, save, load_stream, save_stream, load_all, save_all
from .magic import FileFormatError, Regex, Glob, Magic
from .streams import Stream, KeepOpen, DirectoryStream, get_stringio, get_bytesio
from . import streams

# ensure plugins get loaded
from . import containers as _containers
from . import formats as _formats
from . import wrappers as _wrappers
