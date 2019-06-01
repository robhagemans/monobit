"""
monobit.typeface - representation of collection of fonts

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from os.path import basename
from functools import wraps
from contextlib import contextmanager
import io
import sys
import os

from .base import VERSION, DEFAULT_FORMAT, scriptable, DirContainer, ZipContainer
from .font import Font


def _open_stream(on, outfile, mode, encoding):
    """Open a binary or encoded text stream."""
    # we take encoding == None to mean binary
    if encoding:
        return on.open(outfile, mode, encoding=encoding)
    else:
        return on.open(outfile, mode + 'b')

def _open_container(outfile, mode):
    """Open a zip or directory container."""
    if isinstance(outfile, (str, bytes)):
        return DirContainer(outfile, mode)
    else:
        return ZipContainer(outfile, mode)


@contextmanager
def _container_saver(save, typeface, outfile, **kwargs):
    """Call a typeface or font saving function, providing a container."""
    # use standard streams if none provided
    if not outfile or outfile=='-':
        outfile = sys.stdout.buffer
    with _open_container(outfile, 'w') as out:
        save(typeface, out, **kwargs)

@contextmanager
def _multi_saver(save, typeface, outfile, encoding, **kwargs):
    """Call a typeface saving function, providing a stream."""
    # use standard streams if none provided
    if not outfile or outfile=='-':
        outfile = sys.stdout.buffer
        # we take encoding == None to mean binary
        if encoding:
            outfile = io.TextIOWrapper(outfile, encoding=encoding)
    if isinstance(outfile, (str, bytes)):
        outfile = _open_stream(io, outfile, 'w', encoding)
    try:
        with outfile:
            save(typeface, outfile, **kwargs)
    except BrokenPipeError:
        # ignore broken pipes
        pass

@contextmanager
def _single_saver(save, typeface, outfile, encoding, ext, **kwargs):
    """Call a font saving function, providing a stream."""
    print(repr((save, typeface, outfile, encoding, ext, kwargs)))
    # use standard streams if none provided
    if not outfile or outfile=='-':
        outfile = sys.stdout.buffer
    if len(typeface) == 1:
        # we have only one font to deal with, no need to create container
        _multi_saver(save, [*typeface][0], outfile, encoding)
    else:
        # create container and call saver for each font in the typeface
        with _open_container(outfile, 'w') as out:
            # save fonts one-by-one
            for font in typeface:
                # generate unique filename
                name = font.name.replace(' ', '_')
                filename = '{}.{}'.format(name, ext)
                i = 0
                print('\n', repr(filename), filename in out, list(out))
                while filename in out:
                    i += 1
                    filename = '{}.{}.{}'.format(name, i, ext)
                try:
                    with _open_stream(out, filename, 'w', encoding) as stream:
                        save(font, stream, **kwargs)
                except Exception as e:
                    logging.error('Could not save %s: %s', filename, e)


@contextmanager
def _call_saver(save, typeface, outfile, encoding, container, multi, ext, **kwargs):
    """
    Call a typeface or font saving function. Provide stream or container as needed.
        encoding: stream text encoding. None for binary or container
        container: saver expexts a container, not a stream
        multi: True - saver saves a typeface; False - one font only
        ext: extension of individual file names created (format name)
    """
    if container:
        _container_saver(save, typeface, outfile, **kwargs)
    elif multi:
        _multi_saver(save, typeface, outfile, encoding, **kwargs)
    else:
        _single_saver(save, typeface, outfile, encoding, ext, **kwargs)
    return typeface


#TODO: maybe use separate loads/saves wrappers instead of this mess,
# e.g @loads_single, @loads_multiple, @loads_container, @loads_text etc

_ZIP_MAGIC = b'PK\x03\x04'

def _call_loader(load, infile, encoding, container, **kwargs):
    if isinstance(infile, (str, bytes)):
        # string provided; open stream or container as appropriate
        if container:
            if os.path.isdir(infile):
                container_type = DirContainer
            else:
                container_type = ZipContainer
            with container_type(infile, 'r') as zip_con:
                return load(zip_con, **kwargs)
        else:
            if os.path.isdir(infile):
                container_type = DirContainer
            else:
                # open file to read magic
                with _open_stream(io, infile, 'r', encoding=None) as instream:
                    if instream.peek(4).startswith(_ZIP_MAGIC):
                        container_type = ZipContainer
                    else:
                        with _open_stream(io, infile, 'r', encoding) as instream:
                            return load(instream, **kwargs)
            with container_type(infile, 'r') as zip_con:
                faces = []
                for name in zip_con:
                    with _open_stream(zip_con, name, 'r', encoding) as stream:
                        faces.append(load(stream, **kwargs))
                return Typeface([_font for _face in faces for _font in _face])
    else:
        with infile:
            # check if text stream
            streamcontent = infile.read(0)
            # binary stream, is it a zip container?
            if isinstance(streamcontent, bytes) and infile.peek(4) == _ZIP_MAGIC:
                with ZipContainer(infile, 'r') as zip_con:
                    if container:
                        return load(zip_con, **kwargs)
                    else:
                        faces = [load(_stream, **kwargs) for _stream in zip_con]
                        return Typeface([_font for _face in faces for _font in _face])
            else:
                # just a binary or text stream
                if container:
                    raise ValueError(
                        'Container format expected but encountering non-container stream'
                    )
                # loader will provide single- or multi-font typeface
                return load(infile, **kwargs)


class Typeface:
    """Holds one or more potentially unrelated fonts."""

    _loaders = {}
    _savers = {}
    _encodings = {}

    def __init__(self, fonts=()):
        """Create typeface from sequence of fonts."""
        self._fonts = tuple(fonts)

    def __iter__(self):
        """Iterate over fonts in typeface."""
        return iter(self._fonts)

    def __len__(self):
        """Number of fonts in typeface."""
        return len(self._fonts)

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
                    base, format = infile.rsplit('.', 1)
                    if format == 'zip':
                        _, format = base.rsplit('.', 1)
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
        saver(self, outfile, **kwargs)
        return self

    def _set_extraction_props(self, infile):
        """Return copy with source-name and source-format set."""
        fonts = []
        for font in self:
            new_props = {
                'converter': 'monobit v{}'.format(VERSION),
            }
            if not font.source_name:
                if isinstance(infile, (str, bytes)):
                    new_props['source-name'] = basename(infile)
                else:
                    new_props['source-name'] = basename(infile.name)
            if not font.source_format:
                new_props['source-format'] = name
            fonts.append(font.set_properties(**new_props))
        return Typeface(fonts)

    @classmethod
    def loads(cls, *formats, name=None, encoding='utf-8-sig', container=False):
        """Decorator to register font loader."""
        if name is None:
            name = formats[0]

        def _load_decorator(load):
            # stream input wrapper
            @wraps(load)
            def _load_func(infile, **kwargs):
                typeface = _call_loader(load, infile, encoding, container, **kwargs)
                # set source-name and source-format
                return typeface._set_extraction_props(infile)
            # register loader
            for format in formats:
                cls._loaders[format.lower()] = _load_func
            return _load_func

        return _load_decorator

    @classmethod
    def saves(cls, *formats, encoding='utf-8', multi=True, container=False):
        """Decorator to register font saver."""

        def _save_decorator(save):
            # stream output wrapper
            @wraps(save)
            def _save_func(typeface, outfile, **kwargs):
                if container:
                    _container_saver(save, typeface, outfile, **kwargs)
                elif multi:
                    _multi_saver(save, typeface, outfile, encoding, **kwargs)
                else:
                    # use first extension provided by saver function
                    _single_saver(save, typeface, outfile, encoding, formats[0], **kwargs)
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
