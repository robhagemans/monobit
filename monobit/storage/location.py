import logging
from pathlib import Path

from monobit.storage.magic import FileFormatError, MagicRegistry
from monobit.storage.containers.directory import Directory
from monobit.base.struct import StructError

from .streams import StreamBase, Stream, KeepOpen
from .wrappers.compressors import WRAPPERS
from .containers.container import CONTAINERS


def open_location(stream_or_location, mode='r', format=''):
    """
    Open stream on given location, resolving nested containers and wrappers.
    """
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not stream_or_location:
        raise ValueError(f'No location provided.')
    if isinstance(stream_or_location, (str, Path, Location)):
        location_spec = stream_or_location
        if isinstance(location_spec, str):
            location_spec = Path(location_spec)
        if isinstance(location_spec, Path):
            root = Path(location_spec.root)
            subpath = location_spec.relative_to(root)
            location = Location(Directory(root), subpath)
        else:
            location = location_spec
        location = location.resolve(format)
        return location
    # stream_or_location is a file-like object
    if isinstance(stream_or_location, StreamBase):
        stream = stream_or_location
    else:
        # we didn't open the file, so we don't own it
        # we neeed KeepOpen for when the yielded object goes out of scope in the caller
        stream = Stream(KeepOpen(stream_or_location), mode=mode)
    location = Location()
    stream = location.unwrap_stream(stream, format)
    return stream


class Location:

    def __init__(self, container=None, subpath=''):
        if container is None:
            container = Directory()
        self.container = container
        self.subpath = subpath
        self._open_streams = []

    def _find_next_node(self):
        """Find the next node (container or file) in the path."""
        head, tail = _split_path(self.container, self.subpath)
        # if mode == 'w' and not head.suffixes:
        #     head2, tail = _split_path_suffix(tail)
        #     head /= head2
        return head, tail

    def resolve(self, format=''):
        """
        Convert location to subpath on innermost container and open stream.
        """
        logging.debug('Resolving %s, %s', self.container, self.subpath)
        head, tail = self._find_next_node()
        logging.debug('Head: %s  Tail: %s', head, tail)
        if str(head) == '.':
            # no next node found, path is leaf
            return self
        # get outermost element in compound format
        new_format_spec, _, outer_format = format.rpartition('.')
        # identify container/wrapper type on head
        stream = self.container.open(head, mode='r') #, mode, overwrite)
        self._open_streams.append(stream)
        # FIXME may need multiple formats to unwrap
        stream_or_container = self.unwrap_stream(stream, format=outer_format)
        if isinstance(stream_or_container, StreamBase):
            if not tail or str(tail) == '.':
                return stream_or_container
            # not a container but we still have a subpath - error
            raise FileFormatError(
                f"Cannot resolve subpath '{tail}' "
                f"on non-container stream '{stream_or_container.name}'"
            )
        location = Location(stream_or_container, subpath=tail)
        return location.resolve(format=new_format_spec)

    def unwrap_stream(self, stream, format=''):
        """
        Open one or more wrappers until an unwrapped stream is found.
        Returns Stream or Container object.
        """
        while True:
            try:
                unwrapped = _open_wrapper(stream, format=format)
            except FileFormatError:
                # not a wrapper
                break
            else:
                self._open_streams.append(unwrapped)
                stream = unwrapped
        try:
            return _open_container(stream, format=format)
        except FileFormatError:
            pass
        return stream


def _open_wrapper(instream, *, format='', **kwargs):
    """Open wrapper on open stream."""
    # identify file type
    fitting_loaders = WRAPPERS.get_for(instream, format=format)
    last_error = None
    for loader in fitting_loaders:
        instream.seek(0)
        logging.info('Opening `%s` as wrapper format %s', instream.name, loader.format)
        try:
            # returns unwrapped stream
            return loader(instream, **kwargs)
        except (FileFormatError, StructError) as e:
            logging.debug(e)
            last_error = e
            continue
    if last_error:
        raise last_error
    message = f'Cannot open wrapper `{instream.name}`'
    if format:
        message += f': format specifier `{format}` not recognised'
    raise FileFormatError(message)


def _open_container(instream, *, format='', **kwargs):
    """Open container on open stream."""
    # identify file type
    fitting_loaders = CONTAINERS.get_for(instream, format=format)
    last_error = None
    for loader in fitting_loaders:
        instream.seek(0)
        logging.info('Opening `%s` as container format %s', instream.name, loader.format)
        try:
            # returns container object
            return loader(instream, **kwargs)
        except (FileFormatError, StructError) as e:
            logging.debug(e)
            last_error = e
            continue
    if last_error:
        raise last_error
    message = f'Cannot open container `{instream.name}`'
    if format:
        message += f': format specifier `{format}` not recognised'
    raise FileFormatError(message)



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
