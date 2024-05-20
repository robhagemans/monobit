"""
monobit.storage.converters - load and save fonts

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import sys
import logging
import shlex
from pathlib import Path
from contextlib import contextmanager

from ..constants import VERSION, CONVERTER_NAME
from ..core import Font, Pack
from ..base.struct import StructError
from ..plumbing import scriptable, ARG_PREFIX
from ..base import Any
from .magic import ConverterRegistry, FileFormatError, maybe_text
from .location import resolve_location


DEFAULT_TEXT_FORMAT = 'yaff'
DEFAULT_BINARY_FORMAT = 'raw'

loaders = ConverterRegistry('load', DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT)
savers = ConverterRegistry('save', DEFAULT_TEXT_FORMAT)


##############################################################################
# loading

@scriptable(wrapper=True, record=False)
def load(infile:Any='', *, format:str='', **kwargs):
    """
    Read font(s) from file.

    infile: input file or path (default: stdin)
    format: input format (default: infer from magic number or filename)
    """
    infile = infile or sys.stdin
    location = resolve_location(infile, 'r')
    try:
        if location.is_dir():
            return load_all(location, format=format, **kwargs)
        with location.open() as stream:
            return load_stream(stream, format=format, **kwargs)
    finally:
        location.close()


def load_stream(instream, *, format='', subpath='', **kwargs):
    """Load fonts from open stream."""
    # identify file type
    fitting_loaders = loaders.get_for(instream, format=format)
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


def load_all(root_location, *, format='', **kwargs):
    """Open container and load all fonts found in it into one pack."""
    logging.info('Reading all from `%s`.', root_location)
    packs = Pack()
    for location in root_location.walk():
        logging.debug('Trying `%s`.', location)
        stream = location.open(mode='r')
        with stream:
            try:
                pack = load_stream(stream, format=format, **kwargs)
            except FileFormatError as exc:
                logging.debug('Could not load `%s`: %s', location, exc)
            else:
                packs += Pack(pack)
    return packs


def loop_load(instream, load_func):
    """
    Loop over files in enclosing container.
    instream should point to a file *inside* the container, not the container file.
    """
    # instream.where does not give the nearest enclosing container but the root where we're calling!
    # we also can't use a directory as instream as it would be recursively read
    container = instream.where
    glyphs = []
    for name in sorted(container):
        if Path(name).parent != Path(instream.name).parent:
            continue
        with container.open(name, mode='r') as stream:
            glyphs.append(load_func(stream))
    return glyphs


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
    print('save', outfile, format, overwrite, kwargs)
    pack = Pack(pack_or_font)
    outfile = outfile or sys.stdout
    if outfile == sys.stdout:
        # errors can occur if the strings we write contain surrogates
        # these may come from filesystem names using 'surrogateescape'
        sys.stdout.reconfigure(errors='replace')
    if not pack:
        raise ValueError('No fonts to save')
    location = resolve_location(outfile, mode='w')
    try:
        if location.is_dir():
            return save_all(
                pack, location, format=format, overwrite=overwrite, **kwargs
            )
        with location.open(mode='w', overwrite=overwrite) as stream:
            save_stream(pack, stream, format=format, **kwargs)
    finally:
        print('closing', vars(location))
        location.close()
    return pack_or_font


def save_stream(pack, outstream, *, format='', **kwargs):
    """Save fonts to an open stream."""
    print('save_stream', outstream, format, kwargs)
    format = format or DEFAULT_TEXT_FORMAT
    matching_savers = savers.get_for(outstream, format=format)
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
    logging.info('Saving `%s` as %s.', outstream.name, saver.format)
    # # special case - saving to directory
    # # we need to create the dir before opening a stream,
    # # or the stream will be a regular file
    # if isinstance(outstream, DirectoryStream) and format == 'dir':
    #     if not (Path(outstream.name) / subpath).exists():
    #         os.makedirs(Path(outstream.name) / subpath, exist_ok=True)
    #         overwrite = True
    saver(pack, outstream, **kwargs)


def save_all(
        pack, location, *, format='', template='', overwrite=False, **kwargs
    ):
    """Save fonts to a container."""
    format = format or DEFAULT_TEXT_FORMAT
    logging.info('Writing all to `%s`.', location)
    for font in pack:
        if format and not template:
            # generate name from format
            template = savers.get_template(format)
        # fill out template
        name = font.format_properties(template)
        # generate unique filename
        filename = location.unused_name(name.replace(' ', '_'))
        new_location = location.join(filename)
        stream = new_location.open(mode='w', overwrite=overwrite)
        try:
            with stream:
                save_stream(Pack(font), stream, format=format, **kwargs)
        except BrokenPipeError:
            pass
        except FileFormatError as e:
            logging.error('Could not save `%s`: %s', filename, e)
        # # FIXME - this needs to go somewhere else
        # new_location.container.close()
