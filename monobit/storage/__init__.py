"""
monobit.storage - recognise files, traverse filesystems, load and save fonts

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import loaders, savers
from .fontfiles import load, save
from .magic import Regex, Glob, Magic
from .streams import Stream, KeepOpen, get_stringio, get_bytesio
from . import streams
