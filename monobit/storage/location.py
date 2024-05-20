import logging
from pathlib import Path

from ..base.struct import StructError
from .magic import FileFormatError, MagicRegistry
from .containers.directory import Directory

from .streams import StreamBase, Stream, KeepOpen
from .wrappers.compressors import WRAPPERS
from .containers.container import CONTAINERS, Container


def open_location(stream_or_location, mode='r', overwrite=False):
    """
    Point to given location, resolving nested containers and wrappers.
    """
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not stream_or_location:
        raise ValueError(f'No location provided.')
    if isinstance(stream_or_location, (str, Path)):
        location = Location.from_path(
            stream_or_location, mode=mode, overwrite=overwrite
        )
    else:
        # stream_or_location is a file-like object
        location = Location.from_stream(
            stream_or_location, mode=mode, overwrite=overwrite
        )
    return location


class Location:

    def __init__(self, *, root=None, subpath='', mode='r', overwrite=False):
        # TODO rename subpath -> path
        self.subpath = Path(subpath)
        self.mode = mode
        # TODO overwrite -> 'w' vs 'a' modes (on containers)
        self.overwrite = overwrite
        self.is_open = False
        # container or stream on which we attch the subpath
        # this object is NOT owned by us but externaly provided
        # an further objects in the path will be ours to close
        self._path_objects = [root]
        # subpath from last object in path_objects
        self._leafpath = self.subpath

    def __repr__(self):
        return str(vars(self))

    # __str__

    @classmethod
    def from_path(cls, path, *, mode='r', overwrite=False):
        """Create from path-like or string."""
        path = Path(path)
        root = path.anchor or '.'
        subpath = path.relative_to(root)
        return cls(
            # Directory objects doesn't really need to be closed
            # so it's OK that we won't close this one
            root=Directory(root),
            subpath=subpath,
            mode=mode,
            overwrite=overwrite,
        )

    @classmethod
    def from_stream(cls, stream, *, subpath='', mode='r', overwrite=False):
        """Create from file-like object."""
        if not isinstance(stream, StreamBase):
            stream = Stream(stream, mode=mode)
        if stream.mode != mode:
            raise ValueError(
                f"Stream mode '{stream.mode}' not equal to mode '{mode}'"
            )
        return cls(
            root=stream,
            subpath=subpath,
            mode=mode,
            overwrite=overwrite,
        )

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self):
        """Resolve path, opening streams and containers as needed."""
        self.is_open = True
        self._resolve()
        return self

    def close(self):
        # leave out the root object as we don't own it
        while len(self._path_objects) > 1:
            self._path_objects.pop().close()
        self.is_open = False

    @property
    def _leaf(self):
        leaf = self._path_objects[-1]
        assert isinstance(leaf, (StreamBase, Container)), leaf
        return leaf

    @property
    def root(self):
        return self._path_objects[0]

    def get_stream(self):
        """Get open stream at location."""
        if self.is_dir():
            raise IsADirectoryError('Location {self} is a directory.')
        return self._leaf

    def is_dir(self):
        """Location points to a directory/container."""
        if not self.is_open:
            raise ValueError('Location {self} is not open.')
        return not isinstance(self._leaf, StreamBase)

    def join(self, subpath):
        """Get a location at the subpath."""
        assert(self.is_dir())
        return Location(
            root=self._leaf,
            subpath=self._leafpath / subpath,
            mode=self.mode,
            overwrite=self.overwrite,
        )

    def walk(self):
        """Recursively open locations."""
        if not self.is_dir():
            yield self
            return
        container = self._leaf
        for path in container.iter_sub(self._leafpath):
            subpath = Path(path).relative_to(self._leafpath)
            location = self.join(subpath)
            with location.open() as opened_location:
                subs = list(opened_location.walk())
                yield from subs

    def unused_name(self, name):
        if not self.is_dir():
            raise ValueError('Cannot create name on stream.')
        container = self._leaf
        return container.unused_name(name)


    ###########################################################################

    def _resolve(self):
        """
        Convert location to subpath on innermost container and open stream.
        """
        if isinstance(self._leaf, StreamBase):
            self._unwrap()
        if isinstance(self._leaf, Container):
            self._resolve_container()

    def _resolve_container(self):
        container = self._leaf
        # find the innermost existing file (if reading)
        # or file name with suffix (if writing)
        head, tail = self._find_next_node()
        if container.is_dir(head):   # also if head == '.'
            # innermost existing/creatable is a subdirectory
            if Path(tail) == Path('.'):
                # we are a directory, nothing to open
                return
            else:
                # tail subpath does not exist
                if self.mode == 'r':
                    raise FileNotFoundError(
                        f"Subpath '{tail}' not found on container {container}."
                    )
                # new directory
                return
        else:
            # head is a file. open it and recurse
            stream = container.open(
                head, mode=self.mode, overwrite=self.overwrite
            )
            self._path_objects.append(stream)
            self._leafpath = tail
            self._resolve()


    def _find_next_node(self):
        """Find the next existing node (container or file) in the path."""
        head, tail = self._split_path(self._leaf, self._leafpath)
        if self.mode == 'w' and not head.suffixes:
            head2, tail = self._split_path_suffix(tail)
            head /= head2
        return head, tail

    @staticmethod
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

    @staticmethod
    def _split_path_suffix(path):
        """Pare forward path until a suffix is found."""
        for head in reversed((path, *path.parents)):
            if head.suffixes:
                tail = path.relative_to(head)
                return head, tail
        # no suffix
        return path, Path('.')


    def _unwrap(self):
        """Open one or more wrappers until an unwrapped stream is found."""
        while True:
            stream = self._leaf
            try:
                unwrapped = _open_wrapper(stream, mode=self.mode)
            except FileFormatError:
                # not a wrapper
                break
            else:
                self._path_objects.append(unwrapped)
                stream = unwrapped
        # check if innermost stream is a container
        try:
            self._path_objects.append(
                _open_container(stream, mode=self.mode)
            )
        except FileFormatError:
            # innermost stream is a non-container stream.
            if self._leafpath == Path('.'):
                return
            raise ValueError(
                f"Cannot open subpath '{subpath}' "
                f"on non-container stream {stream}'"
            )


def _open_wrapper(instream, *, format='', mode='r', **kwargs):
    """Open wrapper on open stream."""
    # identify file type
    fitting_classes = WRAPPERS.get_for(instream, format=format)
    last_error = None
    for cls in fitting_classes:
        instream.seek(0)
        logging.info('Opening `%s` as wrapper format %s', instream.name, cls.format)
        try:
            # returns unwrapped stream
            return cls.open(instream, mode=mode, **kwargs)
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


def _open_container(instream, *, format='', mode='r', **kwargs):
    """Open container on open stream."""
    # identify file type
    fitting_classes = CONTAINERS.get_for(instream, format=format)
    last_error = None
    for cls in fitting_classes:
        instream.seek(0)
        logging.info('Opening `%s` as container format %s', instream.name, cls.format)
        try:
            # returns container object
            return cls(instream, mode=mode, **kwargs)
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
