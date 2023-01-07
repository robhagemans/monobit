"""
monobit.formats - font format converter plugins

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from importlib import import_module
from pathlib import Path
from pkg_resources import resource_listdir


# import all modules in this directory into module namespace
globals().update({
    Path(_file).stem: import_module('.' + Path(_file).stem, __package__)
    for _file in resource_listdir(__name__, '')
    if not _file.startswith('_')
})
