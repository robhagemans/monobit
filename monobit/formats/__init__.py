"""
monobit.codecs - font format converters

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from importlib import import_module
from pathlib import Path
from pkg_resources import resource_listdir
from types import SimpleNamespace

from ._base import open_location, loaders, savers


# load all modules in this directory into converters namespace
converters = SimpleNamespace(**{
    Path(_file).stem: import_module('.' + Path(_file).stem, __package__)
    for _file in resource_listdir(__name__, '')
    if not _file.startswith('_')
})
