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
from ..plumbing import scriptable
from ..base import Any
from .magic import MagicRegistry, FileFormatError, maybe_text
from .location import open_location
from ..plumbing import convert_arguments, check_arguments
from .base import (
    DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT,
    loaders, savers, container_loaders, container_savers
)


##############################################################################
# loading

@scriptable(wrapper=True, record=False)
def load(infile:Any='', *, format:str='', container_format:str='', match_case:bool=False, **kwargs):
    """
    Read font(s) from file.

    infile: input file or path (default: stdin)
    format: input format (default: infer from magic number or filename)
    container_format: container/wrapper formats separated by . (default: infer from magic number or filename)
    match_case: interpret path as case-sensitive (if file system supports it; default: False)
    """
    infile = infile or sys.stdin
    with open_location(
            infile, mode='r', match_case=match_case,
            container_format=container_format, argdict=kwargs,
        ) as location:
        if location.is_dir():
            return _load_container(
                location, format=format, **location.argdict
            )
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
        except FileFormatError as e:
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
    pack = _annotate_fonts_with_source(
        fonts, instream.name, instream.where, loader.format, kwargs
    )
    return pack


def _annotate_fonts_with_source(
        fonts, filename, location, format, loader_kwargs
    ):
    """Set source metadata on font pack."""
    # convert font or pack to pack
    pack = Pack(fonts)
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
            source_name=_font.source_name or filename,
            source_path=str(location.path),
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
    for loader in fitting_loaders:
        yield _wrap_converter_func(loader)
    return


def _wrap_converter_func(loader):
    loader = convert_arguments(loader)
    loader = check_arguments(loader)
    return loader


def _load_container(location, *, format='', **kwargs):
    """Load from a container."""
    try:
        loaders = container_loaders.get_for(format=format)
    except ValueError:
        loaders = None
    if not loaders:
        pack = load_all(location, format=format, **kwargs)
        spec_msg = 'all'
    else:
        loader = _wrap_converter_func(loaders[0])
        logging.info("Loading '%s' as container format `%s`", location.path, loader.format)
        fonts = loader(location, **kwargs)
        spec_msg = f"as format {loader.format}"
        pack = _annotate_fonts_with_source(
            fonts, location.path, location, loader.format, kwargs
        )
    if not pack:
        raise FileFormatError(
            f"No fonts found in '{location.path}' while loading {spec_msg}."
        )
    return pack


def load_all(root_location, *, format='', **kwargs):
    """Open container and load all fonts found in it into one pack."""
    logging.info('Reading all from `%s`.', root_location)
    packs = Pack()
    for location in root_location.walk():
        with location:
            logging.debug('Trying `%s`.', location)
            try:
                pack = _load_stream(
                    location.get_stream(), format=format, **kwargs
                )
            except FileFormatError as exc:
                logging.debug('Could not load `%s`: %s', location, exc)
            else:
                packs += Pack(pack)
    if not packs:
        raise FileFormatError('Unable to read fonts from container.')
    return packs


def loop_load(location, load_func):
    """Loop over per-glyph files in container."""
    glyphs = []
    for name in sorted(location.iter_sub('')):
        with location.open(name, mode='r') as stream:
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
            _save_container(
                pack, location, format=format, **location.argdict
            )
        else:
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
    saver = _wrap_converter_func(saver)
    saver(pack, outstream, **kwargs)


def _save_container(pack, location, *, format, **kwargs):
    """Save font(s) to container."""
    try:
        savers = container_savers.get_for(format=format)
    except ValueError:
        savers = None
    if not savers:
        save_all(pack, location, format=format, **kwargs)
    else:
        saver = _wrap_converter_func(savers[0])
        logging.info(
            "Saving '%s' as container format `%s`", location.path, saver.format
        )
        saver(pack, location, **kwargs)


def save_all(
        pack, location, *, format='', template='', **kwargs
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
