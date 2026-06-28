"""
monobit.base.imports - supporting functionds for dynamic imports

(c) 2024--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
from pathlib import Path
from importlib import import_module
from importlib.resources import files
from importlib.util import find_spec
from functools import cached_property


def import_all(module_name):
    """Import all plugins in directory."""
    module = sys.modules[module_name]
    vars(module).update({
        Path(_file).stem: import_module(
            '.' + Path(_file.name).stem,
            module.__package__
        )
        for _file in files(module_name).iterdir()
        if (
            not _file.name.startswith('_')
            and not _file.name.startswith('.')
        )
    })


def safe_import(module_name):
    """Wrapper for importing external modules and dealing with their errors."""
    return LazyModule(module_name)


class LazyModule:
    """Lazy-loading wrapper for modules."""

    def __init__(self, name, available=True):
        self._name = name
        self._module = None

    @cached_property
    def _available(self):
        # check for availability without triggering an import
        available = find_spec(self._name) is not None
        if not available:
            logging.debug('Could not find module `%s`.', self._name)
        return available

    def __bool__(self):
        return self._available

    def __getattr__(self, attr):
        if not self._available:
            raise AttributeError(attr)
        if self._module is None:
            # what if this raises an error/ we can't find out without trying
            # would need to replace
            try:
                self._module = import_module(self._name)
            except Exception as e:
                logging.warning('Error while importing module `%s`: %s', module_name, e)
                self._available = False
                raise AttributeError(attr)
        return getattr(self._module, attr)
