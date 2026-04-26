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


open_location = resolve_path


class Location:

    def __init__(
            self, *,
            path, mode, overwrite, match_case,
            argdict,
            elements,
            outermost_path,
        ):
        self.mode = mode
        self.overwrite = overwrite
        self.match_case = match_case
        self.argdict = argdict

        # resources to manage
        self._elements = elements

        # full path relative to root
        self.relative_path = path
        # outermost file that has been created, which should be removed on failure
        self._outermost_path = outermost_path

    def __repr__(self):
        return (
            f"<{type(self).__name__} "
            f"path='{self.path}' mode='{self.mode}'"
            f">"
        )

    def __str__(self):
        return str(self.path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type == BrokenPipeError:
            return True
        elif exc_type is not None:
            if self._elements and self.mode == 'w':
                root = self._elements[0].container
                if isinstance(root, Directory):
                    root.remove(self._outermost_path)

    def close(self):
        """Close objects we opened on path."""
        # leave out the root object as we don't own it
        while self._elements:
            outer = self._elements.pop()
            lastelement = not self._elements
            container = outer.container
            if container and not lastelement:
                try:
                    container.close()
                except Exception as exc:
                    logging.warning('Exception while closing %s: %s', container, exc)
            while outer.streams:
                stream = outer.streams.pop()
                if lastelement and not outer.streams:
                    # root stream
                    break
                try:
                    stream.close()
                except Exception as exc:
                    logging.warning('Exception while closing %s: %s', stream, exc)

    @property
    def path(self):
        if not self._elements:
            return Path()
        if self._elements[0].streams:
            root = self._elements[0].streams[0]
        else:
            root = self._elements[0].container
        return Path(str(root)) / self.relative_path

    # stream functionality

    def get_parent(self):
        """Parent location of stream."""
        if self.is_dir():
            raise NotImplementedError('get_parent only implemented for file locations.')
        if len(self._elements) > 1:
            parent_elements = [*self._elements[:-1]]
            parent_elements[-1].subpath = parent_elements[-1].subpath.parent
        else:
            parent_elements = []
        return Location(
            path=self.path.parent,
            mode=self.mode,
            overwrite=self.overwrite,
            match_case=self.match_case,
            argdict=self.argdict,
            elements=parent_elements,
            outermost_path=None,
        )

    def get_stream(self):
        """Get open stream at location."""
        if self.is_dir():
            raise IsADirectoryError(f'{self.path} is a directory.')
        stream = self._elements[-1].streams[-1]
        stream.where = self.get_parent()
        return stream

    def is_dir(self):
        """Location points to a directory/container."""
        return self._elements[-1].container

    # directory (container) functionality

    def _get_container_and_subpath(self):
        """Get open container and subpath to location."""
        if not self.is_dir():
            raise NotADirectoryError(f'{self.path} is not a directory.')
        return self._elements[-1].container, self._elements[-1].subpath

    def join(self, subpath):
        """Get a location at the subpath."""
        container, path = self._get_container_and_subpath()
        return resolve_path(
            container,
            subpath=path / subpath,
            mode=self.mode,
            overwrite=self.overwrite,
            match_case=self.match_case,
        )

    def walk(self):
        """Recursively open locations."""
        if not self.is_dir():
            # recursion ends on a file path
            yield self
            return
        container, containerpath = self._get_container_and_subpath()
        for path in container.iter_sub(containerpath):
            subpath = Path(path).relative_to(containerpath)
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
