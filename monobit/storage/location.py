import logging
from pathlib import Path

from monobit.storage.magic import FileFormatError, MagicRegistry
from monobit.storage.containers.directory import Directory
from monobit.base.struct import StructError

from .streams import StreamBase, Stream, KeepOpen
from .wrappers.compressors import WRAPPERS
from .containers.container import CONTAINERS


def resolve_location(stream_or_location, mode='r'):
    """
    Point to given location, resolving nested containers and wrappers.
    """
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not stream_or_location:
        raise ValueError(f'No location provided.')
    if isinstance(stream_or_location, (str, Path)):
        location = Location.from_path(stream_or_location)
        location = location.resolve()
        return location
    # stream_or_location is a file-like object
    location = Location.from_stream(stream_or_location)
    location = location.unwrap_stream()
    return location


class Location:

    def __init__(self, container, subpath=''):
        # self.parent = None
        self.container = container
        self.subpath = Path(subpath)
        self._target_stream = None

    @classmethod
    def from_path(cls, path):
        """Create from path-like or string."""
        path = Path(path)
        root = path.anchor or '.'
        subpath = path.relative_to(root)
        return cls(container=Directory(root), subpath=subpath)

    @classmethod
    def from_stream(cls, stream):
        """Create from file-like object."""
        location = cls(container=None, subpath='')
        # FIXME track parent Location to stop open parent streams getting closed
        if not isinstance(stream, StreamBase):
            # we didn't open the file, so we don't own it
            # we need KeepOpen for when the yielded object goes out of scope in the caller
            stream = Stream(KeepOpen(stream), mode='r')
        # FIXME: do we need KeepOpen for all streams?
        location._target_stream = stream
        return location

    def open(self, mode='r'):
        """Get open stream at location."""
        if self._target_stream is not None:
            return self._target_stream
        return self.container.open(self.subpath, mode=mode)

    def __enter__(self):
        return self.open()

    def __exit__(self,  exc_type, exc_val, exc_tb):
        # FIXME should we close opened stream?
        pass

    def is_dir(self):
        """Location points to a directory/container."""
        if self._target_stream is not None:
            return False
        return self.container.is_dir(self.subpath)

    def join(self, subpath):
        """Get a location at the subpath."""
        if self.subpath / subpath == self.subpath:
            return self
        if self._target_stream is not None:
            raise ValueError(
                f"Cannot open subpath '{subpath}' on stream `{self._target_stream}`."
            )
        logging.debug('joined to %s %s', self.container, self.subpath / subpath)
        # FIXME keep parent links
        return Location(self.container, self.subpath / subpath)

    def walk(self):
        """Recursively open locations."""
        if not self.is_dir():
            yield self
            return
        for path in self.container.iter_sub(self.subpath):
            subpath = Path(path).relative_to(self.subpath)
            location = self.join(subpath)
            location = location.resolve()
            yield from location.walk()


    ###########################################################################

    def _find_next_node(self):
        """Find the next node (container or file) in the path."""
        if self.container is None:
            logging.debug(vars(self))
            return '.', ''
        head, tail = _split_path(self.container, self.subpath)
        # if mode == 'w' and not head.suffixes:
        #     head2, tail = _split_path_suffix(tail)
        #     head /= head2
        return head, tail

    def resolve(self):
        """
        Convert location to subpath on innermost container and open stream.
        """
        head, tail = self._find_next_node()
        if str(head) == '.':
            # no next node found, path is leaf
            return self
        if self.container.is_dir(head):
            location = self
        else:
            # identify container/wrapper type on head
            stream = self.container.open(head, mode='r') #, mode, overwrite)
            location = self.from_stream(stream)
            location = location.unwrap_stream()
        if not tail or str(tail) == '.':
            return location
        location = location.join(tail)
        return location.resolve()

    def unwrap_stream(self):
        """
        Open one or more wrappers until an unwrapped stream is found.
        Returns Location object.
        """
        stream = self._target_stream
        while True:
            try:
                unwrapped = _open_wrapper(stream)
            except FileFormatError:
                # not a wrapper
                break
            else:
                stream = unwrapped
        try:
            container = _open_container(stream)
            return Location(container)
        except FileFormatError:
            pass
        return self.from_stream(stream)


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
        logging.debug('exists %s in %s', head, container)
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
