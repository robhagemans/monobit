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

from .base import VERSION, DEFAULT_FORMAT
from .containers import Container, open_container, unique_name, ContainerFormatError
from .font import Font
from .pack import Pack
from . import streams
from .streams import (
    Stream, open_stream, compressors, has_magic, FileFormatError,
    normalise_suffix
)


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
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    # no container given - see if file is itself a container
    if not on:
        try:
            with open_container(file, mode, overwrite=overwrite) as container:
                if mode == 'r':
                    logging.info('Reading all from `%s`.', container.name)
                else:
                    logging.info('Writing all to `%s`.', container.name)
                # empty file parameter means 'load/save all'
                yield None, container
            return
        except ContainerFormatError as e:
            # infile is not a container, load/save single file
            pass
    with open_container(on, mode, overwrite=overwrite) as container:
        with open_stream(file, mode, on=container, overwrite=overwrite) as stream:
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
        infile must be a Stream or empty
        """
        if not format:
            # try to use magic sequences
            if infile:
                if infile.readable():
                    for magic, loader in cls._magic.items():
                        if has_magic(infile, magic):
                            return loader
                # fall back to suffixes
                suffix = Path(infile.name).suffix
                format = normalise_suffix(suffix or DEFAULT_FORMAT)
            else:
                format = DEFAULT_FORMAT
        return cls._loaders.get(format, None)

    @classmethod
    def load(cls, infile:str, format:str='', on:str='', **kwargs):
        """Read new font from file."""
        # if container/file provided as string or steam, open them
        if not isinstance(on, Container) or infile and not isinstance(infile, Stream):
            with open_location(infile, 'r', on=on) as (stream, container):
                return cls.load(stream, format, container, **kwargs)
        # infile not provided - load all from container
        if not infile:
            return cls._load_all(on, format, **kwargs)
        return cls._load_from_file(infile, on, format, **kwargs)

    @classmethod
    def _load_from_file(cls, infile, on, format, **kwargs):
        """Open file and load font(s) from it."""
        # infile is not a container - identify file type
        loader = cls.get_loader(infile, format=format)
        if not loader:
            raise FileFormatError('Cannot load from format `{}`.'.format(format)) from None
        return loader(infile, on, **kwargs)

    @classmethod
    def _load_all(cls, container, format, **kwargs):
        """Open container and load all fonts found in it into one pack."""
        packs = []
        # try opening a container on input file for read, will raise error if not container format
        for name in container:
            logging.debug('Attempting to load from file `%s`.', name)
            with open_stream(name, 'r', on=container) as stream:
                try:
                    font_or_pack = cls.load(stream, on=container, format=format, **kwargs)
                    logging.info('Found `%s` on `%s`', stream.name, container.name)
                except Exception as exc:
                    # if one font fails for any reason, try the next
                    # loaders raise ValueError if unable to parse
                    logging.debug('Could not load `%s`: %s', name, exc)
                else:
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
                    instream = instream.text
                if container:
                    font_or_pack = original_loader(instream, container=on, **kwargs)
                else:
                    font_or_pack = original_loader(instream, **kwargs)
                name = Path(instream.name).name
                return _set_extraction_props(font_or_pack, name, format)

            # register loader
            _loader.name = name
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
        if not format:
            if outfile:
                suffix = Path(outfile.name).suffix
                format = normalise_suffix(suffix or DEFAULT_FORMAT)
            else:
                format = DEFAULT_FORMAT
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
            overwrite: if outfile is a filename, allow overwriting existing file
        """
        # if container provided as string or steam, open it
        if not isinstance(on, Container) or outfile and not isinstance(outfile, Stream):
            with open_location(outfile, 'w', on=on, overwrite=overwrite) as (stream, container):
                return cls.save(pack_or_font, stream, format, container, **kwargs)
        if isinstance(pack_or_font, Font):
            pack = Pack([pack_or_font])
        else:
            pack = pack_or_font
        if not outfile:
            # create a container on outfile, store the fonts in there as individual files
            return cls._save_all(pack, on, format, **kwargs)
        return cls._save_to_file(pack, outfile, on, format, **kwargs)

    @classmethod
    def _save_all(cls, pack, container, format, **kwargs):
        """Save pack of fonts to a container created on outfile."""
        for font in pack:
            # generate unique filename
            name = font.name.replace(' ', '_')
            filename = unique_name(container, name, format)
            logging.debug('Attempting to save to file `%s`.', filename)
            try:
                with open_stream(filename, 'w', on=container) as stream:
                    cls._save_to_file(Pack([font]), stream, container, format, **kwargs)
                    logging.info('Saved to `%s`.', stream.name)
            except BrokenPipeError:
                pass
            except Exception as e:
                logging.error('Could not save %s: %s', filename, e)
                raise

    @classmethod
    def _save_to_file(cls, pack, outfile, on, format, **kwargs):
        """Save pack of fonts to a single file."""
        saver = cls.get_saver(outfile, format=format)
        if not saver:
            raise FileFormatError('Cannot save to format `{}`.'.format(format))
        saver(pack, outfile, on, **kwargs)
        return pack


    @classmethod
    def register(cls, *formats, name='', binary=False, multi=False, container=False):
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
                if not (container or multi or len(pack) == 1):
                    raise FileFormatError(
                        f"Can't save multiple fonts to single {name} file."
                    ) from None
                if not multi:
                    pack = pack[0]
                if not binary:
                    outfile = outfile.text
                if container:
                    original_saver(pack, outfile, container=on, **kwargs)
                else:
                    original_saver(pack, outfile, **kwargs)
                if not binary:
                    outfile.close()

            # register saver
            _saver.script_args = original_saver.__annotations__
            _saver.name = name
            for format in formats:
                cls._savers[format.lower()] = _saver
            return _saver

        return _save_decorator
