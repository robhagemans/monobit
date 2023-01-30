"""
monobit.formats.source - fonts embedded in C/Python/JS source files

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from io import BytesIO
import string

from ..binary import ceildiv
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..streams import FileFormatError
from ..basetypes import Coord
from .raw import load_bitmap


_C_PARAMS = dict(
    delimiters='{}',
    comment='//',
)

_JS_PARAMS = dict(
    delimiters='[]',
    comment='//',
)

_PY_PARAMS = dict(
    delimiters='[]',
    comment='#',
)

###################################################################################################

@loaders.register('c', 'cc', 'cpp', 'h', name='c')
def load_c(
        infile, where=None, *,
        identifier:str='',
        cell:Coord=(8, 8), count:int=-1, offset:int=0, padding:int=0,
        align:str='left', strike_count:int=1, strike_bytes:int=-1,
        first_codepoint:int=0
    ):
    """
    Extract font from bitmap encoded in C or C++ source code.

    identifier: text at start of line where bitmap starts. (default: first array literal {})
    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyphs (default: 0)
    count: number of glyphs to extract (<=0 means all; default: all glyphs)
    align: alignment of glyph in byte (left for most-, right for least-significant; default: left)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    first_codepoint: first code point in bitmap (default: 0)
    """
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, count=count, offset=offset, padding=padding,
        align=align, strike_count=strike_count, strike_bytes=strike_bytes,
        first_codepoint=first_codepoint,
        **_C_PARAMS
    )

@loaders.register('js', 'json', name='json')
def load_json(
        infile, where=None, *,
        identifier:str='',
        cell:Coord=(8, 8), count:int=-1, offset:int=0, padding:int=0,
        align:str='left', strike_count:int=1, strike_bytes:int=-1,
        first_codepoint:int=0
    ):
    """
    Extract font from bitmap encoded in JavaScript source code.

    identifier: text at start of line where bitmap starts (default: first list [])
    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyphs (default: 0)
    count: number of glyphs to extract (<=0 means all; default: all)
    align: alignment of glyph in byte (left for most-, right for least-significant; default: left)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    first_codepoint: first code point in bitmap (default: 0)
    """
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, count=count, offset=offset, padding=padding,
        align=align, strike_count=strike_count, strike_bytes=strike_bytes,
        first_codepoint=first_codepoint,
        **_JS_PARAMS
    )

@loaders.register('py', name='python')
def load_python(
        infile, where=None, *,
        identifier:str='',
        cell:Coord=(8, 8), count:int=-1, offset:int=0, padding:int=0,
        align:str='left', strike_count:int=1, strike_bytes:int=-1,
        first_codepoint:int=0
    ):
    """
    Extract font from bitmap encoded as a list in Python source code.

    identifier: text at start of line where bitmap starts (default: first list [])
    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyphs (default: 0)
    count: number of glyphs to extract (<=0 means all; default: all)
    align: alignment of glyph in byte (left for most-, right for least-significant; default: left)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    first_codepoint: first code point in bitmap (default: 0)
    """
    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, count=count, offset=offset, padding=padding,
        align=align, strike_count=strike_count, strike_bytes=strike_bytes,
        first_codepoint=first_codepoint,
        **_PY_PARAMS
    )

@loaders.register(name='source')
def load_source(
        infile, where=None, *,
        identifier:str='', delimiters:str='{}', comment:str='//',
        cell:Coord=(8, 8), count:int=-1, strike_count:int=1, strike_bytes:int=-1,
        offset:int=0, padding:int=0, align:str='left',
        first_codepoint:int=0
    ):
    """
    Extract font from bitmap encoded in source code.

    identifier: text at start of line where bitmap starts (default: first delimiter)
    delimiters: pair of delimiters that enclose the bitmap (default: {})
    comment: string that introduces inline comment (default: //)
    cell: size X,Y of character cell (default: 8x8)
    offset: number of bytes in file before bitmap starts (default: 0)
    padding: number of bytes between encoded glyphs (default: 0)
    count: number of glyphs to extract (<=0 means all; default: all)
    align: alignment of glyph in byte (left for most-, right for least-significant; default: left)
    strike_count: number of glyphs in glyph row (<=0 for all; default: 1)
    strike_bytes: strike width in bytes (<=0 means as many as needed to fit the glyphs; default: as needed)
    first_codepoint: first code point in bitmap (default: 0)
    """

    return _load_coded_binary(
        infile, where, identifier=identifier,
        cell=cell, count=count, offset=offset, padding=padding,
        align=align, strike_count=strike_count, strike_bytes=strike_bytes,
        first_codepoint=first_codepoint,
        delimiters=delimiters, comment=comment
    )


def _load_coded_binary(
        infile, where, identifier, delimiters, comment,
        cell, count, offset, padding, align, strike_count, strike_bytes, first_codepoint
    ):
    """Load font from binary encoded in source code."""
    width, height = cell
    payload = _get_payload(infile.text, identifier, delimiters, comment)
    data = bytes(_int_from_c(_s) for _s in payload.split(',') if _s)
    bytesio = BytesIO(data[offset:])
    return load_bitmap(
        bytesio, width, height, count, padding, align, strike_count, strike_bytes, first_codepoint
    )

def _int_from_c(cvalue):
    """Parse integer from c code."""
    # suffixes
    while cvalue[-1:].lower() in ('u', 'l'):
        cvalue = cvalue[:-1]
    if cvalue.startswith('0') and cvalue[1:2] and cvalue[1:2] in string.digits:
        # C / Python-2 octal 0777
        cvalue = '0o' + cvalue[1:]
    # 0x, 0b, decimals - like Python
    return int(cvalue, 0)

def _get_payload(instream, identifier, delimiters, comment):
    """Find the identifier and get the part between delimiters."""
    start, end = delimiters
    for line in instream:
        if comment in line:
            line, _ = line.split(comment, 1)
        line = line.strip(' \r\n')
        if identifier in line:
            if identifier:
                _, line = line.split(identifier)
            if start in line:
                _, line = line.split(start)
                break
    else:
        raise ValueError('No payload with identifier `{}` found in file'.format(identifier))
    if end in line:
        line, _ = line.split(end, 1)
        return line
    payload = [line]
    for line in instream:
        if comment in line:
            line, _ = line.split(comment, 1)
        line = line.strip(' \r\n')
        if start in line:
            _, line = line.split(start, 1)
        if end in line:
            line, _ = line.split(end, 1)
            payload.append(line)
            break
        if line:
            payload.append(line)
    return ''.join(payload)


###################################################################################################

@savers.register('c', linked=load_c)
def save_c(fonts, outstream, where=None):
    """
    Save font to bitmap encoded in C source code.
    """
    return _save_coded_binary(fonts, outstream, 'char font_{compactname}[{bytesize}] = ', **_C_PARAMS)

@savers.register('py', 'python', linked=load_python)
def save_python(fonts, outstream, where=None):
    """
    Save font to bitmap encoded in Python source code.
    """
    return _save_coded_binary(fonts, outstream, 'font_{compactname} = ', **_PY_PARAMS)

@savers.register('json', linked=load_json)
def save_json(fonts, outstream, where=None):
    """
    Save font to bitmap encoded in JSON code.
    """
    return _save_coded_binary(fonts, outstream, '', **_JS_PARAMS)

@savers.register('source', linked=load_source)
def save_source(
        fonts, outstream, where=None, *,
        identifier:str, assign:str='=', delimiters:str='{}', comment:str='//',
    ):
    """
    Save font to bitmap encoded in source code.
    """
    return _save_coded_binary(fonts, outstream, f'{identifier} {assign} ', delimiters, comment)

def _save_coded_binary(fonts, outstream, assignment_pattern, delimiters, comment):
    """
    Generate bitmap encoded source code from a font.

    Args:
        fonts (List[Font]): Exactly one font must be given.
        outstream: Stream to write the source code to.
        assignment_pattern: Format pattern for the assignment statement. May include `compactname` amd `bytesize` variables.
        delimiters (str): Must contain two characters, building the opening and closing delimiters of the collection. E.g. []
        comment (str): Line Comment character(s). Currently not used.

    Raises:
        FileFormatError: If more the one Font is passed or if it is not a character-cell font.
        ValueError: If delimiter does not contain at least two characters.

    Returns:
        Font: Used font.
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to source file.')
    font = fonts[0]
    outstream = outstream.text
    # check if font is fixed-width and fixed-height
    if font.spacing != 'character-cell':
        raise FileFormatError(
            'This format only supports character-cell fonts.'
        )
    if len(delimiters) < 2:
        raise ValueError('A start and end delimiter must be given. E.g. []')
    start_delimiter = delimiters[0]
    end_delimiter = delimiters[1]
    # build the identifier
    ascii_name = font.name.encode('ascii', 'ignore').decode('ascii')
    ascii_name = ''.join(_c if _c.isalnum() else '_' for _c in ascii_name)
    width, height = font.raster_size
    bytesize = ceildiv(width, 8) * height * len(font.glyphs)
    assignment = assignment_pattern.format(compactname=ascii_name, bytesize=bytesize)
    # emit code
    outstream.write(f'{assignment}{start_delimiter}\n')
    for glyph in font.glyphs:
        outstream.write('  ')
        for byte in glyph.as_bytes():
            outstream.write(f'0x{byte:02x}, ')
        outstream.write('\n')
    outstream.write(f'{end_delimiter}\n')
    return font
