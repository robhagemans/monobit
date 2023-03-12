"""
monobit.formats.borland - Borland Graphics Interface .CHR files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..storage import loaders, savers
from ..magic import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..struct import little_endian as le, bitfield
from ..vector import StrokePath, StrokeMove


_BGI_MAGIC = b'PK\b\bBGI '

@loaders.register(
    name='borland',
    magic=(_BGI_MAGIC,),
    patterns=('*.chr',),
)
def load_borland(instream):
    """Load a Borland BGI stroke font."""
    bgi_data = _read_borland(instream)
    logging.debug(bgi_data)
    font = _convert_borland(**bgi_data)
    return font

@savers.register(linked=load_borland)
def save_borland(fonts, outstream):
    """Save a Borland BGI stroke font."""
    if len(fonts) > 1:
        raise FileFormatError('BBC font file can only store one font.')
    bgi_data = _convert_to_borland(fonts[0])
    _write_borland(outstream, **bgi_data)


# from the BGIKIT: BGIFNT.ZIP/FE.DOC
# e.g. at http://annex.retroarchive.org/cdrom/nightowl-004/025A/index.html
# also https://www.fileformat.info/format/borland-chr/corion.htm
_HEADER = le.Struct(
    HeaderSize='word',
    fname='4s',
    # > font file size
    DataSize='word',
    MajorVersion='byte',
    MinorVersion='byte',
    # 0x0100
    minimal_version='word',
)

# the file format seems to have a double header; the docs mention it is v 2.0
# so perhaps 1.0 excludes the additional header
_HEADER2 = le.Struct(
    # > 80h     '+'  flags stroke file type
    signature='1s',
    # > 81h-82h  number chars in font file (n)
    number_chars='word',
    undefined0='byte',
    # > 84h      ASCII value of first char in file
    first_char='byte',
    # > 85h-86h  offset to stroke definitions (8+3n)
    # actually, 16 + 3n ?
    stroke_offset='word',
    # normally 0
    scan_flag='byte',
    # > 88h      distance from origin to top of capital
    capital_top='int8',
    # > 89h      distance from origin to baseline
    baseline='int8',
    # >> 008Ah                   1 byte   Distance from origin to bottom descender
    descent='int8',
    # >> 008Bh                   4 char   Four character name of font
    # we need another byte for null terminator and/or alignment, anyway we need it
    four_char_name='5s',
)

_STROKE_CODE = le.Struct(
    # bitfields in LE order
    # x and y are signed
    x=bitfield('int16', 7),
    op0=bitfield('int16', 1),
    y=bitfield('int16', 7),
    op1=bitfield('int16', 1),
)


def _read_borland(instream):
    """Read a Borland BGI stroke font."""
    magic = instream.read(8)
    if magic != _BGI_MAGIC:
        raise FileFormatError(
            f'Not a Borland BGI font: magic bytes {magic}. not recognised'
        )
    frontmatter = instream.read(120)
    description, _, headerbytes = frontmatter.partition(b'\x1a')
    description  = description.rstrip(b'\0').decode('ascii', 'replace')
    header = _HEADER.from_bytes(headerbytes)
    header2 = _HEADER2.read_from(instream)
    offsets = le.uint16.array(header2.number_chars).read_from(instream)
    widths = le.uint8.array(header2.number_chars).read_from(instream)
    glyphbytes = [
        instream.read(_next-_offs)
        for _offs, _next in zip(offsets, offsets[1:])
    ]
    glyphbytes.append(instream.read())
    return dict(
        header=header,
        description=description,
        old_header=header2,
        offsets=offsets,
        widths=widths,
        glyphbytes=glyphbytes
    )

def _convert_borland(
        header, description, old_header,
        offsets, widths, glyphbytes
    ):
    """Convert BGI font data to monobit Font."""
    glyphs = []
    for codepoint, (code, width) in enumerate(
            zip(glyphbytes, widths), old_header.first_char
        ):
        if code.endswith(b'\0\0'):
            code =  code[:-2]
        absmoves = ((StrokePath.MOVE, 0, -old_header.baseline),) + tuple(
            _convert_stroke_code(first, second)
            for first, second in zip(code[::2], code[1::2])
        )
        relmoves = (
            (cmd, nx-x, ny-y)
            for (cmd, nx, ny), (_, x, y) in zip(absmoves[1:], absmoves)
        )
        path = StrokePath(relmoves)
        glyphs.append(Glyph.from_path(
            path, advance_width=width, codepoint=codepoint
        ))
    return Font(
        glyphs, ascent=old_header.capital_top, descent=-old_header.descent,
        shift_up=-old_header.baseline,
        notice=description, family=header.fname.decode('ascii', 'replace'),
    )


def _convert_stroke_code(first, second):
    """Convert two-byte stroke code to path command."""
    code = _STROKE_CODE.from_bytes(bytes((first, second)))
    opcode = code.op0, code.op1
    if opcode == (0, 0):
        return (StrokePath.MOVE, 0, 0)
    if opcode == (0, -1):
        logging.warning('Do not know how to process opcode (0, 1)')
        return (StrokePath.MOVE, 0, 0)
    if opcode == (-1, 0):
        return StrokePath.MOVE, code.x, code.y
    if opcode == (-1, -1):
        return StrokePath.LINE, code.x, code.y
    raise ValueError(opcode)


###############################################################################
# BGI writer

def _convert_to_stroke_code(command, absx, absy):
    """Convert path command to two-byte stroke code."""
    return _STROKE_CODE(
        op0=-1, op1=-1 * (command==StrokePath.LINE),
        x=absx, y=absy
    )

def _make_contiguous(font):
    """Fill out a contiguous range of glyphs."""
    # we need a contiguous range between the min and max codepoints
    codepoints = font.get_codepoints()
    ord_glyphs = [
        font.get_glyph(_codepoint, missing='empty')
        for _codepoint in range(min(codepoints)[0], max(codepoints)[0]+1)
    ]
    font = font.modify(ord_glyphs)
    return font


def _convert_to_borland(font):
    """Convert monobit Font to BGI font data."""
    font = _make_contiguous(font)
    glyphbytes = []
    widths = []
    offsets = []
    for glyph in font.glyphs:
        code = []
        if glyph.path:
            path = glyph.path.as_moves()
            cmd = (_move.command for _move in path)
            absx = accumulate(_move.dx for _move in path)
            absy = accumulate(_move.dy for _move in path)
            absmoves = zip(cmd, absx, absy)
            code = [
                bytes(_convert_to_stroke_code(*_triplet))
                for _triplet in absmoves
            ]
            # terminator
            code.append(bytes(_STROKE_CODE(op0=0, op1=0, x=0, y=0)))
        glyphbytes.append(b''.join(code))
    stroke_offset = _HEADER2.size + 3*len(font.glyphs)
    header = _HEADER(
        HeaderSize=0x80,
        fname=font.name[:4].encode('ascii', 'replace').upper(),
        DataSize=stroke_offset+sum(len(_code) for _code in glyphbytes),
        MajorVersion=1,
        MinorVersion=0,
        minimal_version=1,
    )
    description = font.notice
    old_header = _HEADER2(
        signature=b'+',
        number_chars=len(font.glyphs),
        first_char=int(font.glyphs[0].codepoint),
        stroke_offset=stroke_offset,
        capital_top=font.ascent,
        # our paths start at the baseline
        baseline=0,
        # is negative in BGI file
        descent=-font.descent,
        # seems to be kept empty by BGI
        #four_char_name=font.name[:4].encode('ascii', 'replace'),
    )
    offsets = (0, *accumulate(len(_b) for _b in glyphbytes[:-1]))
    offsets = le.uint16.array(old_header.number_chars)(*offsets)
    widths = le.uint8.array(old_header.number_chars)(
        *(_g.advance_width for _g in font.glyphs)
    )
    return dict(
        header=header,
        description=description,
        old_header=old_header,
        offsets=offsets,
        widths=widths,
        glyphbytes=glyphbytes,
    )


def _write_borland(outstream, header, description, old_header, offsets, widths, glyphbytes):
    """Write a Borland BGI stroke font."""
    outstream.write(_BGI_MAGIC)
    outstream.write(description.encode('ascii','replace'))
    outstream.write(b'\0\x1a')
    outstream.write(bytes(header))
    outstream.write(b'\0'*(0x80-outstream.tell()))
    outstream.write(b''.join((
        bytes(old_header), bytes(offsets), bytes(widths),
        *glyphbytes
    )))
