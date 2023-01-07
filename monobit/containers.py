"""
monobit.containers - file containers

(c) 2021--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import os
import sys
import time
import logging
import itertools
from contextlib import contextmanager
import zipfile
import tarfile
import gzip
import lzma
import bz2
from pathlib import Path, PurePath, PurePosixPath

from .streams import (
    MagicRegistry, FileFormatError,
    StreamBase, StreamWrapper, Stream, KeepOpen,
    get_suffix, open_stream, get_name
)

DEFAULT_ROOT = 'fonts'


def get_bytesio(bytestring):
    """Workaround as our streams objects require a buffer."""
    return io.BufferedReader(io.BytesIO(bytestring))


class ContainerFormatError(FileFormatError):
    """Incorrect container format."""


containers = MagicRegistry()

def open_container(file, mode, overwrite=False):
    """Open container of the appropriate type."""
    if isinstance(file, Container):
        return file
    if not file:
        # no-container, will throw errors when used
        return Container(None)
    container_type = _identify_container(file, mode, overwrite)
    container = container_type(file, mode, overwrite=overwrite)
    logging.debug("Opening %s container `%s` for '%s'.", container_type.__name__, container.name, mode)
    return container

def _identify_container(file, mode, overwrite):
    """Get container of the appropriate type."""
    if not file:
        raise ValueError('No location provided.')
    # if it already is a directory there is no choice
    if isinstance(file, (str, Path)) and Path(file).is_dir():
        container_type = DirContainer
    else:
        container_type = containers.identify(file, do_open=(mode == 'r'))
    if not container_type:
        suffix = get_suffix(file)
        # output to file with no suffix - default to directory
        if mode == 'w' and not suffix and isinstance(file, (str, Path)):
            return DirContainer
        # no container type found
        raise ContainerFormatError('Expected container format, got non-container stream.')
    return container_type


class Container(StreamBase):
    """Base class for container types."""

    def __iter__(self):
        """List contents."""
        raise NotImplementedError

    def open(self, name, mode):
        """Open a binary stream in the container."""
        raise NotImplementedError

    def unused_name(self, stem, suffix):
        """Generate unique name for container file."""
        for i in itertools.count():
            if i:
                filename = '{}.{}.{}'.format(stem, i, suffix)
            else:
                filename = '{}.{}'.format(stem, suffix)
            if filename not in self:
                return filename

###################################################################################################
# directory

class DirContainer(Container):
    """Treat directory tree as a container."""

    def __init__(self, path, mode='r', *, overwrite=False):
        """Create directory wrapper."""
        # if empty path, this refers to the whole filesystem
        if not path:
            path = ''
        self._path = Path(path)
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode == 'w':
            logging.debug('Creating directory `%s`', self._path)
            # exist_ok raises FileExistsError only if the *target* already exists, not the parents
            self._path.mkdir(parents=True, exist_ok=overwrite)
        super().__init__(None, mode, str(self._path))

    def open(self, name, mode):
        """Open a stream in the container."""
        # mode in 'r', 'w'
        mode = mode[:1]
        pathname = Path(name)
        if mode == 'w':
            path = pathname.parent
            logging.debug('Creating directory `%s`', self._path / path)
            (self._path / path).mkdir(parents=True, exist_ok=True)
        # provide name relative to directory container
        file = Stream(self._path / pathname, mode=mode, name=str(pathname), overwrite=True)
        return file

    def __iter__(self):
        """List contents."""
        # don't walk the whole filesystem - no path is no contents
        if not self._path:
            return ()
        return (
            str((Path(_r) / _f).relative_to(self._path))
            for _r, _, _files in os.walk(self._path)
            for _f in _files
        )

    def __contains__(self, name):
        """File exists in container."""
        return (self._path / name).exists()


###################################################################################################
# zip archive

@containers.register('.zip', magic=(b'PK\x03\x04',))
class ZipContainer(Container):
    """Zip-file wrapper."""

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        # reading zipfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            # note file is externally provided so we shouldn't close it
            # but the BytesIO is ours
            stream = get_bytesio(file.read())
        else:
            stream = open_stream(file, mode, overwrite=overwrite)
        # create the zipfile
        try:
            self._zip = zipfile.ZipFile(stream, mode, compression=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipFile as exc:
            raise ContainerFormatError(exc) from exc
        super().__init__(stream, mode, self._zip.filename)
        # on output, put all files in a directory with the same name as the archive (without suffix)
        if mode == 'w':
            self._root = Path(self.name).stem or DEFAULT_ROOT
        else:
            self._root = ''
        # output files, to be written on close
        self._files = []


    def close(self):
        """Close the zip file, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            for file in self._files:
                logging.debug('Writing out `%s` to zip container `%s`.', file.name, self.name)
                bytearray = file.getvalue()
                file.close()
                self._zip.writestr(file.name, bytearray)
        try:
            self._zip.close()
        except EnvironmentError:
            # e.g. BrokenPipeError
            pass
        super().close()
        self.closed = True

    def __iter__(self):
        """List contents."""
        return (
            str(PurePosixPath(_name).relative_to(self._root))
            for _name in self._zip.namelist()
        )

    def open(self, name, mode):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        filename = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on zip container `%s`.', filename, self.name)
        if mode == 'r':
            return Stream(self._zip.open(filename, mode), mode=mode)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = KeepOpen(io.BytesIO(), mode=mode, name=filename)
            if filename in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', filename)
            self._files.append(newfile)
            return newfile



###################################################################################################
# tar archive

@containers.register('.tar')
class TarContainer(Container):
    """Tar-file wrapper."""

    def __init__(self, file, mode='r',*, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        # reading tarfile needs a seekable stream, drain to buffer if needed
        # note you can only do this once on the input stream!
        if (mode == 'r' and not isinstance(file, (str, Path)) and not file.seekable()):
            # note file is externally provided so we shouldn't close it
            # but the BytesIO is ours
            stream = get_bytesio(file.read())
        else:
            stream = open_stream(file, mode, overwrite=overwrite)
        # create the tarfile
        try:
            self._tarfile = tarfile.open(fileobj=stream, mode=mode)
        except tarfile.ReadError as exc:
            raise ContainerFormatError(exc) from exc
        super().__init__(stream, mode, self._tarfile.name)
        # on output, put all files in a directory with the same name as the archive (without suffix)
        if mode == 'w':
            self._root = Path(self.name).stem or DEFAULT_ROOT
        else:
            self._root = ''
        # output files, to be written on close
        self._files = []

    def close(self):
        """Close the tar file, ignoring errors."""
        if self.mode == 'w' and not self.closed:
            for file in self._files:
                name = file.name
                logging.debug('Writing out `%s` to tar container `%s`.', name, self.name)
                tinfo = tarfile.TarInfo(name)
                tinfo.mtime = time.time()
                tinfo.size = len(file.getvalue())
                file.seek(0)
                self._tarfile.addfile(tinfo, file)
                file.close()
        try:
            self._tarfile.close()
        except EnvironmentError:
            # e.g. BrokenPipeError
            pass
        super().close()
        self.closed = True

    def __iter__(self):
        """List contents."""
        # list regular files only, skip symlinks and dirs and block devices
        return (_ti.name for _ti in self._tarfile.getmembers() if _ti.isfile())

    def open(self, name, mode):
        """Open a stream in the container."""
        name = str(PurePosixPath(self._root) / name)
        mode = mode[:1]
        # always open as binary
        logging.debug('Opening file `%s` on tar container `%s`.', name, self.name)
        if mode == 'r':
            file = self._tarfile.extractfile(name)
            # .name is not writeable, so we need to wrap
            return Stream(file, mode, name=name)
        else:
            # stop BytesIO from being closed until we want it to be
            newfile = KeepOpen(io.BytesIO(), mode=mode, name=name)
            if name in self._files:
                logging.warning('Creating multiple files of the same name `%s`.', name)
            self._files.append(newfile)
            return newfile


###################################################################################################
# single-file compression

class Compressor(Container):
    """Base class for compression helpers."""

    format = ''
    compressor = None

    def __init__(self, infile, mode='r', *, overwrite=False):
        stream = Stream(infile, mode, overwrite=overwrite)
        super().__init__(stream, mode)
        # drop the .gz etc
        last_suffix = get_suffix(self.name)
        if last_suffix == self.format:
            self._content_name = self.name[:-1-len(last_suffix)]
        else:
            self._content_name = self.name

    def __iter__(self):
        return iter((self._content_name,))

    def open(self, name='', mode=''):
        """Open a stream in the container."""
        mode = mode[:1] or self.mode
        wrapped = self.compressor.open(self._stream, mode + 'b')
        wrapped = Stream(wrapped, mode, name=self._content_name)
        logging.debug(
            "Opening %s-compressed stream `%s` on `%s` for mode '%s'",
            self.format, wrapped.name, self.name, mode
        )
        return wrapped


@containers.register('.gz', magic=(b'\x1f\x8b',))
class GzipCompressor(Compressor):
    compressor = gzip

@containers.register('.xz', magic=(b'\xFD7zXZ\x00',))
class XZCompressor(Compressor):
    compressor = lzma

# the magic is a 'maybe'
@containers.register('.lzma', magic=(b'\x5d\0\0',))
class LzmaCompressor(Compressor):
    compressor = lzma

@containers.register('.bz2', magic=(b'BZh',))
class Bzip2Compressor(Compressor):
    compressor = bz2


##############################################################################
# Mac data/resource fork containers

class MacContainer(Container):
    """Mac data/resource fork container."""

    parse = None

    def __init__(self, file, mode='r', *, overwrite=False):
        """Create wrapper."""
        # mode really should just be 'r' or 'w'
        mode = mode[:1]
        if mode != 'r':
            raise ContainerFormatError(
                'Writing to Mac resource container is not implemented.'
            )
        with open_stream(file, mode, overwrite=overwrite) as stream:
            self._fork_name, self._data, self._rsrc = self.parse(stream)
        super().__init__(None, mode, stream.name)

    def __iter__(self):
        """List contents."""
        contents = []
        if self._data:
            contents.append(f'{self._fork_name}.data')
        if self._rsrc:
            contents.append(f'{self._fork_name}.rsrc')
        return iter(contents)

    def open(self, name, mode):
        """Open a stream in the container."""
        # using posixpath for internal paths in the archive
        # as forward slash should always work, but backslash would fail on unix
        mode = mode[:1]
        if mode != 'r':
            raise ContainerFormatError(
                'Writing to Mac resource container is not implemented.'
            )
        filename = str(name)[-4:].lower()
        if filename not in ('data', 'rsrc'):
            raise FileNotFoundError(
                'Stream name on Mac resource container must end with `rsrc` or `data`'
            )
        filename = f'{self._fork_name}.{filename}'
        # always open as binary
        logging.debug(
            'Opening fork `%s` on %s `%s`.', filename,
            type(self).__name__, self.name
        )
        if filename.endswith('data'):
            fork = self._data
        else:
            fork = self._rsrc
        if not fork:
            raise FileNotFoundError(filename)
        newfile = Stream(get_bytesio(fork), mode=mode, name=filename)
        return newfile


###############################################################################
# BinHex 4.0 container
# https://files.stairways.com/other/binhex-40-specs-info.txt

from binascii import crc_hqx
from itertools import zip_longest

from .struct import big_endian as be


_BINHEX_CODES = (
    '''!"#$%&'()*+,-012345689@ABCDEFGHIJKLMNPQRSTUVXYZ[`abcdefhijklmpqr'''
)
_BINHEX_CODEDICT = {_BINHEX_CODES[_i]: _i for _i in range(64)}

_BINHEX_HEADER = be.Struct(
    type='4s',
    auth='4s',
    flag='uint16',
    dlen='uint32',
    rlen='uint32',
)
_CRC = be.Struct(
    crc='uint16',
)

def _parse_binhex(stream):
    """Parse a BinHex 4.0 file."""
    front, binhex, *back = stream.text.read().split(':')
    if 'BinHex 4.0' not in front:
        logging.warning('No BinHex 4.0 signature found.')
    back = ''.join(back).strip()
    if back:
        logging.warning('Additional data found after BinHex section: %r', back)
    binhex = ''.join(binhex.split('\n'))
    # decode into 6-bit ints
    data = (_BINHEX_CODEDICT[_c] for _c in binhex)
    # convert to bit sequence
    bits = ''.join(bin(_d)[2:].zfill(6) for _d in data)
    # group into chunks of 8
    args = [iter(bits)] * 8
    octets = (''.join(_t) for _t in zip_longest(*args, fillvalue='0'))
    # convert to bytes
    bytestr = bytes(int(_s, 2) for _s in octets)
    # find run-length encoding marker
    chunks = bytestr.split(b'\x90')
    out = bytearray(chunks[0])
    for c in chunks[1:]:
        if c:
            # run-length byte
            repeat = c[0]
        else:
            # ...\x90\x90... -> ...', '', '...
            repeat = 0x90
        if not repeat:
            # zero-byte is placeholder for just 0x90
            out += b'\x90'
        else:
            # apply RLE. the last byte counts as the first of the run
            out += out[-1:] * (repeat-1)
        out += c[1:]
    # decode header
    length = out[0]
    name = bytes(out[1:1+length]).decode('mac-roman')
    if out[1+length] != 0:
        logging.warning('No null byte after name')
    header = _BINHEX_HEADER.from_bytes(out, 2+length)
    logging.debug(header)
    offset = 2 + length + _BINHEX_HEADER.size
    crc_header = out[:offset]
    hc = _CRC.from_bytes(out, offset)
    offset += _CRC.size
    if crc_hqx(crc_header, 0) != hc.crc:
        logging.error('CRC fault in header')
    data = out[offset:offset+header.dlen]
    offset += header.dlen
    dc = _CRC.from_bytes(out, offset)
    offset += _CRC.size
    rsrc = out[offset:offset+header.rlen]
    offset += header.rlen
    rc = _CRC.from_bytes(out, offset)
    if crc_hqx(data, 0) != dc.crc:
        logging.error('CRC fault in data fork')
    if crc_hqx(rsrc, 0) != rc.crc:
        logging.error('CRC fault in resource fork')
    return name, data, rsrc


@containers.register(
    '.hqx', magic=(
        b'(This file must be converted',
        b'\r(This file must be converted',
    ),
)
class BinHexContainer(MacContainer):
    """BinHex 4.0 Container."""
    parse = staticmethod(_parse_binhex)


##############################################################################
# MacBinary container
# v1: https://www.cryer.co.uk/file-types/b/bin_/original_mac_binary_format_proposal.htm
# v2: https://files.stairways.com/other/macbinaryii-standard-info.txt
# v2 defines additional fields inside an area zeroed in v1. we can ignore them.

from .binary import align


_MACBINARY_HEADER = be.Struct(
    # Offset 000-Byte, old version number, must be kept at zero for compatibility
    old_version='byte',
    # Offset 001-Byte, Length of filename (must be in the range 1-63)
    filename_length='byte',
    # Offset 002-1 to 63 chars, filename (only "length" bytes are significant).
    filename='63s',
    # Offset 065-Long Word, file type (normally expressed as four characters)
    file_type='4s',
    # Offset 069-Long Word, file creator (normally expressed as four characters)
    file_creator='4s',
    # Offset 073-Byte, original Finder flags
    original_finder_flags='byte',
    # Offset 074-Byte, zero fill, must be zero for compatibility
    zero_0='byte',
    # Offset 075-Word, file's vertical position within its window.
    window_vert='word',
    # Offset 077-Word, file's horizontal position within its window.
    window_horiz='word',
    # Offset 079-Word, file's window or folder ID.
    window_id='word',
    # Offset 081-Byte, "Protected" flag (in low order bit).
    protected='byte',
    # Offset 082-Byte, zero fill, must be zero for compatibility
    zero_1='byte',
    # Offset 083-Long Word, Data Fork length (bytes, zero if no Data Fork).
    data_length='dword',
    # Offset 087-Long Word, Resource Fork length (bytes, zero if no R.F.).
    rsrc_length='dword',
    # Offset 091-Long Word, File's creation date
    creation_date='dword',
    # Offset 095-Long Word, File's "last modified" date.
    last_modified_date='dword',
    # Offset 099-Word, length of Get Info comment to be sent after the resource
    # fork (if implemented, see below).
    get_info_length='word',
    # *Offset 101-Byte, Finder Flags, bits 0-7. (Bits 8-15 are already in byte 73)
    finder_flags='byte',
    # *Offset 116-Long Word, Length of total files when packed files are unpacked.
    packed_length='dword',
    # *Offset 120-Word, Length of a secondary header.  If this is non-zero,
    #              Skip this many bytes (rounded up to the next multiple of 128)
    #              This is for future expansion only, when sending files with
    #              MacBinary, this word should be zero.
    second_header_length='dword',
    # *Offset 122-Byte, Version number of Macbinary II that the uploading program
    # is written for (the version begins at 129)
    writer_version='byte',
    # *Offset 123-Byte, Minimum MacBinary II version needed to read this file
    # (start this value at 129 129)
    reader_version='byte',
    # *Offset 124-Word, CRC of previous 124 bytes
    crc='word',
    # from v1 desc:
    # > 126 2 Reserved for computer type and OS ID
    # > (this field will be zero for the current Macintosh).
    reserved='word',
    # *This is newly defined for MacBinary II.
)

def _parse_macbinary(stream):
    """Parse a MacBinary file."""
    data = stream.read()
    header = _MACBINARY_HEADER.from_bytes(data)
    ofs = 128
    if header.old_version != 0:
        raise FileFormatError(
            'Not a MacBinary file: incorrect version field'
            f' ({header.old_version}).'
        )
    if header.writer_version > 128:
        ofs += align(header.second_header_length, 7)
    data_fork = data[ofs:ofs+header.data_length]
    ofs += align(header.data_length, 7)
    rsrc_fork = data[ofs:ofs+header.rsrc_length]
    name = header.filename.decode('mac-roman').strip()
    return name, data_fork, rsrc_fork


@containers.register('.bin')
class MacBinaryContainer(MacContainer):
    """MacBinary Container."""
    parse = staticmethod(_parse_macbinary)


##############################################################################
# AppleSingle/AppleDouble container
# v1: see https://web.archive.org/web/20160304101440/http://kaiser-edv.de/documents/Applesingle_AppleDouble_v1.html
# v2: https://web.archive.org/web/20160303215152/http://kaiser-edv.de/documents/AppleSingle_AppleDouble.pdf
# the difference between v1 and v2 affects the file info sections
# not the resource fork which is what we care about

_APPLESINGLE_MAGIC = 0x00051600
_APPLEDOUBLE_MAGIC = 0x00051607


_APPLE_HEADER = be.Struct(
    magic='uint32',
    version='uint32',
    home_fs='16s',
    number_entities='uint16',
)
_APPLE_ENTRY = be.Struct(
    entry_id='uint32',
    offset='uint32',
    length='uint32',
)

# Entry IDs
_ID_DATA = 1
_ID_RESOURCE = 2
_ID_NAME = 3

_APPLE_ENTRY_TYPES = {
    1: 'data fork',
    2: 'resource fork',
    3: 'real name',
    4: 'comment',
    5: 'icon, b&w',
    6: 'icon, color',
    7: 'file info', # v1 only
    8: 'file dates info', # v2
    9: 'finder info',
    # the following are all v2
    10: 'macintosh file info',
    11: 'prodos file info',
    12: 'ms-dos file info',
    13: 'short name',
    14: 'afp file info',
    15: 'directory id',
}


def _parse_apple_container(stream):
    """Parse an AppleSingle or AppleDouble file."""
    data = stream.read()
    header = _APPLE_HEADER.from_bytes(data)
    if header.magic == _APPLESINGLE_MAGIC:
        container = 'AppleSingle'
    elif header.magic == _APPLEDOUBLE_MAGIC:
        container = 'AppleDouble'
    else:
        raise FileFormatError('Not an AppleSingle or AppleDouble file.')
    entry_array = _APPLE_ENTRY.array(header.number_entities)
    entries = entry_array.from_bytes(data, _APPLE_HEADER.size)
    name, data_fork, rsrc_fork = '', b'', b''
    for i, entry in enumerate(entries):
        entry_type = _APPLE_ENTRY_TYPES.get(entry.entry_id, 'unknown')
        logging.debug(
            '%s container: entry #%d, %s [%d]',
            container, i, entry_type, entry.entry_id
        )
        if entry.entry_id == _ID_RESOURCE:
            rsrc_fork = data[entry.offset:entry.offset+entry.length]
        if entry.entry_id == _ID_DATA:
            data_fork = data[entry.offset:entry.offset+entry.length]
        if entry.entry_id == _ID_NAME:
            name = data[entry.offset:entry.offset+entry.length]
            name = name.decode('mac-roman')
    return name, data_fork, rsrc_fork



@containers.register(
    '.as',
    magic=(
        _APPLESINGLE_MAGIC.to_bytes(4, 'big'),
    ),
)
class AppleSingleContainer(MacContainer):
    """AppleSingle Container."""
    parse = staticmethod(_parse_apple_container)


@containers.register(
    '.adf', #'rsrc',
    magic=(
        _APPLEDOUBLE_MAGIC.to_bytes(4, 'big'),
    ),
)
class AppleDoubleContainer(MacContainer):
    """AppleDouble Container."""
    parse = staticmethod(_parse_apple_container)
