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
from .containers import DirContainer, ZipContainer, TextMultiStream, unique_name, identify_container
from .font import Font
from .pack import Pack

from . import streams


# identify font file format from suffix

def get_format(infile, format=''):
    """Get format name."""
    if isinstance(infile, bytes):
        infile = infile.decode('ascii')
    if not format:
        format = DEFAULT_FORMAT
        # if filename given, try to use it to infer format
        if isinstance(infile, (str, Path)):
            suffixes = Path(infile).suffixes
            if suffixes:
                if suffixes[-1] in ('.zip', '.gz') and len(suffixes) >= 2:
                    format = suffixes[-2][1:]
                else:
                    format = suffixes[-1][1:]
    return format.lower()


##############################################################################
# loading

class Loaders:
    """Loader plugin registry."""

    _loaders = {}

    @classmethod
    def get_loader(cls, infile, format=''):
        """Get loader function for this format."""
        format = get_format(infile, format)
        try:
            return cls._loaders[format]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format)) from None

    @classmethod
    def load(cls, infile:str, format:str='', **kwargs):
        """Read new font from file."""
        loader = cls.get_loader(infile, format)
        return loader(infile, **kwargs)

    @classmethod
    def register(cls, *formats, name=None, binary=False, multi=False, container=False):
        """
        Decorator to register font loader.
            *formats: list of extensions covered by this function
            name: name of the format
            binary: format is binary, not text
            multi: format can contain multiple fonts
            container: format is stored as files in a directory or other container
        """
        if name is None:
            name = formats[0]

        def _load_decorator(load):

            # stream input wrapper
            @wraps(load)
            def _load_func(infile, **kwargs):
                if container:
                    return _container_loader(load, infile, binary, multi, name, **kwargs)
                return _stream_loader(load, infile, binary, multi, name, **kwargs)

            # register loader
            _load_func.script_args = load.__annotations__
            for format in formats:
                cls._loaders[format.lower()] = _load_func
            return _load_func

        return _load_decorator


# container-format loader

def _container_loader(load, infile, binary, multi, format, **kwargs):
    """Open a container and provide to font loader."""
    container_type = identify_container(infile)
    if not container_type:
        raise ValueError('Container format expected but encountering non-container stream')
    with container_type(infile, 'r') as zip_con:
        font_or_pack = load(zip_con, **kwargs)
        return _set_extraction_props(font_or_pack, infile, format)


# single-stream format loader

def _stream_loader(load, infile, binary, multi, format, **kwargs):
    """Open a stream and load one or more fonts."""
    container_type = identify_container(infile)
    if container_type:
        return _load_streams_from_container(
            load, infile, container_type, binary, multi, format, **kwargs
        )
    else:
        return _load_stream_directly(load, infile, binary, multi, format, **kwargs)


def _load_stream_directly(load, infile, binary, multi, format, **kwargs):
    """Load font or pack from stream."""
    with streams.make_stream(infile, 'r', binary) as instream:
        font_or_pack = load(instream, **kwargs)
        return _set_extraction_props(font_or_pack, instream.name, format)


def _load_streams_from_container(load, infile, container_type, binary, multi, format, **kwargs):
    """Open container and load all fonts found in it into one pack."""
    # text container can only hold text, so we can't read a binary font from it
    with container_type(infile, 'r') as zip_con:
        packs = []
        for name in zip_con:
            with streams.open(name, 'r', binary, on=zip_con) as stream:
                font_or_pack = load(stream, **kwargs)
                font_or_pack = _set_extraction_props(font_or_pack, name, format)
                if isinstance(font_or_pack, Pack):
                    packs.append(font_or_pack)
                else:
                    packs.append([font_or_pack])
        # flatten list of packs
        fonts = [_font for _pack in packs for _font in _pack]
        return Pack(fonts)


# extraction properties

def _set_extraction_props(font_or_pack, infile, format):
    """Return copy with source-name and source-format set."""
    if isinstance(font_or_pack, Pack):
        return Pack(
            _set_extraction_props(_font, infile, format)
            for _font in font_or_pack
        )
    if isinstance(infile, (str, bytes, Path)):
        source_name = Path(infile).name
    else:
        source_name = Path(infile.name).name
    font = font_or_pack
    new_props = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': font.source_format or format,
        'source-name': font.source_name or source_name
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
    def save(cls, pack, outfile:str, format:str='', **kwargs):
        """Write to file, return unchanged."""
        saver = cls.get_saver(outfile, format)
        saver(pack, outfile, **kwargs)
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

        def _save_decorator(save):
            # stream output wrapper
            @wraps(save)
            def _save_func(pack_or_font, outfile, **kwargs):
                if isinstance(pack_or_font, Font):
                    pack = Pack([pack_or_font])
                else:
                    pack = pack_or_font
                if container:
                    _container_saver(save, pack, outfile, **kwargs)
                elif multi:
                    _multi_saver(save, pack, outfile, binary, **kwargs)
                else:
                    # use first extension provided by saver function
                    _single_saver(save, pack, outfile, binary, formats[0], **kwargs)
            # register saver
            _save_func.script_args = save.__annotations__
            for format in formats:
                cls._savers[format.lower()] = _save_func
            return _save_func

        return _save_decorator



def _create_container(outfile, binary):
    """Open a zip, directory or text container, depending on input type."""
    if outfile and isinstance(outfile, (str, bytes, Path)):
        return DirContainer(outfile, 'w')
    elif binary:
        return ZipContainer(outfile, 'w')
    else:
        return TextMultiStream(outfile, 'w')

def _container_saver(save, pack, outfile, **kwargs):
    """Call a pack or font saving function, save to a container."""
    with _create_container(outfile, binary=True) as out:
        save(pack, out, **kwargs)

def _multi_saver(save, pack, outfile, binary, **kwargs):
    """Call a pack saving function, save to a stream."""
    # use standard streams if none provided
    if not outfile or isinstance(outfile, (str, bytes, Path)):
        outfile = streams.open(outfile, 'w', binary)
    else:
        if not binary:
            outfile = io.TextIOWrapper(outfile, encoding='utf-8')
    with outfile:
        save(pack, outfile, **kwargs)

def _single_saver(save, pack, outfile, binary, ext, **kwargs):
    """Call a font saving function, save to a stream or container."""
    if len(pack) == 1:
        # we have only one font to deal with, no need to create container
        _multi_saver(save, [*pack][0], outfile, binary, **kwargs)
    else:
        # create container and call saver for each font in the pack
        with _create_container(outfile, binary) as out:
            # save fonts one-by-one
            for font in pack:
                # generate unique filename
                name = font.name.replace(' ', '_')
                filename = unique_name(out, name, ext)
                try:
                    with streams.open(filename, 'w', binary, on=out) as stream:
                        save(font, stream, **kwargs)
                except Exception as e:
                    logging.error('Could not save %s: %s', filename, e)
                    raise
