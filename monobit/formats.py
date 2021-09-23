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
from contextlib import contextmanager

from .base import VERSION, DEFAULT_FORMAT, scriptable
from .containers import Container, open_container, unique_name, containers
from .font import Font
from .pack import Pack
from . import streams
from .streams import Stream, open_stream, make_textstream, compressors, has_magic


# identify font file format from suffix

def get_format(file=None, format=''):
    """
    Get format name from file name.
    `file` must be a Stream or empty
    """
    if not format:
        format = DEFAULT_FORMAT
        if file:
            # if filename given, try to use it to infer format
            suffix = Path(file.name).suffix
            if suffix:
                format = suffix
    # normalise suffix
    if format.startswith('.'):
        format = format[1:]
    return format.lower()


##############################################################################

@contextmanager
def open_location(file, mode, on=None, overwrite=False):
    """
    Open a binary stream on a container or filesystem
    both `file` and `on` may be Streams, files, or file/directory names
    `on` may also be a Container
    if `on` is empty or the module io, the whole filesystem is taken as the container/location.
    returns a Steam and a Container object
    """
    with open_container(on, mode) as container:
        with open_stream(file, mode, binary=True, on=container, overwrite=overwrite) as stream:
            yield stream, container


##############################################################################
# loading

class Loaders:
    """Loader plugin registry."""

    _loaders = {}
    _magic = {}

    @classmethod
    def get_loader(cls, infile=None, format=''):
        """
        Get loader function for this format.
        infile must be a Stream or empty.
        """
        # try to use magic sequences
        if infile and infile.readable():
            for magic, loader in cls._magic.items():
                if has_magic(infile, magic):
                    return loader
        # fall back to suffixes
        format = get_format(infile, format)
        return cls._loaders.get(format, None)

    @classmethod
    def load(cls, infile:str, format:str='', on:str='', **kwargs):
        """Read new font from file."""
        # if container provided as string or steam, open it
        if not isinstance(on, Container) or not isinstance(infile, Stream):
            with open_location(infile, 'r', on=on) as (stream, container):
                return cls.load(stream, format, container, **kwargs)
        # try if infile is a container first
        if not format:
            try:
                return cls._load_all_from_container(infile, **kwargs)
            except TypeError:
                pass
        return cls._load_from_file(infile, on, format, **kwargs)

    @classmethod
    def _load_from_file(cls, infile, on, format, **kwargs):
        """Open file and load font(s) from it."""
        # infile is not a container - identify file type
        loader = cls.get_loader(infile, format=format)
        if not loader:
            raise ValueError('Cannot load from format `{}`.'.format(format)) from None
        return loader(infile, on, **kwargs)

    @classmethod
    def _load_all_from_container(cls, infile, **kwargs):
        """Open container and load all fonts found in it into one pack."""
        packs = []
        # try opening a container on input file for read, will raise error if not container format
        with open_container(infile, 'r') as container:
            for name in container:
                with open_stream(name, 'r', binary=True, on=container) as stream:
                    font_or_pack = cls._load_from_file(stream, on=container, format=None, **kwargs)
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
            def _loader(instream, on, **kwargs):
                if not binary:
                    instream = make_textstream(instream)
                if container:
                    font_or_pack = original_loader(instream, container=on, **kwargs)
                else:
                    font_or_pack = original_loader(instream, **kwargs)
                name = Path(instream.name).name
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
    def get_saver(cls, outfile=None, format=''):
        """
        Get saver function for this format.
        `outfile` must be a Stream or empty.
        """
        format = get_format(outfile, format)
        return cls._savers.get(format, None)

    @classmethod
    def save(
            cls, pack_or_font,
            outfile:str, format:str='', on:str='', overwrite:bool=False,
            **kwargs
        ):
        """
        Write to file, return unchanged.
            outfile: stream or filename
            format: format specification string
            on: location/container. mandatory for formats that need filesystem access.
                if specified and outfile is a filename, it is taken relative to this location.
            overwrite: if outfile is a filename, allow overwriting exising file
        """
        # if container provided as string or steam, open it
        if not isinstance(on, Container) or not isinstance(outfile, Stream):
            with open_location(outfile, 'w', on=on, overwrite=overwrite) as (stream, container):
                return cls.save(pack_or_font, stream, format, container, **kwargs)
        if isinstance(pack_or_font, Font):
            pack = Pack([pack_or_font])
        else:
            pack = pack_or_font
        saver = cls.get_saver(outfile, format=format)
        if not saver:
            raise ValueError('Cannot save to format `{}`.'.format(format))
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
            def _saver(pack, outfile, on, **kwargs):
                if container or multi or len(pack) == 1:
                    if not binary:
                        outfile = make_textstream(outfile)
                    if not multi:
                        pack = pack[0]
                    if container:
                        original_saver(pack, outfile, container=on, **kwargs)
                    else:
                        original_saver(pack, outfile, **kwargs)
                else:
                    # create a container on outfile, store the fonts in there
                    # use first extension provided by saver function
                    _save_all_to_container(
                        original_saver, pack, outfile, formats[0], binary, **kwargs
                    )

            # register saver
            _saver.script_args = original_saver.__annotations__
            for format in formats:
                cls._savers[format.lower()] = _saver
            return _saver

        return _save_decorator


def _save_all_to_container(original_saver, pack, outfile, suffix, binary, **kwargs):
    """Call a font saving function, save to a stream or container."""
    with open_container(outfile, 'w', binary) as on:
        for font in pack:
            # generate unique filename
            name = font.name.replace(' ', '_')
            filename = unique_name(on, name, suffix)
            try:
                with open_stream(filename, 'w', binary, on=on) as stream:
                    original_saver(font, stream, **kwargs)
            except BrokenPipeError:
                pass
            except Exception as e:
                logging.error('Could not save %s: %s', filename, e)
