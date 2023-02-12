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
from .container import Container, Directory
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
            with open_stream_or_container(container, location, mode) as soc:
                yield soc
    elif isinstance(location, (StreamBase, Container)):
        yield location
    else:
        # we didn't open the file, so we don't own it
        # we neeed KeepOpen for when the yielded object goes out of scope in the caller
        yield Stream(KeepOpen(location), mode=mode)


@contextmanager
def open_stream_or_container(container, path, mode):
    """Open stream or sub-container given container and path."""
    head, tail = _split_path(container, path)
    if mode == 'w' and str(head) == '.':
        head2, tail = _split_path_suffix(tail)
        head /= head2
    if str(head) == '.':
        # base condition
        next_container = None
        # this'll raise a FileNotFoundError if we're reading
        stream = container.open(tail, mode)
    else:
        stream = container.open(head, mode)
        try:
            next_container = open_container(stream, mode)
        except FileFormatError as e:
            logging.debug(e)
            # not a container file, must be leaf node
            if str(tail) != '.':
                raise
            next_container = None
    if not next_container:
        with stream:
            yield stream
        return
    elif str(tail) == '.':
        # special case: leaf node is container file
        # return the whole container instead of a stream
        # caller can decide to extract the whole container
        with next_container:
            yield next_container
    else:
        # recursively open containers-in-containers
        with next_container:
            with open_stream_or_container(next_container, tail, mode) as soc:
                yield soc


def _split_path(container, path):
    """Pare back path until an existing ancestor is found."""
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


def open_container(stream, mode, format=''):
    """Interpret stream as (archive) container."""
    # Directory.open() may return Directory objects (which are Container instances)
    if hasattr(stream, 'open'):
        return stream
    fitting_containers = containers.get_for(stream, format=format)
    for opener in fitting_containers:
        try:
            container = opener(stream, mode)
        except FileFormatError:
            continue
        else:
            return container
    message = (
        f'Cannot open `{stream.name}` as container: '
        'format not recognised'
    )
    if format:
        message += f' of format `{format}`'
    raise FileFormatError(message)


##############################################################################
# loading

@scriptable(unknown_args='passthrough', record=False)
def load(infile:Any='', *, format:str='', **kwargs):
    """
    Read font(s) from file.

    infile: input file (default: stdin)
    format: input format (default: infer from magic number or filename)
    """
    infile = infile or sys.stdin
    with open_location(infile, 'r') as stream:
        return load_stream(stream, format, **kwargs)


def load_stream(instream, format='', **kwargs):
    """Load fonts from open stream."""
    # special case - directory or container object supplied
    if hasattr(instream, 'open'):
        return load_all(instream, format=format)
    # stream supplied and link to member - only works if stream holds a container
    # identify file type
    fitting_loaders = loaders.get_for(instream, format=format)
    if not fitting_loaders:
        message = f'Cannot load `{instream.name}`'
        if format:
            message += f' as format `{format}`'
        raise FileFormatError(message)
    for loader in fitting_loaders:
        instream.seek(0)
        logging.info('Loading `%s` as %s', instream.name, loader.name)
        try:
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

@scriptable(unknown_args='passthrough', record=False, pack_operation=True)
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
    with open_location(outfile, 'w', overwrite=overwrite) as stream:
        save_stream(pack, stream, format, **kwargs)
    return pack_or_font


def save_stream(pack, outstream, format='', **kwargs):
    """Save fonts to an open stream."""
    # special case - directory or container object supplied
    if hasattr(outstream, 'open'):
        return save_all(pack, outstream)
    matching_savers = savers.get_for(outstream, format=format)
    if not matching_savers:
        raise ValueError(f'Format specification `{format}` not recognised')
    if len(matching_savers) > 1:
        raise ValueError(
            f"Format for filename '{outstream.name}' is ambiguous: "
            f'specify -format with one of the values '
            f'({", ".join(_s.name for _s in matching_savers)})'
        )
    saver, *_ = matching_savers
    logging.info('Saving `%s` as %s.', outstream.name, saver.name)
    saver(pack, outstream, **kwargs)


def save_all(pack, container, **kwargs):
    """Save fonts to a container."""
    suffixes = Path(container.name).suffixes
    if len(suffixes) > 1:
        format = suffixes[-2][1:]
    else:
        format = ''
    logging.info('Writing all to `%s`.', container.name)
    for font in pack:
        # generate unique filename
        name = font.name.replace(' ', '_')
        filename = container.unused_name(name, format)
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

    def __init__(self, func_name, default_text='', default_binary=''):
        """Set up registry and function name."""
        super().__init__()
        self._func_name = func_name
        self._default_text = default_text
        self._default_binary = default_binary

    def get_for_location(self, file, mode, format=''):
        """Get loader/saver for font file location."""
        if not file:
            return self.get_for(format=format)
        with open_location(file, mode) as stream:
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
            elif ((
                        not file
                        or not file.name or file.name == '<stdout>'
                        or (file.mode == 'r' and maybe_text(file))
                    )
                    and self._default_text
                ):
                logging.debug(
                    'Fallback to default `%s` format', self._default_text
                )
                converter = (self._names[self._default_text],)
            elif file.mode == 'r' and self._default_binary:
                converter = (self._names[self._default_binary],)
                logging.debug(
                    'Fallback to default `%s` format', self._default_binary
                )
            else:
                if format:
                    raise ValueError( f'Format `{format}` not recognised')
                converter = ()
        return converter

    def register(self, *formats, magic=(), name='', linked=None, wrapper=False):
        """
        Decorator to register font loader/saver.

        *formats: extensions covered by registered function
        magic: magic sequences covered by the converter (no effect for savers)
        name: name of the format
        linked: loader/saver linked to saver/loader
        wrapper: this is a single-file wrapper format, enable argument passthrough
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
                record=(name=='load' and DEFAULT_TEXT_FORMAT not in formats),
                unknown_args='passthrough' if wrapper else 'raise',
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


loaders = ConverterRegistry('load', DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT)
savers = ConverterRegistry('save', DEFAULT_TEXT_FORMAT, DEFAULT_BINARY_FORMAT)
containers = ConverterRegistry('open')
