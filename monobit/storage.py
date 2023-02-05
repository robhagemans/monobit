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
from .container import open_container, Container, Directory
from .font import Font
from .pack import Pack
from .streams import Stream, StreamBase, KeepOpen
from .magic import MagicRegistry, FileFormatError, maybe_text
from .scripting import scriptable, ScriptArgs, ARG_PREFIX
from .basetypes import Any


DEFAULT_TEXT_FORMAT = 'yaff'
DEFAULT_BINARY_FORMAT = 'raw'


@contextmanager
def open_location(file, mode, where=None, overwrite=False):
    """Parse file specification, open file and container."""
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not file and not where:
        raise ValueError(f'No location provided.')
    if isinstance(file, str):
        file = Path(file)
    # interpret incomplete arguments
    if isinstance(file, Path):
        if file.is_dir():
            where = file
            file = None
        elif not where:
            where = file.parent
            file = Path(file.name)
    container = open_container(where, mode, overwrite=True)
    with container:
        if not file:
            stream = container
            yield stream, container
        elif isinstance(file, Path):
            stream = container.open(file, mode=mode)
            with stream:
                yield stream, container
        else:
            # we didn't open the stream, so we don't own it
            # we neeed KeepOpen for when the yielded object goes out of scope in the caller
            stream = Stream(KeepOpen(file), mode=mode)
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
        return _load_from_file(stream, container, format, **kwargs)

def _load_from_file(instream, where, format, **kwargs):
    """Open file and load font(s) from it."""
    # identify file type
    fitting_loaders = loaders.get_for(instream, format=format)
    if not fitting_loaders:
        raise FileFormatError(f'Cannot load from format `{format}`')
    for loader in fitting_loaders:
        instream.seek(0)
        logging.info('Loading `%s` on `%s` as %s', instream.name, where.name, loader.name)
        try:
            fonts = loader(instream, where, **kwargs)
        except FileFormatError as e:
            logging.debug(e)
            continue
        if not fonts:
            logging.debug('No fonts found in file.')
            continue
        # convert font or pack to pack
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
    raise FileFormatError('No fonts found in file')


##############################################################################
# saving



#@scriptable(unknown_args='passthrough', record=False, pack_operation=True)
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
        _save_to_file(pack, stream, container, format, **kwargs)
    return pack_or_font

def _save_to_file(pack, outfile, where, format, **kwargs):
    """Save fonts to a single file."""
    matching_savers = savers.get_for(outfile, format=format)
    if not matching_savers:
        raise ValueError(f'Format specification `{format}` not recognised')
    if len(matching_savers) > 1:
        raise ValueError(
            f"Format for filename '{outfile.name}' is ambiguous: "
            f'specify -format with one of the values '
            f'({", ".join(_s.name for _s in matching_savers)})'
        )
    saver, *_ = matching_savers
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

    def get_for_location(self, file, format='', where=''):
        """Get loader/saver for font file location."""
        if not file and not where:
            return self.get_for(format=format)
        if where:
            # if container/file provided as string or steam, open them to check magic bytes
            with open_location(file, 'r', where=where) as (stream, container):
                # identify file type if possible
                return self.get_for(stream, format=format)
        else:
            return self.get_for(file, format=format)


    def get_for(self, file=None, format=''):
        """
        Get loader/saver function for this format.
        infile must be a Stream or empty
        """
        converter = ()
        if not format:
            converter = self.identify(file)
        if not converter:
            if format:
                try:
                    converter = (self._names[format],)
                except KeyError:
                    converter = self._suffixes.get(format,  ())
            elif (
                    not file
                    or not file.name or file.name == '<stdout>'
                    or (file.mode == 'r' and maybe_text(file))
                ):
                logging.debug(
                    'Fallback to default `%s` format', DEFAULT_TEXT_FORMAT
                )
                converter = (self._names[DEFAULT_TEXT_FORMAT],)
            elif file.mode == 'r':
                converter = (self._names[DEFAULT_BINARY_FORMAT],)
                logging.debug(
                    'Fallback to default `%s` format', DEFAULT_BINARY_FORMAT
                )
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
            register_magic(*_func.formats, magic=_func.magic, name=_func.name)(_func)
            return _func

        return _decorator


loaders = ConverterRegistry('load')
savers = ConverterRegistry('save')


@loaders.register(name='dir')
def load_dir(instream, where=None):
    return Directory(instream).load()

@savers.register(linked=load_dir)
def save_dir(fonts, outstream, where=None):
    return Directory(outstream).save(fonts)
