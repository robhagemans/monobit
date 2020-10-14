"""
monobit.typeface - representation of collection of fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import logging
from functools import wraps
from contextlib import contextmanager
from pathlib import Path

from .base import (
    VERSION, DEFAULT_FORMAT, scriptable,
    DirContainer, ZipContainer, TextMultiStream, unique_name
)
from .font import Font


def _open_stream(on, outfile, mode, binary=False):
    """Open a binary or encoded text stream."""
    if not binary:
        encoding = 'utf-8-sig' if mode == 'r' else 'utf-8'
        return on.open(outfile, mode, encoding=encoding)
    else:
        return on.open(outfile, mode + 'b')

def _open_container(outfile, mode, binary=True):
    """Open a zip or directory container."""
    if isinstance(outfile, (str, bytes)):
        return DirContainer(outfile, mode)
    elif binary:
        return ZipContainer(outfile, mode)
    else:
        return TextMultiStream(outfile, mode)

def _has_magic(instream, magic):
    """Check if a binary stream matches the given signature."""
    return instream.peek(len(magic)).startswith(magic)

@contextmanager
def _container_saver(save, typeface, outfile, **kwargs):
    """Call a typeface or font saving function, providing a container."""
    # use standard streams if none provided
    if not outfile or outfile == '-':
        outfile = sys.stdout.buffer
    with _open_container(outfile, 'w', binary=True) as out:
        save(typeface, out, **kwargs)

@contextmanager
def _multi_saver(save, typeface, outfile, binary, **kwargs):
    """Call a typeface saving function, providing a stream."""
    # use standard streams if none provided
    if not outfile or outfile == '-':
        outfile = sys.stdout.buffer
    if isinstance(outfile, (str, bytes)):
        outfile = _open_stream(io, outfile, 'w', binary)
    else:
        if not binary:
            outfile = io.TextIOWrapper(outfile, encoding='utf-8')
    try:
        with outfile:
            save(typeface, outfile, **kwargs)
    except BrokenPipeError:
        # ignore broken pipes
        pass

@contextmanager
def _single_saver(save, typeface, outfile, binary, ext, **kwargs):
    """Call a font saving function, providing a stream."""
    # use standard streams if none provided
    if not outfile or outfile == '-':
        outfile = sys.stdout.buffer
    if len(typeface) == 1:
        # we have only one font to deal with, no need to create container
        _multi_saver(save, [*typeface][0], outfile, binary)
    else:
        # create container and call saver for each font in the typeface
        with _open_container(outfile, 'w', binary) as out:
            # save fonts one-by-one
            for font in typeface:
                # generate unique filename
                name = font.name.replace(' ', '_')
                filename = unique_name(out, name, ext)
                try:
                    with _open_stream(out, filename, 'w', binary) as stream:
                        save(font, stream, **kwargs)
                except Exception as e:
                    logging.error('Could not save %s: %s', filename, e)
                    raise


def _set_extraction_props(typeface, infile, format):
    """Return copy with source-name and source-format set."""
    fonts = []
    for font in typeface:
        new_props = {
            'converter': 'monobit v{}'.format(VERSION),
        }
        if not font.source_name:
            if isinstance(infile, (str, bytes)):
                new_props['source-name'] = Path(infile).name
            else:
                new_props['source-name'] = Path(infile.name).name
        if not font.source_format:
            new_props['source-format'] = format
        fonts.append(font.set_properties(**new_props))
    return Typeface(fonts)


def _container_loader(load, infile, binary, format, **kwargs):
    """Open a container and provide to font loader."""
    if not infile or infile == '-':
        infile = sys.stdin.buffer
    if isinstance(infile, (str, bytes)):
        # string provided; open stream or container as appropriate
        if Path(infile).is_dir():
            container_type = DirContainer
        else:
            container_type = ZipContainer
    else:
        # stream - is it a zip container?
        with infile:
            if isinstance(infile.read(0), bytes) and _has_magic(infile, ZipContainer.magic):
                container_type = ZipContainer
            else:
                raise ValueError(
                    'Container format expected but encountering non-container stream'
                )
    with container_type(infile, 'r') as zip_con:
        typeface = load(zip_con, **kwargs)
        return _set_extraction_props(typeface, infile, format)


def _stream_loader(load, infile, binary, format, **kwargs):
    """Open a single- or multifont format."""
    if not infile or infile == '-':
        infile = sys.stdin.buffer
    container_type = None
    if isinstance(infile, (str, bytes)):
        # string provided; open stream or container as appropriate
        if Path(infile).is_dir():
            container_type = DirContainer
        else:
            with _open_stream(io, infile, 'r', binary=True) as instream:
                if _has_magic(instream, ZipContainer.magic):
                    container_type = ZipContainer
    else:
        if isinstance(infile.read(0), bytes):
            # binary stream - is it a zip container?
            if _has_magic(infile, ZipContainer.magic):
                container_type = ZipContainer
            elif not binary and _has_magic(infile, TextMultiStream.magic):
                container_type = TextMultiStream
    if not container_type:
        if isinstance(infile, (str, bytes)):
            with _open_stream(io, infile, 'r', binary) as instream:
                typeface = load(instream, **kwargs)
                return _set_extraction_props(typeface, infile, format)
        else:
            # check text/binary
            if isinstance(infile.read(0), bytes):
                if not binary:
                    infile = io.TextIOWrapper(infile, encoding='utf-8-sig')
            else:
                if binary:
                    raise ValueError('This format requires a binary stream, not a text stream.')
            typeface = load(infile, **kwargs)
            return _set_extraction_props(typeface, infile, format)
    else:
        with container_type(infile, 'r') as zip_con:
            faces = []
            for name in zip_con:
                with _open_stream(zip_con, name, 'r', binary) as stream:
                    typeface = load(stream, **kwargs)
                    faces.append(_set_extraction_props(typeface, name, format))
            return Typeface([_font for _face in faces for _font in _face])


class Typeface:
    """Holds one or more potentially unrelated fonts."""

    _loaders = {}
    _savers = {}

    def __init__(self, fonts=()):
        """Create typeface from sequence of fonts."""
        self._fonts = tuple(fonts)

    def __iter__(self):
        """Iterate over fonts in typeface."""
        return iter(self._fonts)

    def __len__(self):
        """Number of fonts in typeface."""
        return len(self._fonts)

    def __repr__(self):
        """Representation."""
        if self.names:
            return "<Typeface \n    '" + "'\n    '".join(self.names) + "'\n>"
        return '<empty Typeface>'

    def __getitem__(self, item):
        """Get a font by number."""
        if isinstance(item, str):
            for _font in self._fonts:
                if _font.name == item:
                    return _font
            raise KeyError(f'No font named {item} in collection.')
        return self._fonts[item]

    @property
    def names(self):
        """List names of fonts in collection."""
        return [_font.name for _font in self._fonts]

    @staticmethod
    def get_format(infile, format=''):
        """Get format name."""
        if isinstance(infile, bytes):
            infile = infile.decode('ascii')
        if not format:
            format = DEFAULT_FORMAT
            # if filename given, try to use it to infer format
            if isinstance(infile, str):
                suffixes = Path(infile).suffixes
                if suffixes:
                    if suffixes[-1] == '.zip' and len(suffixes) > 2:
                        format = suffixes[-2][1:]
                    else:
                        format = suffixes[-1][1:]
        return format.lower()

    @classmethod
    def get_loader(cls, infile, format=''):
        """Get loader function for this format."""
        format = cls.get_format(infile, format)
        try:
            return cls._loaders[format]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format))

    @classmethod
    def load(cls, infile:str, format:str='', **kwargs):
        """Read new font from file."""
        loader = cls.get_loader(infile, format)
        return loader(infile, **kwargs)

    @classmethod
    def get_saver(cls, outfile, format=''):
        """Get saver function for this format."""
        format = cls.get_format(outfile, format)
        try:
            return cls._savers[format]
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))

    @scriptable
    def save(self, outfile:str, format:str='', **kwargs):
        """Write to file, return unchanged."""
        saver = self.get_saver(outfile, format)
        saver(self, outfile, **kwargs)
        return self

    @classmethod
    def loads(cls, *formats, name=None, binary=False, container=False):
        """Decorator to register font loader."""
        if name is None:
            name = formats[0]

        def _load_decorator(load):
            # stream input wrapper
            @wraps(load)
            def _load_func(infile, **kwargs):
                if container:
                    return _container_loader(load, infile, binary, name, **kwargs)
                else:
                    return _stream_loader(load, infile, binary, name, **kwargs)
            # register loader
            _load_func.script_args = load.__annotations__
            for format in formats:
                cls._loaders[format.lower()] = _load_func
            return _load_func

        return _load_decorator

    @classmethod
    def saves(cls, *formats, binary=False, multi=True, container=False):
        """Decorator to register font saver."""

        def _save_decorator(save):
            # stream output wrapper
            @wraps(save)
            def _save_func(typeface, outfile, **kwargs):
                if container:
                    _container_saver(save, typeface, outfile, **kwargs)
                elif multi:
                    _multi_saver(save, typeface, outfile, binary, **kwargs)
                else:
                    # use first extension provided by saver function
                    _single_saver(save, typeface, outfile, binary, formats[0], **kwargs)
            # register saver
            _save_func.script_args = save.__annotations__
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
