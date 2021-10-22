"""
monobit.struct - property structures

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from collections import OrderedDict
import ctypes


def reverse_dict(orig_dict):
    """Reverse a dict."""
    return {_v: _k for _k, _v in orig_dict.items()}


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
        'ubyte': ctypes.c_uint8,
        'uint8': ctypes.c_uint8,
        'B': ctypes.c_uint8,

        'int8': ctypes.c_int8,
        'b': ctypes.c_int8,

        'word': ctypes.c_uint16,
        'uword': ctypes.c_uint16,
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

        # classmethod __mul__ doesn't seem to work
        @classmethod
        def array(cls, number):
            """Create array."""
            array = cls * number # base.__mul__(cls, number)
            array.size = cls.size * number
            array.from_bytes = array.from_buffer_copy
            array.read_from = lambda stream: array.from_buffer_copy(
                stream.read(ctypes.sizeof(array))
            )
            return array

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
