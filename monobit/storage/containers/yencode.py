"""
monobit.storage.containers.yencode - yEncode format

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
import yenc
import re
from binascii import crc32

from ..magic import FileFormatError
from ..base import containers
from .containers import FlatFilterContainer


NAME_RE = re.compile(br"^.*? name=(.+?)$")
LINE_RE = re.compile(br"^.*? line=(\d{3}) .*$")
SIZE_RE = re.compile(br"^.*? size=(\d+) .*$")
CRC32_RE = re.compile(br"^.*? crc32=(\w+)")


@containers.register(
    name='yenc',
    patterns=('*.yenc',),
    magic=(b'=ybegin ',),
    # last line starts with '=yend '
)
class YEncodeContainer(FlatFilterContainer):
    """yEncoded format container."""

    @classmethod
    def decode_all(cls, instream):
        data = {}
        while instream.peek(1):
            data |= cls._decode(instream)
        return data

    @classmethod
    def _decode(cls, file_in):
        head_crc = trail_crc = None
        while True:
            line = file_in.readline()
            if line.startswith(b"=ybegin "):
                try:
                    name, size = NAME_RE.match(line).group(1), int(SIZE_RE.match(line).group(1))
                    m_obj = CRC32_RE.match(line)
                    if m_obj:
                        head_crc = m_obj.group(1)
                except re.error as e:
                    raise FileFormatError("Malformed =ybegin header.") from e
                break
            elif not line:
                raise FileFormatError("No valid =ybegin header found.")
        with BytesIO() as file_out:
            try:
                dec, dec_crc = yenc.decode(file_in, file_out, size)
            except yenc.Error as e:
                raise FileFormatError(e) from e
            garbage	= False
            for line in file_in.read().split(b"\r\n"):
                if line.startswith(b"=yend "):
                    try:
                        size = int( SIZE_RE.match(line).group(1) )
                        m_obj = CRC32_RE.match(line)
                        if m_obj:
                            trail_crc = m_obj.group(1)
                    except re.error:
                        logging.warning("Malformed =yend trailer")
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
                tmp_crc = head_crc.decode("ascii").lower()
            elif trail_crc:
                tmp_crc = trail_crc.decode("ascii").lower()
            else:
                tmp_crc = dec_crc
            if tmp_crc != dec_crc:
                logging.warning("CRC32 mismatch: header: %s dec: %s", tmp_crc, dec_crc)
            return {
                name.decode('latin-1'): file_out.getvalue()
            }

    @classmethod
    def encode_all(cls, data, outstream):
        for name, filedata in data.items():
            cls._encode(filedata, outstream, name=name)
            outstream.write(b'\r\n')

    @classmethod
    def _encode(cls, filedata, file_out, *, name):
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
