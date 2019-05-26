"""
monobit.typeface - representation of collection of fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from os.path import basename
from functools import wraps

from .base import VERSION, DEFAULT_FORMAT, scriptable, ensure_stream, zip_streams
from .font import Font


class Typeface:
    """Holds one or more potentially unrelated fonts."""

    _loaders = {}
    _savers = {}
    _encodings = {}

    def __init__(self, fonts=()):
        """Create typeface from sequence of fonts."""
        self._fonts = tuple(fonts)

    @classmethod
    def load(cls, infile:str, format:str='', **kwargs):
        """Read new font from file."""
        if isinstance(infile, bytes):
            infile = infile.decode('ascii')
        if not format:
            format = DEFAULT_FORMAT
            # if filename given, try to use it to infer format
            if isinstance(infile, str):
                try:
                    _, format = infile.rsplit('.', 1)
                except ValueError:
                    pass
        format = format.lower()
        try:
            loader = cls._loaders[format]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format))
        return loader(infile, **kwargs)

    @scriptable
    def save(self, outfile:str, format:str='', **kwargs):
        """Write to file, return unchanged."""
        if isinstance(outfile, bytes):
            outfile = outfile.decode('ascii')
        if not format:
            format = DEFAULT_FORMAT
            # if filename given, try to use it to infer format
            if isinstance(outfile, str):
                try:
                    _, format = outfile.rsplit('.', 1)
                except ValueError:
                    pass
        format = format.lower()
        try:
            saver = self._savers[format]
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))
        return saver(self, outfile, **kwargs)

    @classmethod
    def loads(cls, *formats, name=None, encoding='utf-8-sig'):
        """Decorator to register font loader."""
        if name is None:
            name = formats[0]

        def _load_decorator(load):
            # stream input wrapper
            @wraps(load)
            def _load_func(infile, **kwargs):
                with ensure_stream(infile, 'r', encoding=encoding) as instream:
                    typeface = load(instream, **kwargs)
                    # set source-name and source-format
                    fonts = []
                    for font in typeface._fonts:
                        new_props = {
                            'converter': 'monobit v{}'.format(VERSION),
                        }
                        if not font.source_name:
                            new_props['source-name'] = basename(instream.name)
                        if not font.source_format:
                            new_props['source-format'] = name
                        fonts.append(font.set_properties(**new_props))
                    return Typeface(fonts)
            # register loader
            for format in formats:
                cls._loaders[format.lower()] = _load_func
            return _load_func

        return _load_decorator

    @classmethod
    def saves(cls, *formats, encoding='utf-8', multi=True):
        """Decorator to register font saver."""

        def _save_decorator(save):
            # stream output wrapper
            @wraps(save)
            def _save_func(typeface, outfile, **kwargs):
                if multi:
                    with ensure_stream(outfile, 'w', encoding=encoding) as outstream:
                        save(typeface, outstream, **kwargs)
                else:
                    for font, stream in zip_streams(outfile, typeface._fonts, formats[0], encoding):
                        try:
                            save(font, stream, **kwargs)
                        except Exception as e:
                            logging.error('Could not save %s: %s', stream.name, e)
                return typeface
            # register saver
            for format in formats:
                cls._savers[format.lower()] = _save_func
            return _save_func

        return _save_decorator

    # inject Font operations into Typeface

    for _name, _func in Font.__dict__.items():
        if hasattr(_func, 'scriptable'):

            def _modify(self, *args, operation=_func, **kwargs):
                """Return a typeface with modified fonts."""
                fonts = [
                    operation(_font, *args, **kwargs)
                    for _font in self._fonts
                ]
                return Typeface(fonts)

            _modify.scriptable = True
            _modify.script_args = _func.script_args
            locals()[_name] = _modify
