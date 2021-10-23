"""
monobit.binary - binary utilities

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


def ceildiv(num, den):
    """Integer division, rounding up."""
    return -(-num // den)

def align(num, exp):
    """Round up to multiple of 2**exp."""
    mask = 2**exp - 1
    return (num + mask) & ~mask

def bytes_to_bits(inbytes, width=None):
    """Convert bytes/bytearray/sequence of int to tuple of bits."""
    bitstr = ''.join('{:08b}'.format(_b) for _b in inbytes)
    bits = tuple(_c == '1' for _c in bitstr)
    return bits[:width]

def int_to_bytes(in_int, byteorder='big'):
    """Convert integer to bytes."""
    return in_int.to_bytes(max(1, ceildiv(in_int.bit_length(), 8)), byteorder)

def bytes_to_int(in_bytes, byteorder='big'):
    """Convert integer to bytes."""
    return int.from_bytes(bytes(in_bytes), byteorder)
