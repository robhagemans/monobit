"""
monobit.formats - font format converter plugins

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from importlib import import_module
from pathlib import Path
from importlib.resources import files


# import all modules in this directory into module namespace
globals().update({
    Path(_file).stem: import_module('.' + Path(_file.name).stem, __package__)
    for _file in files(__name__).iterdir()
    if not _file.name.startswith('_')
})
