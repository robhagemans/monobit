"""
monobit.base - supporting classes

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .basetypes import *
from .properties import reverse_dict, extend_string, Props
from .cachedprops import HasProps, checked_property, writable_property
from . import struct
from . import binary
from . import blocks


###############################################################################
# plugin module importer

import sys
from importlib import import_module
from pathlib import Path
from importlib.resources import files

def import_all(module_name):
    module = sys.modules[module_name]
    vars(module).update({
        Path(_file).stem: import_module('.' + Path(_file.name).stem, module.__package__)
        for _file in files(module_name).iterdir()
        if not _file.name.startswith('_') and not _file.name.startswith('.')
    })
