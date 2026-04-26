"""
monobit.storage.resolvepath - archive, directory and wrapper traversal

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from os.path import commonprefix
from dataclasses import dataclass, field

from ..plumbing import take_arguments
from .magic import FileFormatError, iter_funcs_from_registry
from .streams import StreamBase, Stream, KeepOpen
from .base import encoders, decoders, containers
from .containers import Container
from .containerformats.directory import Directory
from .pathutils import path_exists, match_path, join_path


def resolve_path(location='', *, subpath='', mode='r', **kwargs):
    if mode not in ('r', 'w'):
        raise ValueError(f"Mode must be 'r' or 'w'; not '{mode}'.")
    if not location and not subpath:
        raise ValueError(f'No path provided.')
    if isinstance(location, (str, Path)):
        path = Path(location) / subpath
        path = path.resolve()
        here = Path().resolve()
        root = Path(commonprefix((path, here)))
        subpath = path.relative_to(root)
        # Directory objects doesn't really need to be closed
        # so it's OK that we won't close this one
        root = Directory(root, mode=mode)
    else:
        # stream or container object
        if not isinstance(location, (StreamBase, Container)):
            # assume it's a python stream object
            # not clear why we need KeepOpen
            # streams mysteriously get closed without it
            # but KeepOpen.close() does not actually get called... :/
            location = Stream(KeepOpen(location), mode=mode)
        if location.mode != mode:
            if mode == 'r':
                raise ValueError(
                    f"Could not read {join_path(location, subpath)}: "
                    f"{location} is write-only."
                )
            else:
                raise ValueError(
                    f"Could not write to {join_path(location, subpath)}: "
                    f"{location} is read-only."
                )
        root = location
    return _PathResolver(
        root=root,
        path=subpath,
        mode=mode,
        **kwargs
    ).resolve()


@dataclass
class _PathElement:
    streams: list = field(default_factory=list)
    container: Container = None
    subpath: Path = Path()


class _PathResolver:

    def __init__(
            self, *,
            root=None, path='', mode='r', overwrite=False, match_case=False,
            container_format='', argdict=None, make_dir=False,
        ):
        self.mode = mode
        self.overwrite = overwrite
        self.match_case = match_case
        # container or stream on which we attch the path
        # this object is NOT owned by us but externaly provided
        # an further objects in the path will be ours to close
        if isinstance(root, Container):
            self.elements = [
                _PathElement(streams=[], container=root, subpath=Path())
            ]
        else:
            self.elements = [
                _PathElement(streams=[KeepOpen(root)], container=None, subpath=Path())
            ]
        # remaining path from innermost container object
        self._unresolved_path = Path(path)
        # format parameters
        self.container_format = container_format.split('.')
        self.make_dir = make_dir
        self.argdict = argdict

    def resolve(self):
        """Recursively open containers and wrappers in path."""
        # late import due to cyclic dependency
        from .location import Location
        error = None
        try:
            self._resolve()
        except Exception as exc:
            error = exc
        location = Location(
            mode=self.mode,
            overwrite=self.overwrite,
            match_case=self.match_case,
            argdict=self.argdict,
            elements=self.elements,
        )
        if error:
            # close all resources created by _resolve()
            location.close()
            raise error
        return location

    def _resolve(self):
        while True:
            if self.elements[-1].container is None:
                self._resolve_wrappers()
            if self.elements[-1].container is None:
                break
            if self._resolve_subpath():
                break
        if self._unresolved_path != Path():
            # catchall - this should not be reached
            raise FileNotFoundError(
                f'Unresolved path {self._unresolved_path}.'
            )

    def _resolve_wrappers(self):
        """Open one or more wrappers until an unwrapped stream is found."""
        while True:
            stream = self.elements[-1].streams[-1]
            if self.container_format:
                format = self.container_format[-1]
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
                if self.container_format:
                    self.container_format.pop()
                self.elements[-1].streams.append(unwrapped_stream)
                stream = unwrapped_stream
        # check if innermost stream is a container
        try:
            container_object = _open_container(
                containers, stream, mode=self.mode, format=format,
            )
        except FileFormatError:
            # innermost stream is a non-container stream.
            if self._unresolved_path == Path():
                return
            raise ValueError(
                f"Could not open {join_path(stream, self._unresolved_path)}: "
                f"stream {stream} is not a container."
            )
        else:
            if self.container_format:
                self.container_format.pop()
            self.elements[-1].container = container_object

    def _resolve_subpath(self):
        """Resolve subpath on a container object."""
        container = self.elements[-1].container
        # stepwise match path elements with existing ones in container
        # innermost existing path element
        existing, unmatched = match_path(container, self._unresolved_path, self.match_case)
        self.elements[-1].subpath = existing
        if Path(existing) == Path() and Path(unmatched) == Path():
            # path has resolved
            self._unresolved_path = unmatched
            return True
        if self.mode == 'r':
            try:
                # see if existing points to a file -> open it
                kwargs = take_arguments(container.decode, self.argdict)
                stream = container.decode(existing, **kwargs)
            except IsADirectoryError:
                if Path(unmatched) == Path():
                    # path has resolved; nothing further to open
                    self._unresolved_path = unmatched
                    return True
                # innermost existing is a subdirectory
                # i.e. unmatched subpath does not exist
                raise FileNotFoundError(
                    f"{join_path(container, existing, unmatched)} not found."
                )
            else:
                # remove used arguments
                for kwarg in kwargs:
                    del self.argdict[kwarg]
        else:
            if unmatched != Path() and not container.is_dir(existing):
                raise FileExistsError(
                    f"Could not create {join_path(container, existing, unmatched)}: "
                    f"{join_path(container, existing)} already exists "
                    "and we cannot append to it."
                )
            # step forward until a container pattern is encountered, or we run out of path
            path_to_container, unmatched = _split_path_containername(unmatched)
            to_be_created = existing / path_to_container
            self.elements[-1].subpath = to_be_created
            # innermost path element *to be created*
            # check if we're asked to create an file or a subdirectory
            # it's a subdirectory if (1) explicitly asked or (2) no suffix
            if self.make_dir or not to_be_created.suffixes:
                # innermost creatable should be a subdirectory
                self._unresolved_path = unmatched
                return True
            else:
                # innermost creatable should be a file -> create it
                if (
                        path_exists(container, to_be_created, self.match_case)
                        and not self.overwrite
                    ):
                    raise FileExistsError(
                        f"{join_path(container, to_be_created)} already exists. "
                        "Use option -overwrite if you wish to overwrite it."
                    )
                kwargs = take_arguments(container.encode, self.argdict)
                stream = container.encode(to_be_created, **kwargs)
                for kwarg in kwargs:
                    del self.argdict[kwarg]
        # recurse on successfully opened file
        self.elements.append(_PathElement())
        self.elements[-1].streams.append(stream)
        self._unresolved_path = unmatched


def _split_path_containername(path):
    """Pare forward path until a recognised container name pattern is encountered."""
    for headpath in reversed((path, *path.parents)):
        if containers.identify_filename(headpath.name):
            subpath = path.relative_to(headpath)
            return headpath, subpath
    # no match
    return path, Path('.')


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
    message = f"Could not open container {instream.name}"
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
            "Transcoding stream '%s' with wrapper format `%s` in mode '%s'",
            instream.name, transcoder.format, mode
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
    if mode == 'r':
        message = f"Could not decode {instream.name}"
    else:
        message = f"Could not encode {instream.name}"
    if format:
        message += f': format specifier `{format}` not recognised'
    raise FileFormatError(message)
