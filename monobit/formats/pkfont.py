"""
monobit.formats.pkfont - TeX packed font font files

(c) 2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import count

from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..raster import Raster
from .. import struct
from ..struct import big_endian as be, bitfield, sizeof
from ..binary import ceildiv, align
from ..properties import Props
from ..magic import Regex


@loaders.register(
    name='pkfont',
    magic=(b'\xf7\x59',),
    # file name pattern is '{name}.{dpi}PK'
    patterns=(Regex(r'.+\.\d+pk'),),

)
def load_pkfont(instream):
    """Load fonts from a METAFONT/TeX PKFONT."""
    return _load_pkfont(instream)


###############################################################################
# https://www.tug.org/TUGboat/tb06-3/tb13pk.pdf

_PK_PRE0 = be.Struct(
    # 0xf7, 247
    command='uint8',
    # 0x59, 89
    i='uint8',
    # length of name string
    k='uint8',
)
# x[k] k-byte name string

_PK_PRE1 = be.Struct(
    # design size of the file in 1/2**16 points
    ds='uint32',
    # checksum of the file
    cs='uint32',
    # horizontal pixels per point, multiplied by 2**16
    hppp='uint32',
    # vertical pixels per point, multiplied by 2**16
    vppp='uint32',
)

def _read_preamble(instream):
    """Read a pk_pre preamble command."""
    preamble0 = _PK_PRE0.read_from(instream)
    name = instream.read(preamble0.k)
    preamble1 = _PK_PRE1.read_from(instream)
    return Props(
        **vars(preamble0),
        x=name,
        **vars(preamble1)
    )

def _read_command(command, instream):
    """Read a command."""
    if command == 240:
        # pk_xxx1
        k = int(be.uint8.read_from(instream))
        return instream.read(k)
    elif command == 241:
        # pk_xxx2
        k = int(be.uint16.read_from(instream))
        return instream.read(k)
    elif command == 242:
        # pk_xxx3
        kbytes = instream.read(3)
        k = int.from_bytes(kbytes, 'big')
        return instream.read(k)
    elif command == 243:
        # pk_xxx4
        k = int(be.uint32.read_from(instream))
        return instream.read(k)
    elif command == 244:
        # pk_yyy
        y = int(be.uint32.read_from(instream))
        return y
    elif command == 245:
        # pk_post
        instream.read()
        return None
    elif command == 246:
        # pk_no_op
        return None
    elif command == 247:
        raise ValueError('Preamble not expected here')
    raise ValueError('Invalid command %d', command)


# flag byte
_CHAR_FLAG = be.Struct(
    # > The most significant four nybbles
    # > of the flag byte yield the dyn-f value for that
    # > character. (Notice that only values of 0 through 14
    # > are legal for dyn-f, with 14 indicating a bit mapped
    # > character; thus, the flag bytes do not conflict with
    # > the command bytes, whose upper nybble is always 15.)
    dyn_f=bitfield('uint8', 4),
    # >     The next bit (with weight 16) indicates whether
    # > the first run count is a black count or a white count,
    # > with a one indicating a black count. For bit-mapped
    # > characters, this bit should be set to a zero
    ink_run=bitfield('uint8', 1),
    # > The next bit (with weight 8) indicates whether certain
    # > later parameters (referred to as size parameters) are
    # > given in one-byte or two-byte quantities, with a one
    # > indicating that they are in two-byte quantities.
    two_byte=bitfield('uint8', 1),
    # > The last two bits are concatenated on to the beginning
    # > of the length parameter in the character preamble
    prepend=bitfield('uint8', 2),
)
# >   However, if the last three bits of the flag
# > byte are all set (normally indicating that the size
# > parameters are two-byte values and that a 3 should
# > be prepended to the length parameter), then a long
# > format of the character preamble should be used
# > instead of one of the short forms.
# >   Therefore, there are three formats for the
# > character preamble, and which one is used depends
# > on the least significant three bits of the flag byte.
# > If the least significant three bits are in the range
# > zero through three, the short format is used. If
# > they are in the range four through six, the extended
# > short format is used. Otherwise, if the least
# > significant bits are all set, then the long form of the
# > character preamble is used.

# short form
_CHAR_SHORT = be.Struct(
    # > The flag parameter is the flag byte.
    ## flag[1]
    # > The parameter pl (packet length) contains the offset of
    # > the byte following this character descriptor, with
    # > respect to the beginning of the tfm width parameter.
    # > This is given so a PK reading program can, once it
    # > has read the flag byte, packet length, and character
    # > code (cc), skip over the character by simply reading
    # > this many more bytes. For the two short forms
    # > of the character preamble, the last two bits of
    # > the flag byte should be considered the two most-
    # > significant bits of the packet length.
    pl='uint8',
    cc='uint8',
    # 'tfm widths', defined somewhere entirely differently, sigh.
    # https://web.archive.org/web/20120722013525/http://www-users.math.umd.edu/~asnowden/comp-cont/tfm.html
    # TeX Font Metric files have a width, height (ascent) and depth (descent)
    # presumably in that order?
    tfm=be.uint8 * 3,
    # 'horizontal escapement (pixels)'
    # named dm in spec
    dx='uint8',
    # >     The w parameter is the width and the h
    # > parameter is the height in pixels of the minimum
    # > bounding box.
    w='uint8',
    h='uint8',
    # > The dx and dy parameters are the
    # > horizontal and vertical escapements, respectively.
    # > In the short formats, dy is assumed to be zero and
    # > dm is dy but in pixels; in the long format, dx and
    # > dy are both in pixels multiplied by 216.
    # > The hoff is the horizontal offset from the upper left pixel to
    # > the reference pixel; the voff is the vertical offset.
    # > They are both given in pixels, with right and down
    # > being positive. The reference pixel is the pixel
    # > which occupies the unit square in METAFONT; the
    # > METAFONT reference point is the lower left hand
    # > corner of this pixel.
    hoff='int8',
    voff='int8',
)

# extended short form
_CHAR_EXTENDED = be.Struct(
    ## flag[1]
    pl='uint16',
    cc='uint8',
    tfm=be.uint8 * 3,
    # named dm in spec
    dx='uint16',
    w='uint16',
    h='uint16',
    hoff='int16',
    voff='int16',
)

# long forrm
_CHAR_LONG = be.Struct(
    ## flag[1]
    pl='uint32',
    cc='uint32',
    tfm=be.uint8 * 4,
    # >      The dx and dy parameters are the
    # > horizontal and vertical escapements, respectively.
    # > In the short formats, dy is assumed to be zero and
    # > dm is dy [they mean dx?] but in pixels; in the long format, dx and
    # > dy are both in pixels multiplied by 2**16.
    dx='uint32',
    dy='uint32',
    w='uint32',
    h='uint32',
    # The spec seems to say uint, but all the other forms are signed
    hoff='int32',
    voff='int32',
)

def _read_chardef(first, instream):
    """Read a character definition."""
    flag = _CHAR_FLAG.from_bytes(first)
    if flag.two_byte == 1 and flag.prepend == 3:
        chardef = _CHAR_LONG.read_from(instream)
        packet_length = chardef.pl
        tfm_offset = 8
        denominator = 2**16
    elif flag.two_byte == 1:
        chardef = _CHAR_EXTENDED.read_from(instream)
        packet_length = flag.prepend * 0x10000 + chardef.pl
        tfm_offset = 3
        denominator = 1
    else:
        chardef = _CHAR_SHORT.read_from(instream)
        packet_length = flag.prepend * 0x100 + chardef.pl
        tfm_offset = 2
        denominator = 1
    # The parameter pl (packet length) contains the offset of
    # the byte following this character descriptor, with
    # respect to the beginning of the tfm width parameter
    payload_size = packet_length + tfm_offset - sizeof(chardef)
    payload = instream.read(payload_size)
    if len(payload) != payload_size:
        logging.warning('Raster data truncated: %d < %d', len(payload), payload_size)
    char = Props(
        **vars(flag),
        **vars(chardef),
        denominator=denominator,
        raster_data=payload
    )
    return char


def _convert_char(char):
    """Convert pkfont character definition to glyph."""
    if char.dyn_f == 14:
        # plain bitmap data
        raster = Raster.from_bytes(
            char.raster_data, stride=char.w, width=char.w, align='bit',
        )
    else:
        bitmap = _unpack_bits(char)
        raster = Raster.from_vector(bitmap, stride=char.w)
    raster = raster.crop(bottom=max(0, raster.height-char.h))
    # convert glyph properties
    props = dict(
        codepoint=char.cc,
        left_bearing=-char.hoff,
        shift_up=char.voff-raster.height+1,
        # how is 'escapement' defined? is it the advance width?
        # or does it exclude the initial offset?
        right_bearing=char.dx//char.denominator-char.w+char.hoff,
        # if there's a dy 'vertical escapement' defined, what do we do with it?
        # also, what _is_ the TFM width??
    )
    return Glyph(raster, **props)


def _unpack_bits(char):
    """Unpack a packed character definition."""
    # we assume raster data is byte aligned and its length is determined
    # by the package size. PKfonts.pdf states that a character flag can also
    # occur in the middle of a byte but that contradicts Rockicki's tb13pk.pdf
    # which states that the packet size can be used to jump to the next
    # character definition record.
    iternyb = _iter_nybbles(char.raster_data)
    repeat = 0
    bitmap = []
    colour = bool(char.ink_run)
    while True:
        try:
            run, new_repeat = _pk_packed_num(iternyb, char.dyn_f)
            if new_repeat is not None:
                repeat = new_repeat
        except StopIteration as e:
            break
        # check if we go past a row boundary
        row_remaining = char.w - (len(bitmap) % char.w)
        # > The current row is defined as the row on which the
        # > first pixel of the next run count will lie. The repeat
        # > count is set back to zero when the last pixel in the
        # > current row is seen, and the row is sent out
        if run >= row_remaining:
            bitmap.extend([colour] * row_remaining)
            run -= row_remaining
            # apply row repeats
            bitmap.extend(bitmap[-char.w:]*repeat)
            repeat = 0
        # even if the rest of the run is longer than a row,
        # there are no more repeat markers
        bitmap.extend([colour] * run)
        # flip colour for next run
        colour = not colour
    return bitmap


def _iter_nybbles(bytestr):
    """Iterate over a bytes string in 4-bit steps (big-endian)."""
    for byte in bytestr:
        hi, lo = divmod(byte, 16)
        yield hi
        yield lo


# implements the pseudocode from
# https://www.tug.org/TUGboat/tb06-3/tb13pk.pdf
def _pk_packed_num(iternyb, dyn_f):
    """
    Read a run number or repeat count.
    returns a tuple run, repeat
    """
    i = next(iternyb)
    if i < 14:
        if i == 0:
            j = 0
            while j == 0:
                j = next(iternyb)
                i += 1
            while i > 0:
                j = j * 16 + next(iternyb)
                i -= 1
            run = j - 15 + (13 - dyn_f)*16 + dyn_f
        elif i <= dyn_f:
            run = i
        else:
            get_nyb = next(iternyb)
            run = (i - dyn_f - 1)*16 + get_nyb + dyn_f + 1
        return run, None
    if i == 14:
        repeat, should_be_none = _pk_packed_num(iternyb, dyn_f)
        if should_be_none is not None:
            logging.warning('Duplicate repeat count')
    else:
        repeat = 1
    # send_out(true, repeat_count)
    # not clear what this means:
    # pk_packed_num <- pk_packed_num
    run, should_be_none = _pk_packed_num(iternyb, dyn_f)
    if should_be_none is not None:
        logging.warning('Duplicate repeat count')
    return run, repeat


def _load_pkfont(instream):
    """Load fonts from a METAFONT/TeX PKFONT."""
    # read preamble
    preamble = _read_preamble(instream)
    # read char definitions and _special_ strings
    chars = []
    specials = []
    while True:
        command = instream.read(1)
        if not command:
            break
        if ord(command) >= 240:
            special = _read_command(ord(command), instream)
            specials.append(special)
        else:
            char = _read_chardef(command, instream)
            chars.append(char)
    # converter
    glyphs = tuple(_convert_char(_char) for _char in chars)
    return Font(glyphs)
