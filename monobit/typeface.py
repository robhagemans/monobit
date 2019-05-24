"""
monobit.typeface - representation of collection of fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from .base import DEFAULT_FORMAT, scriptable, ensure_stream
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
        # TODO: set source-name and source-format (add a human name for each format in the decorator)

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
    def loads(cls, *formats, encoding='utf-8-sig'):
        """Decorator to register font loader."""
        def _load_decorator(load):

            # stream input wrapper
            def _load_func(infile, **kwargs):
                with ensure_stream(infile, 'r', encoding=encoding) as instream:
                    return load(instream, **kwargs)
            _load_func.__doc__ = load.__doc__
            _load_func.__name__ = load.__name__

            # register loader
            for format in formats:
                cls._loaders[format.lower()] = _load_func

            return _load_func
        return _load_decorator

    @classmethod
    def saves(cls, *formats, encoding='utf-8'):
        """Decorator to register font saver."""
        def _save_decorator(save):

            # stream output wrapper
            def _save_func(typeface, outfile, **kwargs):
                with ensure_stream(outfile, 'w', encoding=encoding) as outstream:
                    save(typeface, outstream, **kwargs)
                return typeface
            _save_func.__doc__ = save.__doc__
            _save_func.__name__ = save.__name__

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
