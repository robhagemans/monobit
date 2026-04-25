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
from .pathutils import path_exists, join_path
from .resolvepath import resolve_path


def open_location(
        stream_or_location, mode='r', overwrite=False, match_case=False,
        container_format='', argdict=None, make_dir=False,
    ):
    """Point to given location; may include nested containers and wrappers."""
    return Location(
        resolve_path(
            stream_or_location, mode=mode,
            overwrite=overwrite, match_case=match_case,
            container_format=container_format, argdict=argdict,
            make_dir=make_dir,
        )
    )


class Location:

    def __init__(self, resolver):
        self.mode = resolver.mode
        self.overwrite = resolver.overwrite
        self.match_case = resolver.match_case
        self.argdict = resolver.argdict

        # resources to manage
        self._path_objects = resolver.path_objects
        self._stream_objects = resolver.stream_objects

        # full path relative to root
        self.relative_path = resolver.path
        # path from last container onward
        self._container_subpath = resolver.container_subpath
        # subdirectory that has been created and should be removed on failure
        self._outermost_path = resolver.outermost_path

    def __repr__(self):
        """String representation."""
        return (
            f"<{type(self).__name__} "
            f"path='{self.path}' mode='{self.mode}'"
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

    @property
    def path(self):
        if self._path_objects:
            root = self._path_objects[0]
        else:
            root = ''
        return Path(str(root)) / self.relative_path

    # stream functionality

    def get_stream(self):
        """Get open stream at location."""
        if self.is_dir():
            raise IsADirectoryError(f'{self.path} is a directory.')
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
        return Location(
            resolve_path(
                self._path_objects[-1],
                subpath=self._container_subpath / subpath,
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
        container = self._path_objects[-1]
        for path in container.iter_sub(self._container_subpath):
            subpath = Path(path).relative_to(self._container_subpath)
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
        exists = path_exists(container, subpath / name, self.match_case)
        if mode == 'r':
            if not exists:
                raise FileNotFoundError(
                    f"{join_path(container, subpath, name)} not found "
                    f"with case-{'' if self.match_case else 'in'}sensitive match."
                )
            kwargs = take_arguments(container.decode, self.argdict)
            stream = container.decode(subpath / name, **kwargs)
        else:
            if exists and not self.overwrite:
                raise FileExistsError(
                    f"{join_path(container, subpath, name)} already exists. "
                    "Use option -overwrite if you wish to overwrite it."
                )
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
