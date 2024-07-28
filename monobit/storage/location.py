"""
monobit.storage.location - archive, directory and wrapper traversal

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools
from pathlib import Path
from collections import deque

from ..plumbing import take_arguments, manage_arguments
from .magic import FileFormatError, MagicRegistry
from .streams import StreamBase, Stream, KeepOpen
from .base import encoders, decoders, containers
from .containers import Container
from .containerformats.directory import Directory


def open_location(
        stream_or_location, mode='r', overwrite=False, match_case=False,
        container_format='', argdict=None, make_dir=False,
    ):
    """Point to given location; may include nested containers and wrappers."""
    if mode not in ('r', 'w'):
        raise ValueError(f"Mode must be 'r' or 'w'; not '{mode}'.")
    if not stream_or_location:
        raise ValueError(f'No location provided.')
    if isinstance(stream_or_location, (str, Path)):
        return Location.from_path(
            stream_or_location, mode=mode,
            overwrite=overwrite, match_case=match_case,
            container_format=container_format, argdict=argdict,
            make_dir=make_dir,
        )
    # assume stream_or_location is a file-like object
    return Location.from_stream(
        stream_or_location, mode=mode,
        overwrite=overwrite, match_case=match_case,
        container_format=container_format, argdict=argdict,
    )


class Location:

    def __init__(
            self, *,
            root=None, path='', mode='r', overwrite=False, match_case=False,
            container_format='', argdict=None, make_dir=False,
        ):
        self.path = Path(path)
        self.mode = mode
        self.overwrite = overwrite
        self.match_case = match_case
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
        self._make_dir = make_dir
        self.argdict = argdict
        self._outermost_path = None

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
        path = Path(path).resolve()
        root = path.anchor
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
        elif exc_type is not None:
            if self._path_objects and self.mode == 'w':
                root = self._path_objects[0]
                if isinstance(root, Directory):
                    root.remove(self._outermost_path)

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
            self._outer_stream_object = self._stream_objects.pop()
            try:
                self._outer_stream_object.close()
            except Exception as exc:
                logging.warning(
                    'Exception while closing %s: %s',
                    self._outer_stream_object, exc
                )
        while len(self._path_objects) > 1:
            outer = self._path_objects.pop()
            try:
                outer.close()
            except Exception as exc:
                logging.warning(
                    'Exception while closing %s: %s',
                    self._outer_stream_object, exc
                )
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
            match_case=self.match_case,
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
        return _contains(container, subpath / item, self.match_case)

    def open(self, name, mode):
        """Open a binary stream in the container."""
        container, subpath = self._get_container_and_subpath()
        self._check_overwrite(container, subpath / name, mode=mode)
        if mode == 'r':
            kwargs = take_arguments(container.decode, self.argdict)
            stream = container.decode(subpath / name, **kwargs)
        else:
            kwargs = take_arguments(container.encode, self.argdict)
            stream = container.encode(subpath / name, **kwargs)
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
        if (
                mode == 'w' and not self.overwrite
                and _contains(container, path, self.match_case)
            ):
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
            self._resolve_subpath()

    def _resolve_wrappers(self):
        """Open one or more wrappers until an unwrapped stream is found."""
        while True:
            stream = self._leaf
            if self._container_format:
                format = self._container_format[-1]
            else:
                format = ''
            try:
                unwrapped_stream = _get_transcoded_stream(
                    stream, mode=self.mode, format=format, argdict=self.argdict,
                )
            except FileFormatError as e:
                # not a wrapper, maybe a container
                logging.debug(e)
                break
            else:
                if self._container_format:
                    self._container_format.pop()
                self._stream_objects.append(unwrapped_stream)
                stream = unwrapped_stream
        # check if innermost stream is a container
        try:
            container_object = _open_container(
                containers, stream, mode=self.mode, format=format,
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

    def _resolve_subpath(self):
        """Resolve subpath on a container object."""
        container = self._leaf
        # stepwise match path elements with existing ones in container
        # head is the innermost existing path element
        head, tail = _match_path(self._leaf, self._leafpath, self.match_case)
        if Path(head) == Path('.') and Path(tail) == Path('.'):
            # path has resolved
            return
        if self.mode == 'r':
            try:
                # see if head points to a file -> open it
                kwargs = take_arguments(container.decode, self.argdict)
                stream = container.decode(head, **kwargs)
            except IsADirectoryError:
                if Path(tail) == Path('.'):
                    # path has resolved; nothing further to open
                    return
                # head (innermost existing) is a subdirectory
                # i.e. tail subpath does not exist
                raise FileNotFoundError(
                    f"Subpath '{tail}' of path '{head}' not found on container {container}."
                )
            else:
                # remove used arguments
                for kwarg in kwargs:
                    del self.argdict[kwarg]
        else:
            # step forward until a suffix is found, or we run out of path
            if not head.suffixes:
                head2, tail = _split_path_suffix(tail)
                head /= head2
            # head is now the innermost path element *to be created*
            # check if we're asked to create an file or a subdirectory
            # it's a subdirectory if (1) explicitly asked or (2) no suffix
            if (
                    self._make_dir
                    or not head.suffixes
                ):
                # head (innermost creatable) should be a subdirectory
                return
            else:
                # head should be a file -> create it
                self._check_overwrite(container, head, mode=self.mode)
                if not self._outermost_path:
                    self._outermost_path = head
                kwargs = take_arguments(container.encode, self.argdict)
                stream = container.encode(head, **kwargs)
                for kwarg in kwargs:
                    del self.argdict[kwarg]
        # recurse on successfully opened file
        self._stream_objects.append(stream)
        self._leafpath = tail
        self._resolve()


def _split_path_suffix(path):
    """Pare forward path until a suffix is found."""
    for head in reversed((path, *path.parents)):
        if head.suffixes:
            tail = path.relative_to(head)
            return head, tail
    # no suffix
    return path, Path('.')


def _step_match(container, matched_path, target, match_case):
    """One-step match for path element."""
    target = str(target)
    for name in container.iter_sub(matched_path):
        found = Path(name).name
        if (found == target) or (
                (not match_case)
                and found.lower() == target.lower()
            ):
            return found
    return ''


def _match_path(container, path, match_case):
    """Stepwise match per path element."""
    segments = Path(path).as_posix().split('/')
    segments = deque(segments)
    matched_path = Path('.')
    while True:
        target = segments.popleft()
        # try case-sensitive match first, then case-insensitive
        match = _step_match(container, matched_path, target, match_case=True)
        if not match and not match_case:
            match = _step_match(container, matched_path, target, match_case=False)
        if match:
            matched_path /= match
            if not segments or not container.is_dir(matched_path):
                # found match this level, can't go deeper
                return matched_path, Path(*segments)
            # found match this level, go to next
            continue
        # no match this level
        return matched_path, Path(target, *segments)


def _contains(container, path, match_case):
    """Container contains file (case insensitive)."""
    _, tail = _match_path(container, path, match_case)
    return tail == Path('.')


def _open_container(
        registry, instream, *,
        format='', mode='r'
    ):
    """Open container on open stream."""
    # identify file type
    fitting_classes = registry.get_for(instream, format=format)
    if not fitting_classes:
        msg = "Container format not recognised"
        if format:
            msg += f': `{format}`'
        raise FileFormatError(msg)
    last_error = None
    for cls in fitting_classes:
        if mode == 'r':
            instream.seek(0)
        logging.info(
            "Opening stream '%s' as container format `%s`",
            instream.name, cls.format
        )
        try:
            # returns container object
            container = cls(instream, mode=mode)
        except FileFormatError as e:
            logging.debug(e)
            last_error = e
            continue
        else:
            return container
    if last_error:
        raise last_error
    message = f"Cannot open container on stream '{instream.name}'"
    if format:
        message += f': format specifier `{format}` not recognised'
    raise FileFormatError(message)


def _get_transcoded_stream(
        instream, *,
        format='', mode='r', argdict=None
    ):
    """Open wrapper on open stream."""
    argdict = argdict or {}
    if mode == 'r':
        registry = decoders
    elif mode == 'w':
        registry = encoders
    else:
        raise ValueError(f"`mode` must be 'r' or 'w', not {mode}.")
    # identify file type
    last_error = None
    for transcoder in iter_funcs_from_registry(registry, instream, format):
        if mode == 'r':
            instream.seek(0)
        logging.info(
            "Transcoding stream '%s' with wrapper format `%s`",
            instream.name, transcoder.format
        )
        try:
            # pick arguments we can use
            kwargs = take_arguments(transcoder, argdict)
            transcoded_stream = transcoder(instream, **kwargs)
        except FileFormatError as e:
            logging.debug(e)
            last_error = e
            continue
        else:
            # remove used arguments
            for kwarg in kwargs:
                del argdict[kwarg]
            return transcoded_stream
    if last_error:
        raise last_error
    message = f"Cannot transcode stream '{instream.name}'"
    if format:
        message += f': format specifier `{format}` not recognised'
    raise FileFormatError(message)


def iter_funcs_from_registry(registry, instream, format):
    """
    Iterate over and wrap functions stored in a MagicRegistry
    that fit a given stream and format.
    """
    # identify file type
    fitting_loaders = registry.get_for(instream, format=format)
    for loader in fitting_loaders:
        yield manage_arguments(loader)
    return
