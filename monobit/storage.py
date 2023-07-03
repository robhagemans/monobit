"""
monobit.storage - load and save fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import sys
import logging
import shlex
from pathlib import Path
from contextlib import contextmanager

from .constants import VERSION, CONVERTER_NAME
from .font import Font
from .pack import Pack
from .streams import Stream, StreamBase, KeepOpen, DirectoryStream
from .magic import MagicRegistry, FileFormatError, maybe_text
from .struct import StructError
from .scripting import scriptable, ScriptArgs, ARG_PREFIX
from .basetypes import Any


DEFAULT_TEXT_FORMAT = 'yaff'
DEFAULT_BINARY_FORMAT = 'raw'


@contextmanager
def open_location(location, mode):
    """Parse file specification, open stream."""
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not location:
        raise ValueError(f'No location provided.')
    if isinstance(location, str):
        location = Path(location)
    if isinstance(location, Path):
        root = Path(location.root)
        subpath = location.relative_to(root)
        with DirectoryStream(root, mode) as stream:
            yield stream, subpath
    elif isinstance(location, StreamBase):
        yield location, ''
    else:
        # we didn't open the file, so we don't own it
        # we neeed KeepOpen for when the yielded object goes out of scope in the caller
        yield Stream(KeepOpen(location), mode=mode), ''


##############################################################################
# loading

@scriptable(wrapper=True, record=False)
def load(infile:Any='', *, format:str='', **kwargs):
    """
    Read font(s) from file.

    infile: input file (default: stdin)
    format: input format (default: infer from magic number or filename)
    """
    infile = infile or sys.stdin
    with open_location(infile, 'r') as (stream, subpath):
        return load_stream(stream, format=format, subpath=subpath, **kwargs)


def load_stream(instream, *, format='', subpath='', **kwargs):
    """Load fonts from open stream."""
    new_format, _, outer = format.rpartition('.')
    # identify file type
    fitting_loaders = loaders.get_for(instream, format=outer)
    if not fitting_loaders:
        message = f'Cannot load `{instream.name}`'
        if format:
            message += f': format specifier `{format}` not recognised'
        raise FileFormatError(message)
    errors = {}
    last_error = None
    for loader in fitting_loaders:
        instream.seek(0)
        logging.info('Loading `%s` as %s', instream.name, loader.format)
        # update format name, removing the most recently found wrapper format
        if outer == loader.format:
            format = new_format
        # only provide subpath and format args if non-empty
        if Path(subpath) != Path('.'):
            kwargs['subpath'] = subpath
        if format:
            kwargs['format'] = format
        try:
            fonts = loader(instream, **kwargs)
        except (FileFormatError, StructError) as e:
            logging.debug(e)
            errors[format] = e
            last_error = e
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
        # source format argumets
        loader_args = ' '.join(
            f'{_k.replace("_", "-")}={shlex.join((str(_v),))}'
            for _k, _v in kwargs.items()
            if _k != 'subpath'
        )
        loader_args = f' [{loader_args}]' if loader_args else ''
        return Pack(
            _font.modify(
                converter=CONVERTER_NAME,
                source_format=_font.source_format or f'{loader.format}{loader_args}',
                source_name=_font.source_name or filename
            )
            for _font in pack
        )
    if last_error:
        raise last_error
    raise FileFormatError('Unable to read fonts from file')


def load_all(container, *, format='', **kwargs):
    """Open container and load all fonts found in it into one pack."""
    logging.info('Reading all from `%s`.', container.name)
    packs = Pack()
    names = list(container)
    for name in container:
        logging.debug('Trying `%s` on `%s`.', name, container.name)
        stream = container.open(name, 'r')
        with stream:
            try:
                pack = load_stream(
                    stream, format=format, **kwargs
                )
            except FileFormatError as exc:
                logging.debug('Could not load `%s`: %s', name, exc)
            else:
                packs += Pack(pack)
    return packs


##############################################################################
# saving

@scriptable(wrapper=True, record=False, pack_operation=True)
def save(
        pack_or_font,
        outfile:Any='', *,
        format:str='', overwrite:bool=False,
        **kwargs
    ):
    """
    Write font(s) to file.

    outfile: output file or path (default: stdout)
    format: font file format
    overwrite: if outfile is a path, allow overwriting existing file
    """
    pack = Pack(pack_or_font)
    outfile = outfile or sys.stdout
    if outfile == sys.stdout:
        # errors can occur if the strings we write contain surrogates
        # these may come from filesystem names using 'surrogateescape'
        sys.stdout.reconfigure(errors='replace')
    if not pack:
        raise ValueError('No fonts to save')
    with open_location(outfile, 'w') as (stream, subpath):
        save_stream(
            pack, stream,
            format=format, subpath=subpath, overwrite=overwrite,
            **kwargs
        )
    return pack_or_font


def save_stream(
        pack, outstream, *,
        format='', subpath='', overwrite=False,
        **kwargs
    ):
    """Save fonts to an open stream."""
    new_format, _, outer = format.rpartition('.')
    matching_savers = savers.get_for(outstream, format=outer)
    if not matching_savers:
        if format:
            raise ValueError(f'Format specification `{format}` not recognised')
        else:
            raise ValueError(
                f'Could not infer output file format from filename `{outstream.name}`, '
                'please specify -format'
            )
    if len(matching_savers) > 1:
        raise ValueError(
            f"Format for output filename '{outstream.name}' is ambiguous: "
            f'specify -format with one of the values '
            f'({", ".join(_s.format for _s in matching_savers)})'
        )
    saver, *_ = matching_savers
    if Path(subpath) == Path('.'):
        logging.info('Saving `%s` as %s.', outstream.name, saver.format)
    else:
        logging.info(
            'Saving `%s` on `%s` as %s.', subpath, outstream.name, saver.format
        )
    # special case - saving to directory
    # we need to create the dir before opening a stream,
    # or the stream will be a regular file
    if isinstance(outstream, DirectoryStream) and format == 'dir':
        if not (Path(outstream.name) / subpath).exists():
            os.makedirs(Path(outstream.name) / subpath, exist_ok=True)
            overwrite = True
    # update format name, removing the most recently found wrapper format
    if outer == saver.format:
        format = new_format
    # only provide subpath and format args if non-empty
    if Path(subpath) != Path('.'):
        kwargs['subpath'] = subpath
        kwargs['overwrite'] = overwrite
    if format:
        kwargs['format'] = format
    saver(pack, outstream, **kwargs)


def save_all(
        pack, container, *,
        format=DEFAULT_TEXT_FORMAT, template='',
        overwrite=False,
        **kwargs
    ):
    """Save fonts to a container."""
    logging.info('Writing all to `%s`.', container.name)
    for font in pack:
        if format and not template:
            # generate name from format
            template = savers.get_template(format)
        # fill out template
        name = font.format_properties(template)
        # generate unique filename
        filename = container.unused_name(name.replace(' ', '_'))
        stream = container.open(filename, 'w', overwrite=overwrite)
        try:
            with stream:
                save_stream(Pack(font), stream, format=format, **kwargs)
        except BrokenPipeError:
            pass
        except FileFormatError as e:
            logging.error('Could not save `%s`: %s', filename, e)


##############################################################################
# loader/saver registry

class ConverterRegistry(MagicRegistry):
    """Loader/Saver registry."""

    def register(
            self, name='', magic=(), patterns=(),
            linked=None, **kwargs
        ):
        """
        Decorator to register font loader/saver.

        name: unique name of the format
        magic: magic sequences for this format (no effect for savers)
        patterns: filename patterns for this format
        linked: loader/saver linked to saver/loader
        """
        register_magic = super().register

        def _decorator(original_func):
            _func = scriptable(
                original_func,
                record=False,
                **kwargs
            )
            # register converter
            if linked:
                format = name or linked.format
                _func.magic = magic or linked.magic
                _func.patterns = patterns or linked.patterns
            else:
                format = name
                _func.magic = magic
                _func.patterns = patterns
            # register magic sequences
            register_magic(
                name=format,
                magic=_func.magic,
                patterns=_func.patterns,
            )(_func)
            return _func

        return _decorator


loaders = ConverterRegistry('load', DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT)
savers = ConverterRegistry('save', DEFAULT_TEXT_FORMAT)
