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

from ..streams import Stream, DelayedWriterStream
from ..magic import FileFormatError
from ..base import encoders, decoders


@decoders.register(name='base64')
def decode_base64(instream):
    """Read from a base64-encoded binary file."""
    encoded_bytes = instream.read()
    data = base64.b64decode(encoded_bytes)
    name = Path(instream.name).stem
    return Stream.from_data(data, mode='r', name=name)


@encoders.register(linked=decode_base64)
def encode_base64(outstream, *, line_length:int=76):
    """
    Write to a base64-encoded binary file.

    line_length: length of each line of base64 encoded data (default: 76)
    """
    encode_func = _do_encode_base64
    name = Path(outstream.name).stem
    return DelayedWriterStream(
        outstream, encode_func, name,
        line_length=line_length,
    )


def _do_encode_base64(data, outstream, *, line_length):
    """Base64-encoded binary file."""
    encoded_bytes = base64.b64encode(data)
    bytesio = BytesIO(encoded_bytes)
    while True:
        line = bytesio.read(line_length)
        if not line:
            break
        outstream.write(line + b'\n')



@decoders.register(name='quopri')
def decode_quopri(instream):
    """Read from quoted-printable-encoded binary file."""
    encoded = instream.read()
    data = binascii.a2b_qp(encoded)
    name = Path(instream.name).stem
    return Stream.from_data(data, mode='r', name=name)


@encoders.register(linked=decode_quopri)
def encode_quopri(outstream, *, quote_tabs:bool=False):
    """
    Write to quoted-printable-encoded binary file.

    quote_tabs: encode tabs and spaces as QP (default: False)
    """
    encode_func = _do_encode_quopri
    name = Path(outstream.name).stem
    return DelayedWriterStream(
        outstream, encode_func, name,
        quote_tabs=quote_tabs,
    )


def _do_encode_quopri(data, outstream, *, quote_tabs):
    encoded = binascii.b2a_qp(data, quotetabs=quote_tabs, istext=False)
    outstream.write(encoded)
