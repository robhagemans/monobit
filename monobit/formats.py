"""
monobit.formats - loader and saver plugin registry

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import gzip
import logging
from functools import wraps
from contextlib import contextmanager
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


# container functions


def _create_container(outfile, binary):
    """Open a zip or directory container."""
    if isinstance(outfile, (str, bytes, Path)):
        return DirContainer(outfile, 'w')
    elif binary:
        return ZipContainer(outfile, 'w')
    else:
        return TextMultiStream(outfile, 'w')

# stream functions

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
                return _loader(container, load, infile, binary, multi, name, **kwargs)

            # register loader
            _load_func.script_args = load.__annotations__
            for format in formats:
                cls._loaders[format.lower()] = _load_func
            return _load_func

        return _load_decorator


def _loader(container_format, load, infile, binary, multi, name, **kwargs):
    """Open a stream or container and load one or more fonts."""
    if not infile or infile == '-':
        infile = sys.stdin.buffer
    container_type = identify_container(infile)
    if container_format:
        return _container_loader(load, infile, container_type, binary, multi, name, **kwargs)
    else:
        return _stream_loader(load, infile, container_type, binary, multi, name, **kwargs)


# container-format loader

def _container_loader(load, infile, container_type, binary, multi, format, **kwargs):
    """Open a container and provide to font loader."""
    if not container_type:
        raise ValueError('Container format expected but encountering non-container stream')
    with container_type(infile, 'r') as zip_con:
        font_or_pack = load(zip_con, **kwargs)
        return _set_extraction_props(font_or_pack, infile, format, multi)


# single-stream format loader

def _stream_loader(load, infile, container_type, binary, multi, format, **kwargs):
    """Open a stream and load one or more fonts."""
    # text container can only hold text, so we can't read a binary font from it
    if binary and container_type == TextMultiStream:
        raise ValueError('This format requires a binary stream, not a text stream.')
    if isinstance(infile, (str, bytes, Path)):
        # all containers expect binary stream, including TextMultiStream
        with streams.open(io, infile, 'r', binary=True) as instream:
            return _stream_loader(
                load, instream, container_type, binary, multi, format, **kwargs
            )
    if container_type:
        return _load_streams_from_container(
            load, infile, container_type, binary, multi, format, **kwargs
        )
    else:
        return _load_stream_directly(load, infile, binary, multi, format, **kwargs)


def _load_stream_directly(load, infile, binary, multi, format, **kwargs):
    """Load font or pack from stream."""
    if isinstance(infile, (str, bytes, Path)):
        with streams.open(io, infile, 'r', binary) as instream:
            return _load_stream_directly(load, instream, binary, multi, format, **kwargs)
    else:
        # check text/binary
        # a text format can be read from a binary stream with a wrapper
        # but vice versa can't be done
        if streams.is_binary(infile):
            if not binary:
                infile = io.TextIOWrapper(infile, encoding='utf-8-sig')
        elif binary:
            raise ValueError('This format requires a binary stream, not a text stream.')
        font_or_pack = load(infile, **kwargs)
        return _set_extraction_props(font_or_pack, infile, format, multi)


def _load_streams_from_container(load, infile, container_type, binary, multi, format, **kwargs):
    """Open container and load all fonts found in it into one pack."""
    if binary and container_type == TextMultiStream:
        raise ValueError('This format requires a binary stream, not a text stream.')
    if isinstance(infile, (str, bytes, Path)):
        # all containers expect binary stream, including TextMultiStream
        with streams.open(io, infile, 'r', binary=True) as instream:
            return _load_streams_from_container(
                load, instream, container_type, binary, multi, format, **kwargs
            )
    with container_type(infile, 'r') as zip_con:
        packs = []
        for name in zip_con:
            with streams.open(zip_con, name, 'r', binary) as stream:
                font_or_pack = load(stream, **kwargs)
                font_or_pack = _set_extraction_props(font_or_pack, name, format, multi)
                if isinstance(font_or_pack, Pack):
                    packs.append(font_or_pack)
                else:
                    packs.append([font_or_pack])
        # flatten list of packs
        fonts = [_font for _pack in packs for _font in _pack]
        return Pack(fonts)




# extraction properties

def _set_extraction_props(font_or_pack, infile, format, multi):
    """Return copy with source-name and source-format set."""
    if multi:
        return Pack(
            _set_font_extraction_props(_font, infile, format)
            for _font in font_or_pack
        )
    else:
        return _set_font_extraction_props(font_or_pack, infile, format)

def _set_font_extraction_props(font, infile, format):
    """Return copy of font with source-name and source-format set."""
    if isinstance(infile, (str, bytes, Path)):
        source_name = Path(infile).name
    else:
        source_name = Path(infile.name).name
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



@contextmanager
def _container_saver(save, pack, outfile, **kwargs):
    """Call a pack or font saving function, save to a container."""
    # use standard streams if none provided
    if not outfile or outfile == '-':
        outfile = sys.stdout.buffer
    with _create_container(outfile, binary=True) as out:
        save(pack, out, **kwargs)

@contextmanager
def _multi_saver(save, pack, outfile, binary, **kwargs):
    """Call a pack saving function, save to a stream."""
    # use standard streams if none provided
    if not outfile or outfile == '-':
        outfile = sys.stdout.buffer
    if isinstance(outfile, (str, bytes, Path)):
        outfile = streams.open(io, outfile, 'w', binary)
    else:
        if not binary:
            outfile = io.TextIOWrapper(outfile, encoding='utf-8')
    try:
        with outfile:
            save(pack, outfile, **kwargs)
    except BrokenPipeError:
        # ignore broken pipes
        pass

@contextmanager
def _single_saver(save, pack, outfile, binary, ext, **kwargs):
    """Call a font saving function, save to a stream."""
    # use standard streams if none provided
    if not outfile or outfile == '-':
        outfile = sys.stdout.buffer
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
                    with streams.open(out, filename, 'w', binary) as stream:
                        save(font, stream, **kwargs)
                except Exception as e:
                    logging.error('Could not save %s: %s', filename, e)
                    raise
