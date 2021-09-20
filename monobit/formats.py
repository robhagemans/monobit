"""
monobit.formats - loader and saver plugin registry

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import gzip
import logging
from functools import wraps
from pathlib import Path

from .base import VERSION, DEFAULT_FORMAT, scriptable
from .containers import open_container, unique_name, containers, Container
from .font import Font
from .pack import Pack
from . import streams
from .streams import compressors, has_magic


# identify font file format from suffix

def get_format(file, format=''):
    """Get format name from file name."""
    if not format:
        format = DEFAULT_FORMAT
        # if filename given, try to use it to infer format
        name = streams.get_stream_name(file)
        suffixes = Path(name).suffixes
        while len(suffixes) > 1:
            if containers.has_suffix(suffixes[-1]) or compressors.has_suffix(suffixes[-1]):
                suffixes.pop()
        if suffixes:
            format = suffixes[-1]
    # normalise suffix
    if format.startswith('.'):
        format = format[1:]
    return format.lower()


##############################################################################
# loading

class Loaders:
    """Loader plugin registry."""

    _loaders = {}
    _magic = {}

    @classmethod
    def get_loader(cls, infile, on=None, format=''):
        """Get loader function for this format."""
        # try to use magic sequences
        if infile:
            if isinstance(infile, (str, Path)) and not Path(infile).is_dir():
                with streams.open_stream(infile, 'r', binary=True, on=on) as stream:
                    return cls.get_loader(stream, on, format)
            else:
                if infile.readable():
                    for magic, loader in cls._magic.items():
                        if has_magic(infile, magic):
                            return loader
        # fall back to suffixes
        format = get_format(infile, format)
        try:
            return cls._loaders[format]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format)) from None

    @classmethod
    def load(cls, infile:str, format:str='', on:str='', **kwargs):
        """Read new font from file."""
        if on and not isinstance(on, Container):
            with open_container(on, 'r') as on:
                return cls.load(infile, format, on, **kwargs)
        # try if infile is a container first
        if not format and not on:
            try:
                return cls._load_all_from_container(infile, **kwargs)
            except TypeError:
                pass
        return cls._load_from_file(infile, on, format, **kwargs)

    @classmethod
    def _load_from_file(cls, infile, on, format, **kwargs):
        """Open file and load font(s) from it."""
        # infile is not a container - identify file type
        loader = cls.get_loader(infile, on, format)
        return loader(infile, on, **kwargs)

    @classmethod
    def _load_all_from_container(cls, infile, **kwargs):
        """Open container and load all fonts found in it into one pack."""
        packs = []
        # try opening a container, will raise error if not container format
        with open_container(infile, 'r') as container:
            for name in container:
                font_or_pack = cls._load_from_file(name, on=container, format=None, **kwargs)
                if isinstance(font_or_pack, Pack):
                    packs.append(font_or_pack)
                else:
                    packs.append([font_or_pack])
        # flatten list of packs
        fonts = [_font for _pack in packs for _font in _pack]
        return Pack(fonts)

    @classmethod
    def register(cls, *formats, magic=(), name=None, binary=False, multi=False, container=False):
        """
        Decorator to register font loader.
            *formats: list of extensions covered by this function
            name: name of the format
            binary: format is binary, not text
            multi: format can contain multiple fonts
            container: needs access to container/filesystem beyond input stream
        """
        format = name or formats[0]

        def _load_decorator(original_loader):

            # stream input wrapper
            @wraps(original_loader)
            def _loader(infile, on, **kwargs):
                with streams.open_stream(infile, 'r', binary, on=on) as instream:
                    if container:
                        font_or_pack = original_loader(instream, container=on, **kwargs)
                    else:
                        font_or_pack = original_loader(instream, **kwargs)
                    name = Path(streams.get_stream_name(instream)).name
                return _set_extraction_props(font_or_pack, name, format)

            # register loader
            _loader.script_args = original_loader.__annotations__
            for format in formats:
                cls._loaders[format.lower()] = _loader
            for sequence in magic:
                cls._magic[sequence] = _loader
            return _loader

        return _load_decorator


# extraction properties

def _set_extraction_props(font_or_pack, name, format):
    """Return copy with source-name and source-format set."""
    if isinstance(font_or_pack, Pack):
        return Pack(
            _set_extraction_props(_font, name, format)
            for _font in font_or_pack
        )
    font = font_or_pack
    new_props = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': font.source_format or format,
        'source-name': font.source_name or name
    }
    return font.set_properties(**new_props)



##############################################################################
# saving

class Savers:
    """Saver plugin registry."""

    _savers = {}

    @classmethod
    def get_saver(cls, outfile, format=''):
        """Get saver function for this format."""
        format = get_format(outfile, format)
        try:
            return cls._savers[format]
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))

    @classmethod
    def save(cls, pack, outfile:str, format:str='', on:str='', **kwargs):
        """
        Write to file, return unchanged.
            outfile: stream or filename
            format: format specification string
            on: location/container. mandatory for formats that need filesystem access.
                if specified and outfile is a filename, it is taken relative to this location.
        """
        saver = cls.get_saver(outfile, format)
        saver(pack, outfile, on, **kwargs)
        return pack


    @classmethod
    def register(cls, *formats, binary=False, multi=False, container=False):
        """
        Decorator to register font saver.
            *formats: extensions covered by registered function
            binary: format is binary, not text
            multi: format can contain multiple fonts
            container: format is stored as files in a directory or other container
        """

        def _save_decorator(original_saver):
            # stream output wrapper
            @wraps(original_saver)
            def _saver(pack_or_font, outfile, on, **kwargs):
                if isinstance(pack_or_font, Font):
                    pack = Pack([pack_or_font])
                else:
                    pack = pack_or_font
                with open_container(on, 'w', binary) as on:
                    if container or multi or len(pack) == 1:
                        with streams.open_stream(outfile, 'w', binary) as outstream:
                            if not multi:
                                pack = pack[0]
                            if container:
                                original_saver(pack, outstream, container=on, **kwargs)
                            else:
                                original_saver(pack, outstream, **kwargs)
                    else:
                        # use first extension provided by saver function
                        _save_streams(
                            original_saver, pack, outfile, on, formats[0], binary, **kwargs
                        )

            # register saver
            _saver.script_args = original_saver.__annotations__
            for format in formats:
                cls._savers[format.lower()] = _saver
            return _saver

        return _save_decorator


def _save_streams(original_saver, pack, outfile, on, suffix, binary, **kwargs):
    """Call a font saving function, save to a stream or container."""
    for font in pack:
        # generate unique filename
        name = font.name.replace(' ', '_')
        filename = unique_name(on, name, suffix)
        try:
            with streams.open_stream(filename, 'w', binary, on=on) as stream:
                original_saver(font, stream, **kwargs)
        except BrokenPipeError:
            pass
        except Exception as e:
            logging.error('Could not save %s: %s', filename, e)
            raise
