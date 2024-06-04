"""
monobit.storage.wrappers.uuencode - UUEncode format

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT

modified from the (deprecated) Python standard library uu module source code,
which carries these notices:

> Copyright 1994 by Lance Ellinghouse
> Cathedral City, California Republic, United States of America.
>                        All Rights Reserved
> Permission to use, copy, modify, and distribute this software and its
> documentation for any purpose and without fee is hereby granted,
> provided that the above copyright notice appear in all copies and that
> both that copyright notice and this permission notice appear in
> supporting documentation, and that the name of Lance Ellinghouse
> not be used in advertising or publicity pertaining to distribution
> of the software without specific, written prior permission.
> LANCE ELLINGHOUSE DISCLAIMS ALL WARRANTIES WITH REGARD TO
> THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
> FITNESS, IN NO EVENT SHALL LANCE ELLINGHOUSE CENTRUM BE LIABLE
> FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
> WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
> ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
> OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
>
> Modified by Jack Jansen, CWI, July 1995:
> - Use binascii module to do the actual line-by-line conversion
>   between ascii and binary. This results in a 1000-fold speedup. The C
>   version is still 5 times faster, though.
"""

import logging
import binascii
from io import BytesIO
from pathlib import Path

from ..magic import FileFormatError
from ..base import wrappers
from .wrappers import FilterWrapper


@wrappers.register(
    name='uuencode',
    magic=(b'begin ',),
    # ends with 'end\n'
)
class UUEncodeWrapper(FilterWrapper):
    """Quoted-printable format wrapper."""

    @staticmethod
    def decode(in_file, out_file):
        #
        # Read until a begin is encountered or we've exhausted the file
        #
        while True:
            hdr = in_file.readline()
            if not hdr:
                raise FileFormatError('No valid begin line found in input file')
            if not hdr.startswith(b'begin'):
                continue
            hdrfields = hdr.split(b' ', 2)
            if len(hdrfields) == 3 and hdrfields[0] == b'begin':
                try:
                    int(hdrfields[1], 8)
                    break
                except ValueError:
                    pass
        out_file.name = (
            hdrfields[2]
            .rstrip(b' \t\r\n\f')
            .decode('ascii', 'replace')
            .replace('\ufffd', '_')
        )
        #
        # Main decoding loop
        #
        s = in_file.readline()
        output = []
        while s and s.strip(b' \t\r\n\f') != b'end':
            try:
                data = binascii.a2b_uu(s)
            except binascii.Error as v:
                # Workaround for broken uuencoders by /Fredrik Lundh
                nbytes = (((s[0]-32) & 63) * 4 + 5) // 3
                data = binascii.a2b_uu(s[:nbytes])
            out_file.write(data)
            s = in_file.readline()

    @staticmethod
    def encode(in_file, out_file, *, mode=0o666, backtick=False):
        name = (
            str(in_file.name)
            .encode('ascii', 'replace')
            .replace(b'?', b'_')
        )
        out_file.write(
            (b'begin %o %s\n' % ((mode & 0o777), name))
        )
        data = in_file.read(45)
        while len(data) > 0:
            out_file.write(binascii.b2a_uu(data, backtick=backtick))
            data = in_file.read(45)
        if backtick:
            out_file.write(b'`\nend\n')
        else:
            out_file.write(b' \nend\n')
