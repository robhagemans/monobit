"""
monobit.storage.wrappers.bintext - text-encoded binary formats

(c) 2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
import base64
import binascii
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
    def decode(instream, outstream):
        encoded_bytes = instream.read()
        data = base64.b64decode(encoded_bytes)
        outstream.write(data)

    @staticmethod
    def encode(instream, outstream, *, line_length):
        data = instream.read()
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
            quote_tabs:bool=False,
        ):
        """
        Quoted-printable-encoded binary file.

        quote_tabs: encode tabs and spaces as QP (default: False)
        """
        self.encode_kwargs = dict(
            quote_tabs=quote_tabs,
        )
        super().__init__(stream, mode)

    @staticmethod
    def decode(instream, outstream):
        encoded = instream.read()
        data = binascii.a2b_qp(encoded)
        outstream.write(data)

    @staticmethod
    def encode(instream, outstream, *, quote_tabs):
        data = instream.read()
        encoded = binascii.b2a_qp(data, quotetabs=quote_tabs, istext=False)
        outstream.write(encoded)
