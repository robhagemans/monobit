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

from .base import VERSION, DEFAULT_FORMAT, CONVERTER_NAME
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
def open_location(file, mode, where=None, overwrite=False):
    """
    Open a binary stream on a container or filesystem
    both `file` and `where` may be Streams, files, or file/directory names
    `where` may also be a Container
    if `where` is empty or the module io, the whole filesystem is taken as the container/location.
    returns a Steam and a Container object
    """
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    # no container given - see if file is itself a container
    if not where:
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
    with open_container(where, mode, overwrite=overwrite) as container:
        with open_stream(file, mode, where=container, overwrite=overwrite) as stream:
            yield stream, container


##############################################################################
# loading

class Loaders:
    """Loader plugin registry."""

    _loaders = {}
    _magic = {}

    def get_loader(self, infile=None, format=''):
        """
        Get loader function for this format.
        infile must be a Stream or empty
        """
        if not format:
            # try to use magic sequences
            if infile:
                if infile.readable():
                    for magic, loader in self._magic.items():
                        if has_magic(infile, magic):
                            return loader
                # fall back to suffixes
                suffix = Path(infile.name).suffix
                format = normalise_suffix(suffix or DEFAULT_FORMAT)
            else:
                format = DEFAULT_FORMAT
        return self._loaders.get(format, None)

    def load(self, infile:str, format:str='', where:str='', **kwargs):
        """Read new font from file."""
        # if container/file provided as string or steam, open them
        if not isinstance(where, Container) or infile and not isinstance(infile, Stream):
            with open_location(infile, 'r', where=where) as (stream, container):
                return self.load(stream, format, container, **kwargs)
        # infile not provided - load all from container
        if not infile:
            return self._load_all(where, format, **kwargs)
        return self._load_from_file(infile, where, format, **kwargs)

    def _load_from_file(self, infile, where, format, **kwargs):
        """Open file and load font(s) from it."""
        # infile is not a container - identify file type
        loader = self.get_loader(infile, format=format)
        if not loader:
            raise FileFormatError('Cannot load from format `{}`.'.format(format)) from None
        return loader(infile, where, **kwargs)

    def _load_all(self, container, format, **kwargs):
        """Open container and load all fonts found in it into one pack."""
        packs = []
        # try opening a container on input file for read, will raise error if not container format
        for name in container:
            logging.debug('Attempting to load from file `%s`.', name)
            with open_stream(name, 'r', where=container) as stream:
                try:
                    font_or_pack = self.load(stream, where=container, format=format, **kwargs)
                    logging.info('Found `%s` on `%s`', stream.name, container.name)
                except Exception as exc:
                    # if one font fails for any reason, try the next
                    # loaders raise ValueError if unable to parse
                    logging.debug('Could not load `%s`: %s', name, exc)
                else:
                    packs.append(Pack(font_or_pack))
        # flatten list of packs
        fonts = [_font for _pack in packs for _font in _pack]
        return Pack(fonts)

    def register(self, *formats, magic=(), name='', saver=None):
        """
        Decorator to register font loader.
            *formats: extensions covered by registered function
            name: name of the format
        """
        def _load_decorator(original_loader):

            # stream input wrapper
            @wraps(original_loader)
            def _loader(instream, where, **kwargs):
                fonts = original_loader(instream, where=where, **kwargs)
                if not fonts:
                    raise ValueError('No fonts found in file.')
                pack = Pack(fonts)
                filename = Path(instream.name).name
                return Pack(
                    _font.set_properties(
                        converter=CONVERTER_NAME,
                        source_format=_font.source_format or name,
                        source_name=_font.source_name or filename
                    )
                    for _font in pack
                )

            # register loader
            _loader.name = name
            _loader.script_args = original_loader.__annotations__
            _loader.saver = saver
            _loader.formats = formats
            if saver:
                saver.loader = _loader
                _loader.name = name or saver.name
                _loader.formats = _loader.formats or saver.formats
            for format in _loader.formats:
                self._loaders[format.lower()] = _loader
            for sequence in magic:
                self._magic[sequence] = _loader
            return _loader

        return _load_decorator


loaders = Loaders()


##############################################################################
# saving

class Savers:
    """Saver plugin registry."""

    _savers = {}

    def get_saver(self, outfile=None, format=''):
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
        return self._savers.get(format, None)

    def save(
            self, pack_or_font,
            outfile:str, format:str='', where:str='', overwrite:bool=False,
            **kwargs
        ):
        """
        Write to file, return unchanged.
            outfile: stream or filename
            format: format specification string
            where: location/container. mandatory for formats that need filesystem access.
                if specified and outfile is a filename, it is taken relative to this location.
            overwrite: if outfile is a filename, allow overwriting existing file
        """
        # if container provided as string or steam, open it
        if not isinstance(where, Container) or outfile and not isinstance(outfile, Stream):
            with open_location(outfile, 'w', where=where, overwrite=overwrite) as (stream, container):
                return self.save(pack_or_font, stream, format, container, **kwargs)
        pack = Pack(pack_or_font)
        if not outfile:
            # create a container on outfile, store the fonts in there as individual files
            return self._save_all(pack, where, format, **kwargs)
        return self._save_to_file(pack, outfile, where, format, **kwargs)

    def _save_all(self, pack, where, format, **kwargs):
        """Save pack of fonts to a container created on outfile."""
        for font in pack:
            # generate unique filename
            name = font.name.replace(' ', '_')
            filename = unique_name(where, name, format)
            logging.debug('Attempting to save to file `%s`.', filename)
            try:
                with open_stream(filename, 'w', where=where) as stream:
                    self._save_to_file(Pack(font), stream, where, format, **kwargs)
                    logging.info('Saved to `%s`.', stream.name)
            except BrokenPipeError:
                pass
            except Exception as e:
                logging.error('Could not save %s: %s', filename, e)
                raise

    def _save_to_file(self, pack, outfile, where, format, **kwargs):
        """Save pack of fonts to a single file."""
        saver = self.get_saver(outfile, format=format)
        if not saver:
            raise FileFormatError('Cannot save to format `{}`.'.format(format))
        saver(pack, outfile, where, **kwargs)
        return pack


    def register(self, *formats, name='', loader=None):
        """
        Decorator to register font saver.
            *formats: extensions covered by registered function
            name: name of the format
            loader: loader for this format
        """
        def _save_decorator(original_saver):

            # stream output wrapper
            @wraps(original_saver)
            def _saver(pack, outfile, where, **kwargs):
                original_saver(pack, outfile, where=where, **kwargs)

            # register saver
            _saver.script_args = original_saver.__annotations__
            _saver.name = name
            _saver.loader = loader
            _saver.formats = formats
            if loader:
                loader.saver = _saver
                _saver.name = name or loader.name
                _saver.formats = _saver.formats or loader.formats
            for format in _saver.formats:
                self._savers[format.lower()] = _saver
            return _saver

        return _save_decorator

savers = Savers()
