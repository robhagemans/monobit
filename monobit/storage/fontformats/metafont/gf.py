"""
monobit.storage.fontformats.gf - METAFONT / TeX generic font files

(c) 2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from monobit.storage import loaders, savers, Regex, Glob
from monobit.core import Font, Glyph, Raster
from monobit.base import FileFormatError, UnsupportedError, Props
from monobit.base.struct import big_endian as be
from .tfm import apply_tfm


@loaders.register(
    name='gf',
    magic=(b'\xf7\x83',),
    # file name pattern is '{name}.{dpi}GF' or '{name}.GF'
    patterns=(Regex(r'.+\.\d+gf'), Glob('*.gf')),
)
def load_gf(instream, tfm:str=''):
    """
    Load fonts from a METAFONT Generic Font file.

    tfm: name of TeX Font metrics file to apply (default: determine from filename)
    """
    gf_commands = []
    while instream.peek(0):
        opcode, value = read_opcode(instream)
        gf_commands.append(preprocess_command(opcode, value))
    font = parse_commands(gf_commands)
    # apply TFM, if available
    tfm_name = tfm or instream.name.partition('.')[0] + '.tfm'
    font = apply_tfm(font, instream.where, tfm_name, font.dpi.x / 72.27, font.dpi.y / 72.27)
    return font



def read_string8(instream):
    k = int(be.uint8.read_from(instream))
    return instream.read(k)

def read_string16(instream):
    k = int(be.uint16.read_from(instream))
    return instream.read(k)

def read_uint24(instream):
    kbytes = instream.read(3)
    return int.from_bytes(kbytes, 'big')

def read_string24(instream):
    k = read_uint24(instream)
    return instream.read(k)

def read_string32(instream):
    k = int(be.uint32.read_from(instream))
    return instream.read(k)


class Opcode:
    """Command opcodes."""
    paint_0 = 0
    # paint_1, ...,
    paint_63 = 63
    paint1 = 64
    paint2 = 65
    paint3 = 66
    boc = 67
    boc1 = 68
    eoc = 69
    skip0 = 70
    skip1 = 71
    skip2 = 72
    skip3 = 73
    new_row_0 = 74
    # , new_row_1, ...
    new_row_164 = 238
    xxx1 = 239
    xxx2 = 240
    xxx3 = 241
    xxx4 = 242
    yyy = 243
    no_op = 244
    char_loc = 245
    char_loc0 = 246
    pre = 247
    post = 248
    post_post = 249


_BOC = be.Struct(
    c='uint32',
    p='int32',
    min_m='int32',
    max_m='int32',
    min_n='int32',
    max_n='int32',
)

_BOC1 = be.Struct(
    c='uint8',
    del_m='uint8',
    max_m='uint8',
    del_n='uint8',
    max_n='uint8',
)

_CHAR_LOC = be.Struct(
    c='uint8',
    dx='uint32', # signed int?
    dy='uint32', # signed int?
    w='uint32',
    p='int32',
)

_CHAR_LOC0 = be.Struct(
    c='uint8',
    dm='uint8', # signed int?
    w='uint32',
    p='int32',
)

_POST = be.Struct(
    p='int32',
    # design size of the file in 1/2**16 points
    ds='uint32',
    # checksum of the file
    cs='uint32',
    # horizontal pixels per point, multiplied by 2**16
    hppp='uint32',
    # vertical pixels per point, multiplied by 2**16
    vppp='uint32',
    min_m='int32',
    max_m='int32',
    min_n='int32',
    max_n='int32'
)

_POST_POST = be.Struct(
    q='uint32',
    i='uint8',
)


def read_opcode(instream):
    """Read a command opcode and accompanying values."""
    opcode = ord(instream.read(1))
    if Opcode.paint_0 <= opcode <= Opcode.paint_63:
        value = None
    elif opcode == Opcode.paint1:
        value = int(be.uint8.read_from(instream))
    elif opcode == Opcode.paint2:
        value = int(be.uint16.read_from(instream))
    elif opcode == Opcode.paint3:
        value = read_uint24(instream)
    elif opcode == Opcode.boc:
        value = _BOC.read_from(instream)
    elif opcode == Opcode.boc1:
        value = _BOC1.read_from(instream)
    elif opcode == Opcode.eoc:
        value = None
    elif opcode == Opcode.skip0:
        value = None
    elif opcode == Opcode.skip1:
        value = int(be.uint8.read_from(instream))
    elif opcode == Opcode.skip2:
        value = int(be.uint16.read_from(instream))
    elif opcode == Opcode.skip3:
        value = read_uint24(instream)
    elif Opcode.new_row_0 <= opcode <= Opcode.new_row_164:
        value = None
    elif opcode == Opcode.xxx1:
        value = read_string8(instream)
    elif opcode == Opcode.xxx2:
        value = read_string16(instream)
    elif opcode == Opcode.xxx3:
        value = read_string24(instream)
    elif opcode == Opcode.xxx4:
        value = read_string32(instream)
    elif opcode == Opcode.yyy:
        value = int(be.uint32.read_from(instream))
    elif opcode == Opcode.no_op:
        value = None
    elif opcode == Opcode.char_loc:
        value = _CHAR_LOC.read_from(instream)
    elif opcode == Opcode.char_loc0:
        value = _CHAR_LOC0.read_from(instream)
    elif opcode == Opcode.pre:
        value = Props(i=int(be.uint8.read_from(instream)), x=read_string8(instream))
    elif opcode == Opcode.post:
        value = _POST.read_from(instream)
    elif opcode == Opcode.post_post:
        value = _POST_POST.read_from(instream)
        instream.read()
    else:
        raise FileFormatError(f'Unrecognised GF opcode {opcode}')
    return opcode, value


def preprocess_command(opcode, value):
    """Convert opcodes into a condensed set of commands."""
    if opcode == Opcode.boc1:
        command = 'boc'
        value = Props(
            c=value.c,
            p=-1,
            min_m=value.max_m-value.del_m, max_m=value.max_m,
            min_n=value.max_n-value.del_n, max_n=value.max_n,
        )
    elif opcode == Opcode.boc:
        command = 'boc'
    elif opcode == Opcode.eoc:
        command = 'eoc'
    elif Opcode.paint_0 <= opcode <= Opcode.paint_63:
        command = 'paint'
        value = opcode - Opcode.paint_0
    elif opcode in (Opcode.paint1, Opcode.paint2, Opcode.paint3):
        command = 'paint'
    elif opcode == Opcode.skip0:
        command = 'skip'
        value = 0
    elif opcode in (Opcode.skip1, Opcode.skip2, Opcode.skip3):
        command = 'skip'
    elif Opcode.new_row_0 <= opcode <= Opcode.new_row_164:
        command = 'new_row'
        value = opcode - Opcode.new_row_0
    elif opcode in (Opcode.xxx1, Opcode.xxx2, Opcode.xxx3, Opcode.xxx4):
        command = 'xxx'
    elif opcode == Opcode.yyy:
        command = 'yyy'
    elif opcode == Opcode.no_op:
        command = 'no_op'
    elif opcode == Opcode.char_loc:
        command = 'char_loc'
    elif opcode == Opcode.char_loc0:
        command = 'char_loc'
        value = Props(c=value.c, dx=65536*value.dm, dy=0, w=value.w, p=value.p)
    elif opcode == Opcode.pre:
        command = 'pre'
    elif opcode == Opcode.post:
        command = 'post'
    elif opcode == Opcode.post_post:
        command = 'post_post'
    return command, value


def parse_commands(commands):
    """Convert commands to font."""
    preamble = None
    postamble = None
    glyphs = []
    metrics = {}
    current_char = None
    paint_switch = 0
    for command, value in commands:
        # preamble
        if not preamble:
            if command != 'pre' or value.i != 131:
                raise FileFormatError('Not a GF file: incorrect signature')
            preamble = value

        if command == 'boc':
            current_char = Props(
                c=value.c,
                p=value.p,
                width=value.max_m - value.min_m + 1,
                height=value.max_n - value.min_n + 1,
                matrix=['']
            )
            paint_switch = 0

        elif command == 'paint':
            current_char.matrix[-1] += chr(ord('0') + paint_switch) * value
            paint_switch = 1 - paint_switch

        elif command == 'skip':
            current_char.matrix[-1] = (
                current_char.matrix[-1].ljust(current_char.width, '0')
            )
            current_char.matrix += ['0' * current_char.width] * (value-1)
            current_char.matrix.append('')
            paint_switch = 0

        elif command == 'new_row':
            current_char.matrix[-1] = (
                current_char.matrix[-1].ljust(current_char.width, '0')
            )
            current_char.matrix.append('0' * value)
            paint_switch = 1

        elif command == 'eoc':
            current_char.matrix[-1] = (
                current_char.matrix[-1].ljust(current_char.width, '0')
            )
            current_char.matrix += ['0' * current_char.width] * (
                current_char.height - len(current_char.matrix)
            )
            glyph = Glyph.from_matrix(
                current_char.matrix, inklevels='01',
                codepoint=current_char.c,
            )
            glyphs.append(glyph)

        elif command == 'post':
            postamble = value

        elif command == 'char_loc':
            metrics[value.c] = Props(
                advance_width=value.dx / 2**16,
                # dy is vertical displacement, do we support this?
                scalable_width=value.w / 2**20 * postamble.ds / 2**20 * postamble.hppp / 2**16,
            )

        elif command == 'post_post':
            break

    metriclist = (
        # > Characters whose codes differ by a multiple of 256
        # > are assumed to share the same font metric infor-
        # > mation, hence the TFM file contains only residues
        # > of character codes modulo 256. This convention
        # > is intended for oriental languages, when there are
        # > many character shapes but few distinct widths.
        metrics[ord(_g.codepoint) % 256] for _g in glyphs
    )
    glyphs = (
        _g.modify(
            right_bearing=_m.advance_width-_g.width,
            scalable_width=round(_m.scalable_width, 2),
        )
        for _g, _m in zip(glyphs, metriclist)
    )
    return Font(
        glyphs,
        point_size=postamble.ds / 2**20,
        dpi=(round(postamble.hppp * 72.27 / 2**16), round(postamble.vppp * 72.27 / 2**16)),
        **{'metafont.checksum': postamble.cs},
    )
