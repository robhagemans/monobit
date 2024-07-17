"""
monobit.storage.containers.sourcecoded - binary files embedded in C/Python/JS source files

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import string
import logging
from pathlib import Path

from ..magic import FileFormatError
from ..base import containers
from ..containers.containers import FlatFilterContainer
from ..utils.source import (
    strip_line_comments, read_array, decode_array, clean_identifier,
    encode_array, to_identifier,
    CCode, PythonCode, PythonTupleCode, JSONCode, PascalCode,
)

class _CodedBinaryContainer(FlatFilterContainer):

    def __init__(
            self, stream, mode='r',
            delimiters:str='',
            comment:str='',
            # reader params
            block_comment:str='',
            assign:str='',
            # writer params
            assign_template:str='',
            separator:str='',
            final_separator:bool=None,
            bytes_per_line:int=16,
            pre:str='',
            post:str='',
        ):
        """
        Extract binary file encoded in source code.

        delimiters: delimiter characters surrounding array definition. (use language default)
        comment: comment character. (use language default)
        block_comment: block comment character. (use language default)
        assign: assignment character. (use language default)
        separator: character separating statements. (use language default)
        final_separator: separator is written on the last statement. (use language default)
        assign_template: format of assignment statement, used on write. (use language default)
        bytes_per_line: number of bytes to write to one line. (default: 16)
        pre: characters needed at start of file. (use language default)
        post: characters needed at end of file. (use language default)
        """
        cls = type(self)
        super().__init__(
            stream, mode,
            decode_kwargs=dict(
                delimiters=delimiters or cls.delimiters,
                comment=comment or cls.comment,
                block_comment=block_comment or cls.block_comment,
                assign=assign or cls.assign,
                int_conv=cls.int_conv,
            ),
            encode_kwargs=dict(
                delimiters=delimiters or cls.delimiters,
                comment=comment or cls.comment,
                assign_template=assign_template or cls.assign_template,
                bytes_per_line=bytes_per_line or cls.bytes_per_line,
                conv_int=cls.conv_int,
                # container writer parameters
                separator=separator or cls.separator,
                pre=pre or cls.pre,
                post=post or cls.post,
            )
        )

    ###########################################################################
    # reader

    @classmethod
    def decode_all(
            cls, instream, *,
            delimiters, comment, block_comment, assign, int_conv
        ):
        """Generator to decode all identifiers with payload."""
        instream = instream.text
        start, end = delimiters
        found_identifier = ''
        data = {}
        for line in instream:
            line = strip_line_comments(line, comment, block_comment)
            if assign in line:
                found_identifier, _, _ = line.partition(assign)
                logging.debug('Found assignment to `%s`', found_identifier)
                found_identifier = clean_identifier(found_identifier)
            if found_identifier and start in line:
                _, line = line.split(start)
                coded_data = read_array(
                    instream, line, start, end,
                    comment, block_comment,
                )
                decoded_data = decode_array(coded_data, int_conv)
                data[found_identifier] = decoded_data
                if not decoded_data:
                    logging.warning(
                        "Could not decode data for identifier '%s'",
                        found_identifier
                    )
                found_identifier = ''
        return data

    ###############################################################################
    # writer

    @classmethod
    def encode_all(
            cls, data, outstream, *,
            pre, separator, post,
            **kwargs
        ):
        outstream = outstream.text
        outstream.write(pre)
        for count, (name, filedata) in enumerate(data.items()):
            cls.encode(
                filedata,
                outstream=outstream,
                name=name,
                **kwargs
            )
            if count < len(data) - 1:
                outstream.write(separator)
        outstream.write(post)

    @classmethod
    def encode(
            cls, rawbytes, outstream, *, name,
            assign_template, delimiters, comment,
            bytes_per_line, conv_int,
        ):
        """
        Generate font file encoded as source code.

        name: Identifier to use.
        assign_template: assignment operator. May include `identifier` and `bytesize` variable.
        delimiters: Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
        comment: Line comment character(s).
        bytes_per_line: number of encoded bytes in a source line
        conv_int: converter function for int values
        """
        if len(delimiters) < 2:
            raise ValueError('A start and end delimiter must be given. E.g. []')
        # remove non-ascii
        identifier = name.encode('ascii', 'ignore').decode('ascii')
        identifier = to_identifier(identifier)
        assign = assign_template.format(
            identifier=identifier, bytesize=len(rawbytes)
        )
        array = encode_array(rawbytes, delimiters, bytes_per_line, conv_int)
        outstream.write(assign)
        outstream.write(array)


@containers.register(
    name='c',
    patterns=('*.c', '*.cc', '*.cpp', '*.h')
)
class CCodedBinary(_CodedBinaryContainer, CCode):
    """C source code wrapper."""


@containers.register(
    name='json',
    patterns=('*.js', '*.json',),
)
class JSONCodedBinary(_CodedBinaryContainer, JSONCode):
    """JSON wrapper."""


@containers.register(
    name='python',
    patterns=('*.py',),
)
class PythonCodedBinary(_CodedBinaryContainer, PythonCode):
    """Python source code wrapper, using lists."""


@containers.register(
    name='python-tuple',
    patterns=('*.py',),
)
class PythonTupleCodedBinary(_CodedBinaryContainer, PythonTupleCode):
    """Python source code wrapper, using tuples."""


@containers.register(
    name='pascal',
    patterns=('*.pas',),
)
class PascalCodedBinary(_CodedBinaryContainer, PascalCode):
    """Pascal source code wrapper."""
