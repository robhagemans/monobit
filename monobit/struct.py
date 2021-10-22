"""
monobit.struct - property structures

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from types import SimpleNamespace
import ctypes
import struct
from ctypes import sizeof


def reverse_dict(orig_dict):
    """Reverse a dict."""
    return {_v: _k for _k, _v in orig_dict.items()}



##############################################################################
# property sets

class Props(SimpleNamespace):
    """
    SimpleNamespace with the dunder methods of a dict
    Not a mapping but allows both key-style and attribute-style access
    """

    def __getitem__(self, item):
        return vars(self)[item.replace('-', '_')]

    def __setitem__(self, item, value):
        vars(self)[item.replace('-', '_')] = value

    def __len__(self):
        return len(vars(self))

    def __iter__(self):
        return iter(_item.replace('_', '-') for _item in vars(self))

    def __str__(self):
        return '\n'.join(f'{_k}: {_v}' for _k, _v in vars(self).items())


##############################################################################
# binary structs

def _wraptype(ctyp):
    """Wrap ctypes types with some convenience members."""
    # ctyp.array(n) is ctyp * n but with the same convenience members
    ctyp.size = ctypes.sizeof(ctyp)
    ctyp.array = lambda n: _wraptype(ctyp * n)
    ctyp.read_from = lambda stream: ctyp.from_buffer_copy(stream.read(ctypes.sizeof(ctyp)))
    ctyp.from_bytes = ctyp.from_buffer_copy
    return ctyp


# base types
char = _wraptype(ctypes.c_char)
uint8 = _wraptype(ctypes.c_uint8)
int8 = _wraptype(ctypes.c_int8)
uint16 = _wraptype(ctypes.c_uint16)
int16 = _wraptype(ctypes.c_int16)
uint32 = _wraptype(ctypes.c_uint32)
int32 = _wraptype(ctypes.c_int32)


# type strings
TYPES = {
    'byte': uint8,
    'ubyte': uint8,
    'uint8': uint8,
    'B': uint8,

    'int8': int8,
    'b': int8,

    'word': uint16,
    'uword': uint16,
    'uint16': uint16,
    'H': uint16,

    'short': int16,
    'int16': int16,
    'h': int16,

    'dword': uint32,
    'uint32': uint32,
    'I': uint32,
    'L': uint32,

    'long': int32,
    'int32': int32,
    'i': int32,
    'l': int32,

    'char': char,
    's': char,
}


def friendlystruct(_endian, **description):
    """A slightly less clunky interface to struct."""

    # get base class based on endianness

    if _endian.lower() in ('<', 'little', 'le'):
        base = ctypes.LittleEndianStructure
    elif _endian.lower() in ('>', 'big', 'be'):
        base = ctypes.BigEndianStructure
    else:
        raise ValueError('Endianness `{}` not understood'.format(_endian))

    # build _fields_ description

    def _parse_type(atype):
        if isinstance(atype, type):
            return atype
        try:
            return TYPES[atype]
        except KeyError:
            pass
        if isinstance(atype, str) and atype.endswith('s'):
            return char * int(atype[:-1])
        raise ValueError('Field type `{}` not understood'.format(atype))

    description = {
        _key: _parse_type(_value)
        for _key, _value in description.items()
    }

    # subclass to define some additional methods

    class Struct(base):
        """Struct with binary representation."""
        _fields_ = tuple(description.items())
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
            return dict(
                (field, getattr(self, field))
                for field, _ in self._fields_
            )

        def __add__(self, other):
            """Concatenate structs."""
            addedstruct = friendlystruct(_endian, **dict(self._fields_ + other._fields_))
            return addedstruct(**self.__dict__, **other.__dict__)

    return _wraptype(Struct)


friendlystruct.char = char
friendlystruct.uint8 = uint8
friendlystruct.int8 = int8
friendlystruct.uint16 = uint16
friendlystruct.int16 = int16
friendlystruct.uint32 = uint32
friendlystruct.int32 = int32
friendlystruct.sizeof = ctypes.sizeof
