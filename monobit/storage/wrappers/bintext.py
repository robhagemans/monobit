"""
monobit.storage.wrappers.bintext - text-encoded binary formats

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import base64
# import quopri
import binascii
from email import quoprimime
from io import BytesIO
from pathlib import Path

from ..streams import Stream
from ..magic import FileFormatError
from ..base import wrappers
from .wrappers import FilterWrapper


@wrappers.register(name='base64')
class Base64Wrapper(FilterWrapper):
    """Base64 format wrapper."""

    def __init__(
            self, stream, mode='r',
            *,
            line_length:int=76,
        ):
        """
        Base64-encoded binary file.

        line_length: length of each line of base64 encoded data (default: 76)
        """
        self.encode_kwargs = dict(
            line_length=line_length,
        )
        super().__init__(stream, mode)

    @staticmethod
    def decode(instream):
        encoded_bytes = instream.read()
        data = base64.b64decode(encoded_bytes)
        return data

    @staticmethod
    def encode(data, outstream, *, line_length):
        encoded_bytes = base64.b64encode(data)
        bytesio = BytesIO(encoded_bytes)
        while True:
            line = bytesio.read(line_length)
            if not line:
                break
            outstream.write(line + b'\n')


@wrappers.register(name='quopri')
class QuotedPrintableWrapper(FilterWrapper):
    """Quoted-printable format wrapper."""

    def __init__(
            self, stream, mode='r',
            *,
            line_length:int=76,
        ):
        """
        Quoted-printable-encoded binary file.

        line_length: length of each line of base64 encoded data (default: 76)
        """
        self.encode_kwargs = dict(
            line_length=line_length,
        )
        super().__init__(stream, mode)

    @staticmethod
    def decode(instream):
        encoded = instream.read()
        data = binascii.a2b_qp(encoded)
        return data

    @staticmethod
    def encode(data, outstream, *, line_length):
        outstream = outstream.text
        # use quoprimime (undocumented?) to get the line breaks right
        # takes str input, use latin-1 to represent bytes as u+0000..u+00ff
        data = data.decode('latin-1')
        encoded_str = quoprimime.body_encode(data, maxlinelen=line_length)
        outstream.write(encoded_str)


###############################################################################
# UUEncode

# some source code taken from deprecated Python standard uu module,
# which carries this notice:
#
# Copyright 1994 by Lance Ellinghouse
# Cathedral City, California Republic, United States of America.
#                        All Rights Reserved
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Lance Ellinghouse
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
# LANCE ELLINGHOUSE DISCLAIMS ALL WARRANTIES WITH REGARD TO
# THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS, IN NO EVENT SHALL LANCE ELLINGHOUSE CENTRUM BE LIABLE
# FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
# Modified by Jack Jansen, CWI, July 1995:
# - Use binascii module to do the actual line-by-line conversion
#   between ascii and binary. This results in a 1000-fold speedup. The C
#   version is still 5 times faster, though.
# - Arguments more compliant with python standard

@wrappers.register(name='uuencode')
class UUEncodeWrapper(FilterWrapper):
    """Quoted-printable format wrapper."""

    @staticmethod
    def decode(in_file):
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
            output.append(data)
            s = in_file.readline()
        # note we're ignoring the filename
        return b''.join(output)

    @staticmethod
    def encode(in_data, out_file):
        name = Path(out_file.name).stem
        mode = 0o666
        backtick = False
        in_file = BytesIO(in_data)
        out_file.write(('begin %o %s\n' % ((mode & 0o777), name)).encode("ascii"))
        data = in_file.read(45)
        while len(data) > 0:
            out_file.write(binascii.b2a_uu(data, backtick=backtick))
            data = in_file.read(45)
        if backtick:
            out_file.write(b'`\nend\n')
        else:
            out_file.write(b' \nend\n')
