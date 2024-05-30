"""
monobit.storage.converters - load and save fonts

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import sys
import logging
import shlex
from pathlib import Path
from contextlib import contextmanager

from ..constants import MONOBIT
from ..core import Font, Pack
from ..base.struct import StructError
from ..plumbing import scriptable
from ..base import Any
from .magic import MagicRegistry, FileFormatError, maybe_text
from .location import open_location
from ..plumbing import convert_arguments, check_arguments
from .base import (
    DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT,
    loaders, savers
)


##############################################################################
# loading

@scriptable(wrapper=True, record=False)
def load(infile:Any='', *, format:str='', container_format:str='', **kwargs):
    """
    Read font(s) from file.

    infile: input file or path (default: stdin)
    format: input format (default: infer from magic number or filename)
    container_format: container/wrapper formats separated by . (default: infer from magic number or filename)
    """
    infile = infile or sys.stdin
    with open_location(
            infile, mode='r', container_format=container_format, argdict=kwargs,
        ) as location:
        if location.is_dir():
            return _load_dir(location, format=format, **location.argdict)
        else:
            return _load_stream(
                location.get_stream(), format=format, **location.argdict
            )


def _load_stream(instream, *, format='', **kwargs):
    """Load fonts from open stream."""
    tried_formats = []
    last_error = None
    for loader in _iter_funcs_from_registry(loaders, instream, format):
        tried_formats.append(loader.format)
        instream.seek(0)
        logging.info("Loading '%s' as format `%s`", instream.name, loader.format)
        try:
            fonts = loader(instream, **kwargs)
        except (FileFormatError, StructError) as e:
            logging.debug(e)
            last_error = e
        else:
            if fonts:
                break
            logging.debug(
                "No fonts found in '%s' as format `%s`.",
                instream.name, loader.format
            )
    else:
        if last_error:
            raise last_error
        message = f"Unable to read fonts from '{instream.name}': "
        if not tried_formats:
            message += f'format specifier `{format}` not recognised.'
        else:
            message += 'tried formats: ' + ', '.join(tried_formats)
        raise FileFormatError(message)
    # convert font or pack to pack
    pack = Pack(fonts)
    pack = _annotate_fonts_with_source(
        pack, instream.name, loader.format, kwargs
    )
    return pack


def _annotate_fonts_with_source(pack, filename, format, loader_kwargs):
    """Set source metadata on font pack."""
    filename = Path(filename).name
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
        for _k, _v in loader_kwargs.items()
    )
    loader_args = f' [{loader_args}]' if loader_args else ''
    return Pack(
        _font.modify(
            converter=MONOBIT,
            source_format=_font.source_format or f'{format}{loader_args}',
            source_name=_font.source_name or filename
        )
        for _font in pack
    )


def _iter_funcs_from_registry(registry, instream, format):
    """
    Iterate over and wrap functions stored in a MagicRegistry
    that fit a given stream and format.
    """
    # identify file type
    fitting_loaders = registry.get_for(instream, format=format)
    if not fitting_loaders:
        return
    for loader in fitting_loaders:
        # wrap loader function
        loader = convert_arguments(loader)
        loader = check_arguments(loader)
        yield loader
    return


def _load_dir(location, *, format='', **kwargs):
    """Open container and load container format, or recurse over container."""
    return _load_all(location, format=format, **kwargs)


def _load_all(root_location, *, format='', **kwargs):
    """Open container and load all fonts found in it into one pack."""
    logging.info('Reading all from `%s`.', root_location)
    packs = Pack()
    for location in root_location.walk():
        with location:
            logging.debug('Trying `%s`.', location)
            try:
                pack = _load_stream(
                    location.get_stream(),
                    format=format,
                )
            except FileFormatError as exc:
                logging.debug('Could not load `%s`: %s', location, exc)
            else:
                packs += Pack(pack)
    if not packs:
        raise FileFormatError('Unable to read fonts from container.')
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
        container_format:str='',
        **kwargs
    ):
    """
    Write font(s) to file.

    outfile: output file or path (default: stdout)
    format: font file format (default: infer from filename)
    container_format: container/wrapper formats separated by . (default: infer from filename)
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
    with open_location(
            outfile, mode='w', overwrite=overwrite,
            container_format=container_format,
            argdict=kwargs,
        ) as location:
        if location.is_dir():
            return _save_all(
                pack, location, format=format, overwrite=overwrite,
                **location.argdict
            )
        _save_stream(
            pack, location.get_stream(), format=format, **location.argdict
        )
    return pack_or_font


def _save_stream(pack, outstream, *, format='', **kwargs):
    """Save fonts to an open stream."""
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
    # apply wrappers to saver function
    saver = convert_arguments(saver)
    saver = check_arguments(saver)
    saver(pack, outstream, **kwargs)


def _save_all(
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
        try:
            with location.join(filename) as new_location:
                _save_stream(
                    Pack(font),
                    new_location.get_stream(),
                    format=format,
                    **kwargs
                )
        except FileFormatError as e:
            logging.error('Could not save `%s`: %s', filename, e)
