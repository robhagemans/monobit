"""
monobit.storage.containers.yencode - yEncode format

(c) 2024 Rob Hagemans

with code from python3-yenc examples
https://github.com/oe-mirrors/python3-yenc/

> Copyright (C) 2003, 2011 Alessandro Duca <alessandro.duca@gmail.com>
>
> This library is free software; you can redistribute it and/or
> modify it under the terms of the GNU Lesser General Public
> License as published by the Free Software Foundation; either
> version 2.1 of the License, or (at your option) any later version.
>
> This library is distributed in the hope that it will be useful,
> but WITHOUT ANY WARRANTY; without even the implied warranty of
> MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
> Lesser General Public License for more details.
>
> You should have received a copy of the GNU Lesser General Public
> License along with this library; if not, write to the Free Software
> Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
"""

import logging
from io import BytesIO
from pathlib import Path
import re
from binascii import crc32

try:
    import yenc
except ImportError:
    yenc = None

from ..magic import FileFormatError, Sentinel
from ..base import containers
from ...base import Props
from ..containers import SerialContainer


if yenc:
    @containers.register(
        name='yenc',
        patterns=('*.yenc',),
        magic=(Sentinel(b'=ybegin '),),
        # last line starts with '=yend '
    )
    class YEncodeContainer(SerialContainer):
        """yEncode format container."""

        def decode(self, name):
            """
            Decode files from yEncode file. Accepts multiple, concatenated files.
            """
            return super().decode(name)

        def encode(self, name):
            """
            Encode files to yEncode file. Multiple files will be concatenated.
            """
            return super().encode(name)

        @classmethod
        def decode_all(cls, file_in):
            data = {}
            while file_in.peek(1):
                head_crc = trail_crc = None
                while True:
                    line = file_in.readline()
                    if line.startswith(b'=ybegin '):
                        metadata, name = line.split(b' name=')
                        name = name.rstrip().decode('latin-1')
                        header = _parse_header(metadata, '=ybegin ')
                        break
                    elif not line:
                        raise FileFormatError("No valid =ybegin header found.")
                if file_in.peek(7).startswith(b'=ypart '):
                    line = file_in.readline().rstrip()
                    part = _parse_header(line, '=ypart ')
                else:
                    part = Props(begin=0, end=header.size)
                with BytesIO() as file_out:
                    try:
                        dec, dec_crc = yenc.decode(file_in, file_out, int(header.size))
                    except yenc.Error as e:
                        raise FileFormatError(e) from e
                    garbage	= False
                    for line in file_in.read().splitlines():
                        if line.startswith(b'=yend '):
                            tailer = _parse_header(line, '=yend ')
                            break
                        elif not line:
                            continue
                        else:
                            garbage = True
                    else:
                        logging.warning("Couldn't find =yend trailer")
                    if garbage:
                        logging.warning("Garbage before =yend trailer")
                    if head_crc:
                        tmp_crc = header.crc.lower()
                    elif trail_crc:
                        tmp_crc = tailer.crc.lower()
                    else:
                        tmp_crc = dec_crc
                    if tmp_crc != dec_crc:
                        logging.warning(
                            "CRC32 mismatch: header: %s dec: %s", tmp_crc, dec_crc
                        )
                    if name not in data:
                        data[name] = bytearray(int(header.size))
                    data[name][int(part.begin):int(part.end)] = file_out.getvalue()
            return data

        @classmethod
        def _head(cls):
            return b''

        @classmethod
        def _tail(cls):
            return b''

        @classmethod
        def _separator(cls):
            return b'\r\n'

        @classmethod
        def _encode(cls, name, filedata, file_out):
            crc = b"%08x" % (0xFFFFFFFF & crc32(filedata))
            size = len(filedata)
            line = b"=ybegin line=128 size=%d crc32=%s name=%s\r\n"
            file_out.write(line % (size, crc, name.encode('latin-1')))
            with BytesIO(filedata) as file_in:
                try:
                    encoded, crc_out = yenc.encode(file_in, file_out, size)
                except Exception as e:
                    raise FileFormatError(e) from e
            line = b"=yend size=%d crc32=%s\r\n" % (encoded, crc_out.encode('ascii'))
            file_out.write(line)


    def _parse_header(line, prefix):
        try:
            line = line.decode('ascii').removeprefix(prefix)
            return Props(**dict(
                _kv.split('=')
                for _kv in line.split()
            ))
        except (ValueError, UnicodeError) as e:
            raise FileFormatError(f'Malformed ={prefix} header.') from e
