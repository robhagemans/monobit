"""
monobit.storage - load and save fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import sys
import logging
from pathlib import Path
from contextlib import contextmanager

from .constants import VERSION, CONVERTER_NAME
from .containers import ContainerFormatError, open_container
from .font import Font
from .pack import Pack
from .streams import MagicRegistry, FileFormatError, open_stream, maybe_text
from .scripting import scriptable, ScriptArgs, ARG_PREFIX
from .basetypes import Any


DEFAULT_TEXT_FORMAT = 'yaff'
DEFAULT_BINARY_FORMAT = 'raw'


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
                pass
            # infile is not a container, load/save single file
            yield stream, container


##############################################################################
# loading


@scriptable(unknown_args='passthrough', record=False)
def load(infile:Any='', *, format:str='', where:Any='', **kwargs):
    """
    Read font(s) from file.

    infile: input file (default: stdin)
    format: input format (default: infer from magic number or filename)
    where: enclosing container stream or name (default: current working directory)
    """
    infile = infile or sys.stdin
    return _load_from_location(infile, where, format, **kwargs)


def _load_from_location(infile, where, format, **kwargs):
    """Read font(s) from file."""
    # if container/file provided as string or steam, open them
    with open_location(infile, 'r', where=where) as (stream, container):
        # infile not provided - load all from container
        if not stream:
            return _load_all(container, format, **kwargs)
        return _load_from_file(stream, container, format, **kwargs)

def _load_from_file(instream, where, format, **kwargs):
    """Open file and load font(s) from it."""
    # identify file type
    loader = loaders.get_for(instream, format=format, do_open=True)
    if not loader:
        raise FileFormatError('Cannot load from format `{}`.'.format(format)) from None
    logging.info('Loading `%s` on `%s` as %s', instream.name, where.name, loader.name)
    fonts = loader(instream, where, **kwargs)
    # convert font or pack to pack
    if not fonts:
        raise FileFormatError('No fonts found in file.')
    pack = Pack(fonts)
    # set conversion properties
    filename = Path(instream.name).name
    # if the source filename contains surrogate-escaped non-utf8 bytes
    # preserve the byte values as backslash escapes
    try:
        filename.encode('utf-8')
    except UnicodeError:
        filename = (
            filename.encode('utf-8', 'surrogateescape')
            .decode('ascii', 'backslashreplace')
        )
    return Pack(
        _font.modify(
            converter=CONVERTER_NAME,
            source_format=_font.source_format or loader.name,
            source_name=_font.source_name or filename
        )
        for _font in pack
    )

def _load_all(container, format, **kwargs):
    """Open container and load all fonts found in it into one pack."""
    logging.info('Reading all from `%s`.', container.name)
    packs = Pack()
    # try opening a container on input file for read, will raise error if not container format
    for name in container:
        logging.debug('Trying `%s` on `%s`.', name, container.name)
        with open_stream(name, 'r', where=container) as stream:
            try:
                pack = _load_from_location(stream, where=container, format=format, **kwargs)
            except Exception as exc:
                # if one font fails for any reason, try the next
                # loaders raise ValueError if unable to parse
                logging.debug('Could not load `%s`: %s', name, exc)
            else:
                packs += Pack(pack)
    return packs


##############################################################################
# saving



@scriptable(unknown_args='passthrough', record=False, pack_operation=True)
def save(
        pack_or_font,
        outfile:Any='', *,
        format:str='', where:Any='', overwrite:bool=False,
        **kwargs
    ):
    """
    Write font(s) to file.

    outfile: output file (default: stdout)
    format: font file format
    where: enclosing location/container. (default: current working directory)
    overwrite: if outfile is a filename, allow overwriting existing file
    """
    # `where` is mandatory for formats that need filesystem access.
    # if specified and outfile is a filename, it is taken relative to this location.
    pack = Pack(pack_or_font)
    outfile = outfile or sys.stdout
    if outfile == sys.stdout:
        # errors can occur if the strings we write contain surrogates
        # these may come from filesystem names using 'surrogateescape'
        sys.stdout.reconfigure(errors='replace')
    with open_location(outfile, 'w', where=where, overwrite=overwrite) as (stream, container):
        if not stream:
            _save_all(pack, container, format, **kwargs)
        else:
            _save_to_file(pack, stream, container, format, **kwargs)
    return pack_or_font

def _save_all(pack, where, format, **kwargs):
    """Save fonts to a container."""
    logging.info('Writing all to `%s`.', where.name)
    for font in pack:
        # generate unique filename
        name = font.name.replace(' ', '_')
        format = format or DEFAULT_TEXT_FORMAT
        filename = where.unused_name(name, format)
        try:
            with open_stream(filename, 'w', where=where) as stream:
                _save_to_file(Pack(font), stream, where, format, **kwargs)
        except BrokenPipeError:
            pass
        except Exception as e:
            logging.error('Could not save `%s`: %s', filename, e)
            #raise

def _save_to_file(pack, outfile, where, format, **kwargs):
    """Save fonts to a single file."""
    saver = savers.get_for(outfile, format=format, do_open=False)
    if not saver:
        raise FileFormatError('Cannot save to format `{}`.'.format(format))
    logging.info('Saving `%s` on `%s` as %s.', outfile.name, where.name, saver.name)
    saver(pack, outfile, where, **kwargs)


##############################################################################
# loader/saver registry

class ConverterRegistry(MagicRegistry):
    """Loader/Saver registry."""

    def __init__(self, func_name):
        """Set up registry and function name."""
        super().__init__()
        self._func_name = func_name

    def get_for_location(self, file, format='', where='', do_open=True):
        """Get loader/saver for font file location."""
        if not file and not where:
            return self.get_for(format=format)
        if where:
            # if container/file provided as string or steam, open them to check magic bytes
            with open_location(file, 'r', where=where) as (stream, container):
                # identify file type if possible
                return self.get_for(stream, format=format, do_open=do_open)
        else:
            return self.get_for(file, format=format, do_open=do_open)


    def get_for(self, file=None, format='', do_open=False):
        """
        Get loader/saver function for this format.
        infile must be a Stream or empty
        """
        converter = None
        if not format:
            converter = self.identify(file, do_open=do_open)
        if not converter:
            if format:
                converter = self[format]
            elif (
                    not file
                    or not file.name or file.name == '<stdout>'
                    or (do_open and maybe_text(file))
                ):
                converter = self[DEFAULT_TEXT_FORMAT]
            elif do_open:
                converter = self[DEFAULT_BINARY_FORMAT]
            else:
                if format:
                    msg = f'Format `{format}` not recognised'
                else:
                    msg = 'Could not determine format'
                    if file:
                        msg += f' from file name `{file.name}`'
                    msg += '. Please provide a -format option'
                raise ValueError(msg)
        return converter

    def get_args(self, file=None, format='', do_open=False):
        """
        Get loader/saver arguments for this format.
        infile must be a Stream or empty
        """
        converter = self.get_for(file, format, do_open)
        if not converter:
            return ScriptArgs()
        return converter.script_args

    def register(self, *formats, magic=(), name='', linked=None):
        """
        Decorator to register font loader/saver.

        *formats: extensions covered by registered function
        magic: magic sequences covered by the converter (no effect for savers)
        name: name of the format
        linked: loader/saver linked to saver/loader
        """
        register_magic = super().register

        def _decorator(original_func):
            # set script arguments
            funcname = self._func_name
            if name:
                funcname += f' {ARG_PREFIX}format={name}'
            _func = scriptable(
                original_func,
                # use the standard name, not that of the registered function
                name=funcname,
                # don't record history of loading from default format
                record=(DEFAULT_TEXT_FORMAT not in formats),
            )
            # register converter
            if linked:
                linked.linked = _func
                _func.name = name or linked.name
                _func.formats = formats or linked.formats
                _func.magic = magic or linked.magic
            else:
                _func.name = name
                _func.linked = linked
                _func.formats = formats
                _func.magic = magic
            # register magic sequences
            register_magic(_func.name, *_func.formats, magic=_func.magic)(_func)
            return _func

        return _decorator


loaders = ConverterRegistry('load')
savers = ConverterRegistry('save')
