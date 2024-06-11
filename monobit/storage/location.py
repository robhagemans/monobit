"""
monobit.storage.location - archive, directory and wrapper traversal

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from collections import deque

from ..plumbing import take_arguments
from .magic import FileFormatError, MagicRegistry
from .streams import StreamBase, Stream, KeepOpen
from .base import wrappers, containers
from .containers.containers import Container
from .containers.directory import Directory


def open_location(
        stream_or_location, mode='r', overwrite=False, container_format='',
        argdict=None,
    ):
    """Point to given location; may include nested containers and wrappers."""
    if mode not in ('r', 'w'):
        raise ValueError(f"Mode must be 'r' or 'w'; not '{mode}'.")
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
        self.resolved = False
        # container or stream on which we attch the path
        # this object is NOT owned by us but externaly provided
        # an further objects in the path will be ours to close
        if isinstance(root, Container):
            self._path_objects = [root]
            self._stream_objects = []
        else:
            self._path_objects = []
            self._stream_objects = [KeepOpen(root)]
        # subpath from last container in path_objects
        self._container_subpath = self.path
        # subpath from last object in path_objects or stream_objects
        self._leafpath = self.path
        # format parameters
        self._container_format = container_format.split('.')
        self.argdict = argdict

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"root='{self._path_objects[0]}' path='{self.path}' mode='{self.mode}'"
            f"{' [unresolved]' if not self.resolved else ''}>"
        )

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
                f"Stream mode '{stream.mode}' not equal to location mode '{mode}'"
            )
        return cls(
            root=stream,
            path=subpath,
            mode=mode,
            **kwargs
        )

    def __enter__(self):
        return self.resolve()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type == BrokenPipeError:
            return True

    def resolve(self):
        """Resolve path, opening streams and containers as needed."""
        self.resolved = True
        try:
            self._resolve()
        except Exception:
            self.close()
            raise
        return self

    def close(self):
        """Close objects we opened on path."""
        # leave out the root object as we don't own it
        while self._stream_objects:
            outer = self._stream_objects.pop()
            try:
                outer.close()
            except Exception as exc:
                logging.warning('Exception while closing %s: %s', outer, exc)
        while len(self._path_objects) > 1:
            outer = self._path_objects.pop()
            try:
                outer.close()
            except Exception as exc:
                logging.warning('Exception while closing %s: %s', outer, exc)
        self.resolved = False

    @property
    def _leaf(self):
        """Object (stream or container) at the end of path."""
        try:
            return self._stream_objects[-1]
        except IndexError:
            return self._path_objects[-1]

    def get_stream(self):
        """Get open stream at location."""
        if self.is_dir():
            raise IsADirectoryError(f'Location {self} is a directory.')
        stream = self._stream_objects[-1]
        stream.where = self
        return stream

    def is_dir(self):
        """Location points to a directory/container."""
        if not self.resolved:
            raise ValueError(f'Location {self} is not open.')
        return not self._stream_objects

    # directory (container) functionality

    def _get_container_and_subpath(self):
        """Get open container and subpath to location."""
        if not self.is_dir():
            return self._path_objects[-1], self._container_subpath.parent
        return self._path_objects[-1], self._container_subpath

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
            with location:
                yield from location.walk()

    def iter_sub(self, prefix):
        """List contents of a subpath."""
        container, subpath = self._get_container_and_subpath()
        return (
            _path.relative_to(subpath)
            for _path in container.iter_sub(subpath / prefix)
        )

    def contains(self, item):
        """Check if file is in container. Case sensitive if container/fs is."""
        container, subpath = self._get_container_and_subpath()
        return _contains(container, subpath / item)

    def open(self, name, mode):
        """Open a binary stream in the container."""
        container, subpath = self._get_container_and_subpath()
        self._check_overwrite(container, subpath / name, mode=mode)
        if container.is_dir(subpath / name):
            raise IsADirectoryError(
                f"Cannot open stream on '{name}': is a directory."
            )
        stream = container.open(subpath / name, mode=mode)
        stream.where = self
        return stream

    def unused_name(self, name):
        """Generate unique name for container file."""
        if not self.contains(name):
            return name
        stem, _, suffix = name.rpartition('.')
        for i in itertools.count():
            filename = '{}.{}'.format(stem, i)
            if suffix:
                filename = '{}.{}'.format(filename, suffix)
            if not self.contains(filename):
                return filename


    ###########################################################################

    def _check_overwrite(self, container, path, mode):
        if mode == 'w' and not self.overwrite and _contains(container, path):
            raise ValueError(
                f"Overwriting existing file '{path}'"
                " requires -overwrite to be set"
            )

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
                self._stream_objects.append(wrapper_object)
                unwrapped_stream = wrapper_object.open()
                self._stream_objects.append(unwrapped_stream)
                stream = unwrapped_stream
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
            self._path_objects.extend(self._stream_objects)
            self._path_objects.append(container_object)
            self._stream_objects = []
            self._container_subpath = self._leafpath

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
            # head points to a file. open it and recurse
            self._check_overwrite(container, head, mode=self.mode)
            stream = container.open(head, mode=self.mode)
            self._stream_objects.append(stream)
            self._leafpath = tail
            self._resolve()

    def _find_next_node(self):
        """Find the next existing node (container or file) in the path."""
        head, tail = _match_case_insensitive(self._leaf, self._leafpath)
        if self.mode == 'w' and not head.suffixes:
            head2, tail = _split_path_suffix(tail)
            head /= head2
        return head, tail


def _split_path_suffix(path):
    """Pare forward path until a suffix is found."""
    for head in reversed((path, *path.parents)):
        if head.suffixes:
            tail = path.relative_to(head)
            return head, tail
    # no suffix
    return path, Path('.')


def _match_case_insensitive(container, path):
    """Stepwise match per path element."""
    segments = Path(path).as_posix().split('/')
    segments = deque(segments)
    matched_path = Path('.')
    while True:
        target = segments.popleft()
        #TODO try case-sensitive match first
        for name in container.iter_sub(matched_path):
            if str(target).lower() == Path(name).name.lower():
                matched_path /= Path(name).name
                if not segments:
                    return matched_path, Path('.')
                elif not container.is_dir(matched_path):
                    return matched_path, Path(*segments)
                break
        else:
            return matched_path, Path(target, *segments)

def _contains(container, path):
    """Container contains file (case insensitive)."""
    _, tail = _match_case_insensitive(container, path)
    return tail == Path('.')



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
        except FileFormatError as e:
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
