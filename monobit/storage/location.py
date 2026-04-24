"""
monobit.storage.location - archive, wrapper and stream resource management

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import itertools
from pathlib import Path

from ..plumbing import take_arguments
from .containers import Container
from .containerformats.directory import Directory
from .pathutils import path_exists
from .resolvepath import PathResolver


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
        return Location(
            PathResolver.from_path(
                stream_or_location, mode=mode,
                overwrite=overwrite, match_case=match_case,
                container_format=container_format, argdict=argdict,
                make_dir=make_dir,
            )
        )
    # assume stream_or_location is a file-like object
    return Location(
        PathResolver.from_stream(
            stream_or_location, mode=mode,
            overwrite=overwrite, match_case=match_case,
            container_format=container_format, argdict=argdict,
        )
    )


class Location:

    def __init__(self, resolver):
        self.path = resolver.path

        self.mode = resolver.mode
        self.overwrite = resolver.overwrite
        self.match_case = resolver.match_case
        self.argdict = resolver.argdict

        self._path_objects = resolver._path_objects
        self._stream_objects = resolver._stream_objects

        self._leafpath = resolver._leafpath
        self._container_subpath = resolver._container_subpath
        self._outermost_path = resolver._outermost_path

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"root='{self._path_objects[0]}' path='{self.path}' mode='{self.mode}'"
            f">"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type == BrokenPipeError:
            return True
        elif exc_type is not None:
            if self._path_objects and self.mode == 'w':
                root = self._path_objects[0]
                if isinstance(root, Directory):
                    root.remove(self._outermost_path)

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

    @property
    def root(self):
        if self._path_objects:
            return self._path_objects[0]
        else:
            return ''

    @property
    def _leaf(self):
        """Object (stream or container) at the end of path."""
        try:
            return self._stream_objects[-1]
        except IndexError:
            return self._path_objects[-1]

    # stream functionality

    def get_stream(self):
        """Get open stream at location."""
        if self.is_dir():
            raise IsADirectoryError(f'Location {self} is a directory.')
        stream = self._stream_objects[-1]
        stream.where = self
        return stream

    def is_dir(self):
        """Location points to a directory/container."""
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
        # PathResolver
        return Location(
            PathResolver(
                root=self._leaf,
                path=self._leafpath / subpath,
                mode=self.mode,
                overwrite=self.overwrite,
                match_case=self.match_case,
            )
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
            try:
                with location:
                    yield from location.walk()
            except EnvironmentError as e:
                # e.g. broken links. log and skip
                logging.warning(e)


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
        return path_exists(container, subpath / item, self.match_case)

    def open(self, name, mode):
        """Open a binary stream in the container."""
        container, subpath = self._get_container_and_subpath()
        if mode == 'r':
            if not path_exists(container, subpath / name, match_case=self.match_case):
                raise FileNotFoundError(
                    f"{container}//{subpath}//{name} not found "
                    f"with case-{'' if self.match_case else 'in'}sensitive match."
                )
            kwargs = take_arguments(container.decode, self.argdict)
            stream = container.decode(subpath / name, **kwargs)
        else:
            self._check_overwrite(container, subpath / name, mode=mode)
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
                and path_exists(container, path, self.match_case)
            ):
            raise FileExistsError(
                f"Overwriting existing file '{path}'"
                " requires -overwrite to be set"
            )
