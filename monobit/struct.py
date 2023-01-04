"""
monobit.struct - binary structures

(c) 2019--2023 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import ctypes
from ctypes import sizeof

import logging
from types import SimpleNamespace
from functools import partial


##############################################################################
# binary structs

# base types
char = ctypes.c_char
uint8 = ctypes.c_uint8
int8 = ctypes.c_int8
uint16 = ctypes.c_uint16
int16 = ctypes.c_int16
uint32 = ctypes.c_uint32
int32 = ctypes.c_int32


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


class bitfield:
    """Pair (type, bit_width) to describe bit field."""

    def __init__(self, fieldtype, bits):
        """Pair (type, bit_width) to describe bit field."""
        self.type = fieldtype
        self.bits = bits

flag = bitfield('B', 1)

def _parse_type(atype):
    """Convert struct member type specification to ctypes base type or array."""
    if isinstance(atype, bitfield):
        return (*_parse_type(atype.type), atype.bits)
    if isinstance(atype, NewType):
        return _parse_type(atype._ctype)
    if isinstance(atype, type):
        return atype,
    try:
        return TYPES[atype],
    except KeyError:
        pass
    if isinstance(atype, str) and atype.endswith('s'):
        return char * int(atype[:-1]),
    raise ValueError('Field type `{}` not understood'.format(atype))


def _build_struct(parent, **description):
    """Use friendly keyword description to build ctypes struct subclass that supports vars()."""
    fields = tuple(
        (_field, *_parse_type(_type))
        for _field, _type in description.items()
    )
    return _define_struct(parent, fields)


def _define_struct(parent, fields):
    """Build ctypes struct subclass with fields list provided."""

    class Struct(parent):
        """Struct with binary representation."""
        _fields_ = fields
        _pack_ = True

        def __repr__(self):
            """String representation."""
            props = vars(self)
            return type(self).__name__ + '({})'.format(
                ', '.join(
                    '{}={}'.format(_fld, _val)
                    for _fld, _val in props.items()
                )
            )

        @property
        def __dict__(self):
            """Extract the fields dictionary."""
            return dict(
                (field, getattr(self, field))
                for field, *_ in self._fields_
            )

        def __add__(self, other):
            """Concatenate structs."""
            addedstruct = _define_struct(parent, self._fields_ + other._fields_)
            return addedstruct(**vars(self), **vars(other))

        def __getattribute__(self, attr):
            """Convert attributes where still necessary."""
            value = super().__getattribute__(attr)
            if isinstance(value, ctypes.Array):
                return tuple(value)
            return value

    return _wrap_struct(Struct)

def _wrap_struct(cstruct):
    """Wrap ctypes structs/struct arrays with convenience methods."""
    cstruct.size = ctypes.sizeof(cstruct)
    cstruct.array = lambda n: _wrap_struct(cstruct * n)
    cstruct.read_from = lambda stream: cstruct.from_buffer_copy(stream.read(ctypes.sizeof(cstruct)))
    cstruct.from_bytes = cstruct.from_buffer_copy
    return cstruct

def _wrap_base_type(ctyp, parent):
    """Wrap ctypes base types with convenience methods."""
    # while struct members defined as ctypes resolve to Python types,
    # base ctypes are objects that are not compatible with Python types
    # so we wrap the base type in a one-member struct
    cls = _build_struct(parent, value=ctyp)
    cls.array = lambda n: _wrap_base_type(ctyp * n, parent)
    cls.read_from = lambda stream: cls.from_buffer_copy(stream.read(ctypes.sizeof(ctyp))).value
    cls.from_bytes = lambda *args: cls.from_buffer_copy(*args).value
    return cls


# interface:
#
# >>> mystruct = big_endian.Struct(one=uint8, two=int32)
# >>> record = mystruct.from_bytes(b'\0\1\2\3\4')
# >>> record
# Struct(one=0, two=16909060)
# >>> hex(record.two)
# '0x1020304'
#
# >>> mystruct = little_endian.Struct(one=uint8, two=int32)
# >>> record = mystruct.from_bytes(b'\0\1\2\3\4')
# >>> hex(record.two)
# '0x4030201'

# note that uint8 etc. are base types while BE.uint8 etc are wrapped
# we can't use the latter in a struct definition

def _binary_types(parent):
    return SimpleNamespace(
        Struct=partial(_build_struct, parent),
        char=_wrap_base_type(char, parent),
        uint8=_wrap_base_type(uint8, parent),
        int8=_wrap_base_type(int8, parent),
        uint16=_wrap_base_type(uint16, parent),
        int16=_wrap_base_type(int16, parent),
        uint32=_wrap_base_type(uint32, parent),
        int32=_wrap_base_type(int32, parent),
    )

# big_endian = _binary_types(ctypes.BigEndianStructure)
# little_endian = _binary_types(ctypes.LittleEndianStructure)



class NewType:

    def __mul__(self, count):
        """Create an array."""
        return self.array(count)

    def from_bytes(self, *args):
        return self._ctype.from_buffer_copy(*args)

    def read_from(self, stream):
        return self.from_bytes(stream.read(self.size))

    def array(self, count):
        return NewArray(self, count)

    @property
    def size(self):
        return ctypes.sizeof(self._ctype)


class NewSimple(NewType):

    def __init__(self, endian, ctype):
        if endian[:1].lower() in ('b', '>'):
            self._ctype = ctype.__ctype_be__
        elif endian[:1].lower() in ('l', '<'):
            self._ctype = ctype.__ctype_le__
        else:
            raise ValueError(f"Endianness '{endian}' not recognised.")

    def __call__(self, value):
        """Instantiate a variable."""
        # but bytes(...) woon't work correctly
        return self._ctype(value).value

    def from_bytes(self, *args):
        return super().from_bytes(*args).value


class NewStruct(NewType):

    def __init__(self, endian, /, **description):
        """Create a structured type."""
        if endian[:1].lower() in ('b', '>'):
            parent = ctypes.BigEndianStructure
        elif endian[:1].lower() in ('l', '<'):
            parent = ctypes.LittleEndianStructure
        else:
            raise ValueError(f"Endianness '{endian}' not recognised.")

        fields = tuple(
            (_field, *_parse_type(_type))
            for _field, _type in description.items()
        )

        class Struct(parent):
            """Struct with binary representation."""
            _fields_ = fields
            _pack_ = True

            @property
            def __dict__(self):
                """Extract the fields dictionary."""
                return dict(
                    (field, getattr(self, field))
                    for field, *_ in self._fields_
                )

            def __getattribute__(self, attr):
                """Convert attributes where still necessary."""
                value = super().__getattribute__(attr)
                if isinstance(value, ctypes.Array):
                    return tuple(value)
                return value

            # deprecate?
            def __add__(self, other):
                """Concatenate structs."""
                addedstruct = NewStruct(endian, **dict(self._fields_), **dict(other._fields_))
                return addedstruct(**vars(self), **vars(other))

        self._ctype = Struct

    def __call__(self, **kwargs):
        """Instantiate a struct variable."""
        return self._ctype(**kwargs)


class NewArray(NewType):

    def __init__(self, struct, count):
        self._count = count
        self._ctype = struct._ctype * count

    def __call__(self, *args):
        """Instantiate a struct variable."""
        array = self._ctype
        # deprecate?
        print('here')
        array.size = self.size
        return array(*args)



class NewStructBE(NewStruct):
    def __init__(self, **description):
        super().__init__('>', **description)

class NewStructLE(NewStruct):
    def __init__(self, **description):
        super().__init__('<', **description)



big_endian = SimpleNamespace(
    Struct=NewStructBE,
    char=NewSimple('>', char),
    uint8=NewSimple('>', uint8),
    int8=NewSimple('>', int8),
    uint16=NewSimple('>', uint16),
    int16=NewSimple('>', int16),
    uint32=NewSimple('>', uint32),
    int32=NewSimple('>', int32),
)

little_endian = SimpleNamespace(
    Struct=NewStructLE,
    char=NewSimple('<', char),
    uint8=NewSimple('<', uint8),
    int8=NewSimple('<', int8),
    uint16=NewSimple('<', uint16),
    int16=NewSimple('<', int16),
    uint32=NewSimple('<', uint32),
    int32=NewSimple('<', int32),
)
