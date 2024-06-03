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
