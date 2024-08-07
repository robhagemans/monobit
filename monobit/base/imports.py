"""
monobit.base.imports - supporting functionds for dynamic imports

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
from importlib import import_module
from pathlib import Path
from importlib.resources import files


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
            _file.name.endswith('.py')
            and not _file.name.startswith('_')
            and not _file.name.startswith('.')
        )
    })


def safe_import(module_name, name=None):
    """Wrapper for importing external modules and dealing with their errors."""
    item = None
    try:
        module = import_module(module_name)
    except ImportError as e:
        logging.debug('Could not import module `%s`: %s', module_name, e)
    except Exception as e:
        logging.warning('Error while importing module `%s`: %s', module_name, e)
    else:
        if name:
            item = getattr(module, name)
        else:
            item = module
    return item
