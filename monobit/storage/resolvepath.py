"""
monobit.storage.resolvepath - archive, directory and wrapper traversal

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from pathlib import Path
from os.path import commonprefix

from ..plumbing import take_arguments
from .magic import FileFormatError, iter_funcs_from_registry
from .streams import StreamBase, Stream, KeepOpen
from .base import encoders, decoders, containers
from .containers import Container
from .containerformats.directory import Directory
from .pathutils import path_exists, match_path


class PathResolver:

    def __init__(
            self, *,
            root=None, path='', mode='r', overwrite=False, match_case=False,
            container_format='', argdict=None, make_dir=False,
        ):
        self.path = Path(path)
        self.mode = mode
        self.overwrite = overwrite
        self.match_case = match_case
        # container or stream on which we attch the path
        # this object is NOT owned by us but externaly provided
        # an further objects in the path will be ours to close
        if isinstance(root, Container):
            self._path_objects = [root]
            self._stream_objects = []
        else:
            self._path_objects = []
            self._stream_objects = [KeepOpen(root)]
        # subpath from last object in path_objects (empty if a stream)
        self._leafpath = self.path
        # subpath from last container
        self._container_subpath = self.path
        # format parameters
        self._container_format = container_format.split('.')
        self._make_dir = make_dir
        self.argdict = argdict
        self._outermost_path = None
        self._resolve()

    @classmethod
    def from_path(cls, path, **kwargs):
        """Create from path-like or string."""
        path = Path(path).resolve()
        here = Path('.').resolve()
        root = Path(commonprefix((path, here)))
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

    @property
    def _leaf(self):
        """Object (stream or container) at the end of path."""
        try:
            return self._stream_objects[-1]
        except IndexError:
            return self._path_objects[-1]

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
        # innermost existing path element
        existing, unmatched = match_path(self._leaf, self._leafpath, self.match_case)
        if Path(existing) == Path() and Path(unmatched) == Path():
            # path has resolved
            return
        if self.mode == 'r':
            try:
                # see if existing points to a file -> open it
                kwargs = take_arguments(container.decode, self.argdict)
                stream = container.decode(existing, **kwargs)
            except IsADirectoryError:
                if Path(unmatched) == Path():
                    # path has resolved; nothing further to open
                    return
                # innermost existing is a subdirectory
                # i.e. unmatched subpath does not exist
                if str(container):
                    message = f"{container}//{existing}//{unmatched} not found."
                else:
                    message = f"{existing}//{unmatched} not found."
                raise FileNotFoundError(message)
            else:
                # remove used arguments
                for kwarg in kwargs:
                    del self.argdict[kwarg]
        else:
            if unmatched != Path() and not container.is_dir(existing):
                if str(container):
                    message = f"Cannot append {unmatched} to {container}//{existing}."
                else:
                    message = f"Cannot append {unmatched} to {existing}."
                raise FileExistsError(message)
            # step forward until a container pattern is encountered, or we run out of path
            path_to_container, unmatched = _split_path_containername(unmatched)
            to_be_created = existing / path_to_container
            # innermost path element *to be created*
            # check if we're asked to create an file or a subdirectory
            # it's a subdirectory if (1) explicitly asked or (2) no suffix
            if self._make_dir or not to_be_created.suffixes:
                # innermost creatable should be a subdirectory
                return
            else:
                # innermost creatable should be a file -> create it
                if (
                        path_exists(container, to_be_created, self.match_case)
                        and not self.overwrite
                    ):
                    raise FileExistsError(
                        f"{container}//{to_be_created} already exists. "
                        "Use option -overwrite if you wish to overwrite it."
                    )
                if not self._outermost_path:
                    self._outermost_path = to_be_created
                kwargs = take_arguments(container.encode, self.argdict)
                stream = container.encode(to_be_created, **kwargs)
                for kwarg in kwargs:
                    del self.argdict[kwarg]
        # recurse on successfully opened file
        self._stream_objects.append(stream)
        self._leafpath = unmatched
        self._resolve()


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
