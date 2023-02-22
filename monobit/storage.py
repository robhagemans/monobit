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
from .font import Font
from .pack import Pack
from .streams import Stream, StreamBase, KeepOpen
from .container import Directory
from .magic import MagicRegistry, FileFormatError, maybe_text
from .scripting import scriptable, ScriptArgs, ARG_PREFIX
from .basetypes import Any


DEFAULT_TEXT_FORMAT = 'yaff'
DEFAULT_BINARY_FORMAT = 'raw'


@contextmanager
def open_location(location, mode, overwrite=False):
    """Parse file specification, open stream."""
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not location:
        raise ValueError(f'No location provided.')
    if isinstance(location, str):
        location = Path(location)
    if isinstance(location, Path):
        container = Directory()
        with container:
            with open_stream_or_container(container, location, mode, overwrite) as (soc, subpath):
                yield soc, subpath
    elif isinstance(location, StreamBase):
        yield location, ''
    else:
        # we didn't open the file, so we don't own it
        # we neeed KeepOpen for when the yielded object goes out of scope in the caller
        yield Stream(KeepOpen(location), mode=mode), ''


@contextmanager
def open_stream_or_container(container, path, mode, overwrite):
    """Open stream or sub-container given container and path."""
    head, tail = find_next_node(container, path, mode)
    if str(head) == '.':
        # no next node found, path is leaf
        # this'll raise a FileNotFoundError if we're reading
        stream = container.open(tail, mode, overwrite)
        tail = ''
    else:
        stream = container.open(head, mode, overwrite)
    with stream:
        yield stream, tail


def find_next_node(container, path, mode):
    """Find the next node (container or file) in the path."""
    head, tail = _split_path(container, path)
    if mode == 'w':
        #if str(head) == '.':
        head2, tail = _split_path_suffix(tail)
        head /= head2
    return head, tail


def _split_path(container, path):
    """Pare back path until an existing ancestor is found."""
    path = Path(path)
    for head in (path, *path.parents):
        if head in container:
            tail = path.relative_to(head)
            return head, tail
    # nothing exists
    return Path('.'), path


def _split_path_suffix(path):
    """Pare forward path until a suffix is found."""
    for head in reversed((path, *path.parents)):
        if head.suffixes:
            tail = path.relative_to(head)
            return head, tail
    # no suffix
    return path, Path('.')


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


def load_stream(instream, format='', subpath='', **kwargs):
    """Load fonts from open stream."""
    # identify file type
    fitting_loaders = loaders.get_for(instream, format=format)
    if not fitting_loaders:
        message = f'Cannot load `{instream.name}`'
        if format:
            message += f': format specifier `{format}` not recognised'
        raise FileFormatError(message)
    for loader in fitting_loaders:
        instream.seek(0)
        logging.info('Loading `%s` as %s', instream.name, loader.format)
        try:
            if subpath and str(subpath) != '.':
                fonts = loader(instream, subpath=subpath, **kwargs)
            else:
                fonts = loader(instream, **kwargs)
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
                .decode('ascii', 'backsl hreplace')
            )
        return Pack(
            _font.modify(
                converter=CONVERTER_NAME,
                source_format=_font.source_format or loader.format,
                source_name=_font.source_name or filename
            )
            for _font in pack
        )
    raise FileFormatError('No fonts found in file')


def load_all(container, format='', **kwargs):
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

    outfile: output file (default: stdout)
    format: font file format
    overwrite: if outfile is a filename, allow overwriting existing file
    """
    pack = Pack(pack_or_font)
    outfile = outfile or sys.stdout
    if outfile == sys.stdout:
        # errors can occur if the strings we write contain surrogates
        # these may come from filesystem names using 'surrogateescape'
        sys.stdout.reconfigure(errors='replace')
    with open_location(outfile, 'w', overwrite=overwrite) as (stream, subpath):
        save_stream(pack, stream, format=format, subpath=subpath, **kwargs)
    return pack_or_font


def save_stream(pack, outstream, format='', subpath='', **kwargs):
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
    if subpath and str(subpath) != '.':
        saver(pack, outstream, subpath=subpath, **kwargs)
    else:
        saver(pack, outstream, **kwargs)


def save_all(pack, container, format, **kwargs):
    """Save fonts to a container."""
    logging.info('Writing all to `%s`.', container.name)
    for font in pack:
        # generate unique filename
        name = font.name.replace(' ', '_')
        # FIXME: confusing format name and suffix
        filename = container.unused_name(f'{name}.{format}')
        stream = container.open(filename, 'w')
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
            # set script arguments
            funcname = self._func_name
            if name:
                funcname += f' {ARG_PREFIX}format={name}'
            _func = scriptable(
                original_func,
                # use the standard name, not that of the registered function
                name=funcname,
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



@loaders.register(
    name='dir',
)
def load_dir(instream, subpath:str='', payload:str='', **kwargs):
    with Directory(instream) as container:
        if not subpath:
            return load_all(container, format=payload, **kwargs)
        with open_stream_or_container(container, subpath, mode='r', overwrite=False) as (stream, subpath):
            return load_stream(stream, format=payload, subpath=subpath, **kwargs)


@savers.register(linked=load_dir)
def save_zip(fonts, outstream, subpath:str='', payload:str='', **kwargs):
    with Directory(outstream, 'w') as container:
        if not subpath:
            return save_all(fonts, container, format=payload, **kwargs)
        with open_stream_or_container(container, subpath, mode='w', overwrite=False) as (stream, subpath):
            return save_stream(fonts, stream, format=payload, subpath=subpath, **kwargs)
