"""
monobit.storage.location - archive, directory and wrapper traversal

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path

from ..base.struct import StructError
from ..plumbing import take_arguments
from .magic import FileFormatError, MagicRegistry
from .streams import StreamBase, Stream, KeepOpen
from .base import wrappers, containers
from .holders import Container
from .containers.directory import Directory


def open_location(
        stream_or_location, mode='r', overwrite=False, container_format='',
        argdict=None,
    ):
    """
    Point to given location, resolving nested containers and wrappers.
    """
    if mode not in ('r', 'w'):
        raise ValueError(f"Unsupported mode '{mode}'.")
    if not stream_or_location:
        raise ValueError(f'No location provided.')
    if isinstance(stream_or_location, (str, Path)):
        return Location.from_path(
            stream_or_location, mode=mode, overwrite=overwrite,
            container_format=container_format, argdict=argdict,
        )
    # assume stream_or_location is a file-like object
    return Location.from_stream(
        stream_or_location, mode=mode, overwrite=overwrite,
        container_format=container_format, argdict=argdict,
    )


class Location:

    def __init__(
            self, *,
            root=None, path='', mode='r', overwrite=False,
            container_format='', argdict=None,
        ):
        self.path = Path(path)
        self.mode = mode
        self.overwrite = overwrite
        self.is_open = False
        # container or stream on which we attch the path
        # this object is NOT owned by us but externaly provided
        # an further objects in the path will be ours to close
        self._path_objects = [root]
        # subpath from last object in path_objects
        self._leafpath = self.path
        self._container_format = container_format.split('.')
        self.argdict = argdict

    def __repr__(self):
        return str(vars(self))

    # __str__

    @classmethod
    def from_path(cls, path, **kwargs):
        """Create from path-like or string."""
        path = Path(path)
        root = path.anchor or '.'
        subpath = path.relative_to(root)
        return cls(
            # Directory objects doesn't really need to be closed
            # so it's OK that we won't close this one
            root=Directory(root),
            path=subpath,
            **kwargs
        )

    @classmethod
    def from_stream(cls, stream, *, subpath='', mode='r', **kwargs):
        """Create from file-like object."""
        if not isinstance(stream, StreamBase):
            # not clear why we need KeepOpen
            # streams mysteriously get closed without it
            # but KeepOpen.close() does not actually get called... :/
            stream = Stream(KeepOpen(stream), mode=mode)
        if stream.mode != mode:
            raise ValueError(
                f"Stream mode '{stream.mode}' not equal to mode '{mode}'"
            )
        return cls(
            root=stream,
            path=subpath,
            mode=mode,
            **kwargs
        )

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type == BrokenPipeError:
            return True

    def open(self):
        """Resolve path, opening streams and containers as needed."""
        self.is_open = True
        try:
            self._resolve()
        except Exception:
            self.close()
            raise
        return self

    def close(self):
        # leave out the root object as we don't own it
        while len(self._path_objects) > 1:
            outer = self._path_objects.pop()
            try:
                outer.close()
            except Exception as exc:
                logging.warning('Exception while closing %s: 5s', outer, exc)
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
            raise IsADirectoryError(f'Location {self} is a directory.')
        return self._leaf

    def is_dir(self):
        """Location points to a directory/container."""
        if not self.is_open:
            raise ValueError(f'Location {self} is not open.')
        return not isinstance(self._leaf, StreamBase)

    def join(self, subpath):
        """Get a location at the subpath."""
        assert(self.is_dir())
        return Location(
            root=self._leaf,
            path=self._leafpath / subpath,
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
                yield from opened_location.walk()

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
            self._resolve_wrappers()
        if isinstance(self._leaf, Container):
            self._resolve_container()

    def _resolve_wrappers(self):
        """Open one or more wrappers until an unwrapped stream is found."""
        while True:
            stream = self._leaf
            if self._container_format:
                format = self._container_format[-1]
            else:
                format = ''
            try:
                wrapper_object = _open_container_or_wrapper(
                    wrappers, stream,
                    mode=self.mode, format=format, argdict=self.argdict,
                )
            except FileFormatError:
                # not a wrapper
                break
            else:
                if self._container_format:
                    self._container_format.pop()
                self._path_objects.append(wrapper_object)
                unwrapped = wrapper_object.open()
                self._path_objects.append(unwrapped)
                stream = unwrapped
        # check if innermost stream is a container
        try:
            container_object = _open_container_or_wrapper(
                containers, stream,
                mode=self.mode, format=format, argdict=self.argdict,
            )
        except FileFormatError:
            # innermost stream is a non-container stream.
            if self._leafpath == Path('.'):
                return
            raise ValueError(
                f"Cannot open subpath '{self._leafpath}' "
                f"on non-container stream {stream}'"
            )
        else:
            if self._container_format:
                self._container_format.pop()
            self._path_objects.append(container_object)

    def _resolve_container(self):
        container = self._leaf
        # find the innermost existing file (if reading)
        # or file name with suffix (if writing)
        head, tail = self._find_next_node()
        if self.mode == 'r':
            is_dir = container.is_dir(head)
        else:
            is_dir = not head.suffixes
        if is_dir:
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


def _open_container_or_wrapper(
        registry, instream, *,
        format='', mode='r', argdict=None
    ):
    """Open container or wrapper on open stream."""
    argdict = argdict or {}
    # identify file type
    try:
        fitting_classes = registry.get_for(instream, format=format)
    except ValueError as e:
        raise FileFormatError(e)
    last_error = None
    for cls in fitting_classes:
        if mode == 'r':
            instream.seek(0)
        logging.info(
            "Opening stream '%s' as container format `%s`",
            instream.name, cls.format
        )
        try:
            kwargs = take_arguments(cls.__init__, argdict)
            # returns container or wrapper object
            container_wrapper = cls(instream, mode=mode, **kwargs)
        except (FileFormatError, StructError) as e:
            logging.debug(e)
            last_error = e
            continue
        else:
            # remove used arguments
            for kwarg in kwargs:
                del argdict[kwarg]
            return container_wrapper
    if last_error:
        raise last_error
    message = f"Cannot open container or wrapper on stream '{instream.name}'"
    if format:
        message += f': format specifier `{format}` not recognised'
    raise FileFormatError(message)
