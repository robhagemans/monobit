"""
monobit.files - load and save fonts

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

from ..base import VERSION, DEFAULT_FORMAT, CONVERTER_NAME
from ..containers import Container, open_container, ContainerFormatError
from ..font import Font
from ..pack import Pack
from .. import streams
from ..streams import (
    Stream, MagicRegistry, FileFormatError,
    normalise_suffix, open_stream, has_magic
)


##############################################################################

@contextmanager
def open_location(file, mode, where=None, overwrite=False):
    """
    Open a binary stream on a container or filesystem
    both `file` and `where` may be Streams, files, or file/directory names
    `where` may also be a Container
    if `where` is empty, the whole filesystem is taken as the container/location.
    if `overwrite` is True, will overwrite `file`. Note that `where` is always considered overwritable
    returns a Steam and a Container object
    """
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not file and not where:
        raise ValueError(f'No location provided.')
    # interpret incomplete arguments
    # no choice - can't open a stream on a directory
    if isinstance(file, (str, Path)) and Path(file).is_dir():
        where = file
        file = None
    # only container location provided - traverse into it
    if where and not file:
        with open_container(where, mode, overwrite=True) as container:
            # empty file parameter means 'load/save all'
            yield None, container
        return
    if not where and isinstance(file, (str, Path)):
        # see if file is itself a container
        # don't open containers if we only have a stream - we don't want surprise directory creation
        try:
            with open_container(file, mode, overwrite=overwrite) as container:
                yield None, container
            return
        except ContainerFormatError as e:
            # file is not itself a container, use enclosing dir as container
            where = Path(file).parent
            file = Path(file).name
    # we have a stream and maybe a container
    with open_container(where, mode, overwrite=True) as container:
        with open_stream(file, mode, where=container, overwrite=overwrite) as stream:
            # see if file is itself a container
            try:
                with open_container(stream, mode, overwrite=overwrite) as container:
                    yield None, container
                return
            except ContainerFormatError as e:
                # infile is not a container, load/save single file
                yield stream, container

##############################################################################
# loading

class Loaders(MagicRegistry):
    """Loader plugin registry."""

    _loaders = {}
    _magic = {}

    def get_loader(self, infile=None, format=''):
        """
        Get loader function for this format.
        infile must be a Stream or empty
        """
        loader = None
        if not format:
            loader = self.identify(infile, mode='r')
        if not loader:
            loader = self[format or DEFAULT_FORMAT]
        return loader

    def load(self, infile:str, format:str='', where:str='', **kwargs):
        """Read new font from file."""
        # if container/file provided as string or steam, open them
        with open_location(infile, 'r', where=where) as (stream, container):
            # infile not provided - load all from container
            if not stream:
                return self._load_all(container, format, **kwargs)
            return self._load_from_file(stream, container, format, **kwargs)

    def _load_from_file(self, infile, where, format, **kwargs):
        """Open file and load font(s) from it."""
        # infile is not a container - identify file type
        loader = self.get_loader(infile, format=format)
        if not loader:
            raise FileFormatError('Cannot load from format `{}`.'.format(format)) from None
        logging.info('Loading `%s` on `%s` as %s', infile.name, where.name, loader.name)
        return loader(infile, where, **kwargs)

    def _load_all(self, container, format, **kwargs):
        """Open container and load all fonts found in it into one pack."""
        logging.info('Reading all from `%s`.', container.name)
        packs = Pack()
        # try opening a container on input file for read, will raise error if not container format
        for name in container:
            logging.debug('Trying `%s` on `%s`.', name, container.name)
            with open_stream(name, 'r', where=container) as stream:
                try:
                    font_or_pack = self.load(stream, where=container, format=format, **kwargs)
                except Exception as exc:
                    # if one font fails for any reason, try the next
                    # loaders raise ValueError if unable to parse
                    logging.debug('Could not load `%s`: %s', name, exc)
                else:
                    packs += Pack(font_or_pack)
        return packs

    def register(self, *formats, magic=(), name='', saver=None):
        """
        Decorator to register font loader.
            *formats: extensions covered by registered function
            name: name of the format
        """
        register_magic = super().register

        def _load_decorator(original_loader):

            # stream input wrapper
            @wraps(original_loader)
            def _loader(instream, where, **kwargs):
                fonts = original_loader(instream, where=where, **kwargs)
                if not fonts:
                    raise FileFormatError('No fonts found in file.')
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
            register_magic(*_loader.formats, magic=magic)(_loader)
            return _loader

        return _load_decorator


loaders = Loaders()


##############################################################################
# saving

class Savers(MagicRegistry):
    """Saver plugin registry."""

    _savers = {}

    def get_saver(self, outfile=None, format=''):
        """
        Get saver function for this format.
        `outfile` must be a Stream or empty.
        """
        saver = None
        if not format:
            saver = self.identify(outfile, mode='r')
        if not saver:
            saver = self[format or DEFAULT_FORMAT]
        return saver

    def save(
            self, pack_or_font,
            outfile:str, format:str='', where:str='', overwrite:bool=False,
            **kwargs
        ):
        """
        Write to file, no return value.
            outfile: stream or filename
            format: format specification string
            where: location/container. mandatory for formats that need filesystem access.
                if specified and outfile is a filename, it is taken relative to this location.
            overwrite: if outfile is a filename, allow overwriting existing file
        """
        pack = Pack(pack_or_font)
        with open_location(outfile, 'w', where=where, overwrite=overwrite) as (stream, container):
            if not stream:
                self._save_all(pack, container, format, **kwargs)
            else:
                self._save_to_file(pack, stream, container, format, **kwargs)

    def _save_all(self, pack, where, format, **kwargs):
        """Save fonts to a container."""
        logging.info('Writing all to `%s`.', where.name)
        for font in pack:
            # generate unique filename
            name = font.name.replace(' ', '_')
            format = format or DEFAULT_FORMAT
            filename = where.unused_name(name, format)
            try:
                with open_stream(filename, 'w', where=where) as stream:
                    self._save_to_file(Pack(font), stream, where, format, **kwargs)
            except BrokenPipeError:
                pass
            except Exception as e:
                logging.error('Could not save `%s`: %s', filename, e)
                #raise

    def _save_to_file(self, pack, outfile, where, format, **kwargs):
        """Save fonts to a single file."""
        saver = self.get_saver(outfile, format=format)
        if not saver:
            raise FileFormatError('Cannot save to format `{}`.'.format(format))
        logging.info('Saving `%s` on `%s` as %s.', outfile.name, where.name, saver.name)
        saver(pack, outfile, where, **kwargs)


    def register(self, *formats, name='', loader=None):
        """
        Decorator to register font saver.
            *formats: extensions covered by registered function
            name: name of the format
            loader: loader for this format
        """
        register_magic = super().register

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
            register_magic(*_saver.formats, magic=())(_saver)
            return _saver

        return _save_decorator

savers = Savers()
