"""
monobit.storage.fontfiles - load and save fonts

(c) 2019--2026 Rob Hagemans
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
from ..plumbing import scriptable, manage_arguments
from ..base import Any, FileFormatError, UnsupportedError
from .magic import MagicRegistry, iter_funcs_from_registry
from .location import open_location
from .base import (
    DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT,
    loaders, savers, container_loaders, container_savers
)


def load_plugins():
    """Ensure plugins get loaded."""
    from . import containerformats
    from . import fontformats
    from . import wrapperformats


##############################################################################
# loading

@scriptable(passthrough=loaders)
def load(infile:Any='', *, format:str='', container_format:str='', match_case:bool=False, **kwargs):
    """
    Read font(s) from file.

    infile: input file or path (default: stdin)
    format: input format (default: infer from magic number or filename)
    container_format: container/wrapper formats separated by . (default: infer from magic number or filename)
    match_case: interpret path as case-sensitive (if file system supports it; default: False)
    """
    load_plugins()
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
    for loader in iter_funcs_from_registry(loaders, instream, format):
        tried_formats.append(loader.format)
        instream.seek(0)
        logging.info("Loading '%s' as format `%s`", instream.name, loader.format)
        try:
            fonts = loader(instream, **kwargs)
        except FileFormatError as e:
            logging.debug(e)
        else:
            if fonts:
                break
            logging.debug(
                "No fonts found in '%s' as format `%s`.",
                instream.name, loader.format
            )
    else:
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


def _sanitise_filesystem_name(filename):
    """
    If the source filename contains surrogate-escaped non-utf8 bytes
    preserve the byte values as backslash escapes
    """
    filename = str(filename)
    try:
        filename.encode('utf-8')
    except UnicodeError:
        filename = (
            filename.encode('utf-8', 'surrogateescape')
            .decode('ascii', 'backslashreplace')
        )
    return filename


def _annotate_fonts_with_source(
        fonts, filename, location, format, loader_kwargs
    ):
    """Set source metadata on font pack."""
    # convert font or pack to pack
    pack = Pack(fonts)
    filename = _sanitise_filesystem_name(Path(filename).name)
    filepath = _sanitise_filesystem_name(location.relative_path)
    if filepath == '.':
        filepath = ''
    # source format arguments
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
            source_path=_font.source_path or filepath,
        )
        for _font in pack
    )


def _load_container(location, *, format='', **kwargs):
    """Load from a container."""
    for loader in iter_funcs_from_registry(
            container_loaders, instream=None, format=format
        ):
        logging.info("Loading '%s' as container format `%s`", location.path, loader.format)
        try:
            fonts = loader(location, **kwargs)
        except FileFormatError as e:
            logging.debug(e)
            continue
        spec_msg = f"as format {loader.format}"
        pack = _annotate_fonts_with_source(
            fonts, location.path, location, loader.format, kwargs
        )
        break
    else:
        pack = load_all(location, format=format, **kwargs)
        spec_msg = 'all'
    if not pack:
        raise FileFormatError(
            f"No fonts found in '{location.path}' while loading {spec_msg}."
        )
    return pack


def load_all(root_location, *, format='', **kwargs):
    """Open container and load all fonts found in it into one pack."""
    load_plugins()
    logging.info('Reading all from `%s`.', root_location)
    packs = Pack()
    for location in root_location.walk():
        with location:
            logging.debug('Trying `%s`.', location)
            try:
                pack = _load_stream(
                    location.get_stream(), format=format, **kwargs
                )
            except (ValueError, EnvironmentError, FileFormatError, UnsupportedError) as exc:
                logging.debug('Could not load `%s`: %s', location, exc)
            else:
                packs += Pack(pack)
    if not packs:
        raise FileFormatError('Unable to read fonts from container.')
    return packs


##############################################################################
# saving

@scriptable(passthrough=savers, pack_operation=True, output=True)
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
    load_plugins()
    return output_pack_or_font(
        pack_or_font, outfile,
        format=format, overwrite=overwrite,
        container_format=container_format, registry=savers,
        **kwargs
    )


def output_pack_or_font(
        pack_or_font,
        outfile, *,
        format, overwrite,
        container_format,
        registry,
        **kwargs
    ):
    pack = Pack(pack_or_font)
    outfile = outfile or sys.stdout
    if outfile == sys.stdout:
        # errors can occur if the strings we write contain surrogates
        # these may come from filesystem names using 'surrogateescape'
        sys.stdout.reconfigure(errors='replace')
    if not pack:
        raise ValueError('No fonts to output')
    make_dir = format in container_savers.get_formats()
    with open_location(
            outfile, mode='w', overwrite=overwrite,
            container_format=container_format,
            argdict=kwargs,
            make_dir=make_dir,
        ) as location:
        if location.is_dir():
            _output_to_container(
                pack, location, format=format, registry=registry,
                **location.argdict
            )
        else:
            _output_to_stream(
                pack, location.get_stream(), format=format, registry=registry,
                **location.argdict
            )
    return pack_or_font


def _output_to_stream(pack, outstream, *, format, registry, **kwargs):
    """Save fonts to an open stream."""
    matching = registry.get_for(outstream, format=format)
    if not matching:
        if format:
            raise ValueError(f'Format specification `{format}` not recognised')
        else:
            raise ValueError(
                f'Could not infer output file format from filename {outstream.name}, '
                'please specify -format'
            )
    if len(matching) > 1:
        raise ValueError(
            f"Format for output filename {outstream.name} is ambiguous: "
            f'specify -format with one of the values '
            f'({", ".join(_s.format for _s in matching)})'
        )
    outputter, *_ = matching
    logging.info('Outputting %s as format `%s`.', outstream.name, outputter.format)
    # apply wrappers to saver function
    outputter = manage_arguments(outputter)
    outputter(pack, outstream, **kwargs)


def _output_to_container(pack, location, *, format, registry, **kwargs):
    """Save font(s) to container."""
    for saver in iter_funcs_from_registry(
            container_savers, instream=None, format=format
        ):
        logging.info(
            "Outputting %s as container format `%s`", location.path, saver.format
        )
        saver(pack, location, **kwargs)
        break
    else:
        _output_all(pack, location, format=format, registry=registry, **kwargs)


def _output_all(pack, location, *, format, registry, template='', **kwargs):
    """Save fonts to a container."""
    format = format or DEFAULT_TEXT_FORMAT
    logging.info('Outputting all to %s.', location)
    for font in pack:
        if format and not template:
            # generate name from format
            template = registry.get_template(format)
        # fill out template
        name = font.format_properties(template)
        # sanitise name
        name = ''.join(c for c in name if 0x20 <= ord(c) < 0x7f or ord(c) > 0xa0)
        name = name.replace(' ', '_')
        # generate unique filename
        filename = location.unused_name(name)
        try:
            with location.join(filename) as new_location:
                _output_to_stream(
                    Pack(font),
                    new_location.get_stream(),
                    format=format,
                    registry=registry,
                    **kwargs
                )
        except (FileFormatError, UnsupportedError) as e:
            logging.error('Could not output %s: %s', filename, e)
