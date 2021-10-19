"""
monobit.plugins - plugin registry

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import gzip
import logging
from pathlib import Path
from contextlib import contextmanager

from ..base import DEFAULT_FORMAT
from ..scripting import scriptable
from ..streams import MagicRegistry


class PluginRegistry(MagicRegistry):
    """Loader/Saver plugin registry."""

    def get_plugin(self, file=None, format='', do_open=False):
        """
        Get loader/saver function for this format.
        infile must be a Stream or empty
        """
        plugin = None
        if not format:
            plugin = self.identify(file, do_open=do_open)
        if not plugin:
            plugin = self[format or DEFAULT_FORMAT]
        return plugin

    def register(self, *formats, magic=(), name='', linked=None):
        """
        Decorator to register font loader/saver.
            *formats: extensions covered by registered function
            magic: magic sequences cobvered by the plugin (no effect for savers)
            name: name of the format
            linked: loader/saver linked to saver/loader
        """
        register_magic = super().register

        def _decorator(original_func):
            # set script arguments
            _func = scriptable(original_func)
            # register plugin
            if linked:
                linked.linked = _func
                _func.name = name or linked.name
                _func.formats = formats or linked.formats
                _func.magic = magic or linked.magic
            else:
                _func.name = name
                _func.linked = linked
                _func.formats = formats
                _func.magic = magic
            # register magic sequences
            register_magic(*_func.formats, magic=_func.magic)(_func)
            return _func

        return _decorator


loaders = PluginRegistry()
savers = PluginRegistry()
