"""
monobit.binary - binary file utilities

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from collections import OrderedDict
import ctypes


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


##############################################################################
# binary structs

def friendlystruct(_endian, **description):
    """A slightly less clunky interface to struct."""

    if _endian.lower() in ('<', 'little', 'le'):
        base = ctypes.LittleEndianStructure
    elif _endian.lower() in ('>', 'big', 'be'):
        base = ctypes.BigEndianStructure
    else:
        raise ValueError('Endianness `{}` not understood'.format(_endian))

    typemap = {
        'byte': ctypes.c_uint8,
        'uint8': ctypes.c_uint8,
        'B': ctypes.c_uint8,

        'int8': ctypes.c_int8,
        'b': ctypes.c_int8,

        'word': ctypes.c_uint16,
        'uint16': ctypes.c_uint16,
        'H': ctypes.c_uint16,

        'short': ctypes.c_int16,
        'int16': ctypes.c_int16,
        'h': ctypes.c_int16,

        'dword': ctypes.c_uint32,
        'uint32': ctypes.c_uint32,
        'I': ctypes.c_uint32,
        'L': ctypes.c_uint32,

        'long': ctypes.c_int32,
        'int32': ctypes.c_int32,
        'i': ctypes.c_int32,
        'l': ctypes.c_int32,

        'char': ctypes.c_char,
        's': ctypes.c_char,
    }

    def _parse_type(atype):
        if isinstance(atype, type):
            return atype
        try:
            return typemap[atype]
        except KeyError:
            pass
        if isinstance(atype, str) and atype.endswith('s'):
            return ctypes.c_char * int(atype[:-1])
        raise ValueError('Field type `{}` not understood'.format(atype))

    description = {
        _key: _parse_type(_value)
        for _key, _value in description.items()
    }

    class Struct(base):
        """Struct with binary representation."""
        _fields_ = tuple(OrderedDict(**description).items())
        _pack_ = True

        def __repr__(self):
            """String representation."""
            return 'Struct({})'.format(
                ', '.join(
                    '{}={}'.format(field, getattr(self, field))
                    for field, _ in self._fields_
                )
            )

        @property
        def __dict__(self):
            """Fields as dict."""
            return OrderedDict(
                (field, getattr(self, field))
                for field, _ in self._fields_
            )

        def __add__(self, other):
            """Concatenate structs."""
            addedstruct = friendlystruct(_endian, **OrderedDict(self._fields_ + other._fields_))
            return addedstruct(**self.__dict__, **other.__dict__)

        @classmethod
        def read_from(cls, stream):
            """Read struct from file."""
            return cls.from_buffer_copy(stream.read(ctypes.sizeof(cls)))

    Struct.size = ctypes.sizeof(Struct)
    Struct.from_bytes = Struct.from_buffer_copy
    return Struct


friendlystruct.char = ctypes.c_char
friendlystruct.uint8 = ctypes.c_uint8
friendlystruct.int8 = ctypes.c_int8
friendlystruct.uint16 = ctypes.c_uint16
friendlystruct.int16 = ctypes.c_int16
friendlystruct.uint32 = ctypes.c_uint32
friendlystruct.int32 = ctypes.c_int32
friendlystruct.sizeof = ctypes.sizeof
