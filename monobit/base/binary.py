"""
monobit.base.binary - binary utilities

(c) 2019--2024 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


def ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)


def align(num, exp):
    """Round up to multiple of 2**exp."""
    mask = 2**exp - 1
    return (num + mask) & ~mask


def bytes_to_bits(byteseq, width=None):
    """
    Convert bytes/bytearray/sequence of int to tuple of bits.
    Note that bytes_to_pixels is the preferred alternative.
    """
    bitstr = bin(int.from_bytes(byteseq, 'big'))[2:].zfill(8 * len(byteseq))
    bits = tuple(_c == '1' for _c in bitstr)
    if width is None:
        return bits
    return bits[:width]


def int_to_bytes(in_int, byteorder='big'):
    """Convert integer to bytes."""
    return in_int.to_bytes(max(1, ceildiv(in_int.bit_length(), 8)), byteorder)


def bytes_to_int(in_bytes, byteorder='big'):
    """Convert integer to bytes."""
    return int.from_bytes(bytes(in_bytes), byteorder)


def reverse_by_group(bitseq, fill='0', group_size=8):
    """
    Reverse bits in every byte in string representation of binary
    Bit sequence is extended to end on byte boundary.
    """
    bitseq = bitseq.ljust(ceildiv(len(bitseq), group_size) * group_size, fill)
    args = [iter(bitseq)] * group_size
    bitseq = ''.join(''.join(_chunk[::-1]) for _chunk in zip(*args))
    return bitseq


###############################################################################
# bytes to pixels

# default string inklevels
INKLEVELS = {
    256: ''.join(chr(_i) for _i in range(256)),
    16: '0123456789abcdef',
    4: '0123',
    2: '01',
}


def bytes_to_pixels(byteseq, levels):
    """Convert bytes to pixels in level-specific representation."""
    if levels not in (2, 4, 16, 256):
        raise ValueError(f'Unsupported `levels` value: {levels}')
    if not byteseq:
        return ''
    if levels == 256:
        return byteseq.decode('latin-1')
    else:
        to_base = _base_converter(levels)
        bpp = (levels - 1).bit_length()
        pixels_per_byte = 8 // bpp
        return (
            to_base(int.from_bytes(byteseq, 'big'))
                .zfill(pixels_per_byte * len(byteseq))
        )


# base-4 conversion
_HEX_TO_QUAD = str.maketrans({
    '0': '00',
    '1': '01',
    '2': '02',
    '3': '03',
    '4': '10',
    '5': '11',
    '6': '12',
    '7': '13',
    '8': '20',
    '9': '21',
    'a': '22',
    'b': '23',
    'c': '30',
    'd': '31',
    'e': '32',
    'f': '33'
})


def _base_converter(base):
    """Converter to given base."""
    if base == 2:
        return (lambda _v: bin(_v)[2:])
    elif base == 4:
        # keep leading zero, we'll need it anyway
        return (lambda _v: hex(_v)[2:].translate(_HEX_TO_QUAD))
    elif base == 16:
        return (lambda _v: hex(_v)[2:])
    else:
        # we don't need the other bases
        raise ValueError(f'Unsupported base: {base}')
